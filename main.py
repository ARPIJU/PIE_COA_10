# main.py
from pathlib import Path
import json
import logging
import pandas as pd

from classes.utils.logging_conf import setup_logging
from classes.io.data_loader import DataLoader
from classes.io.schemas import DataSchema
from classes.processing.cleaning import DataCleaner
from classes.processing.feature_engineering import FeatureEngineer
from classes.domain.apm_models import APMModels
from classes.domain.maintenance import MaintenanceCatalog
from classes.analysis.impact_analysis import ImpactAnalyzer
from classes.analysis.reporting import Reporter
from classes.optimization.scheduler import MaintenanceScheduler


BASE = Path(__file__).resolve().parent
SETTINGS_PATH = BASE / "config" / "settings.json"
OUTPUTS_DIR = BASE / "outputs"


def run_pipeline():
    # 0) Settings + logging
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting pipeline")

    # 1) Load data
    loader = DataLoader(BASE, SETTINGS_PATH)
    df_txt = loader.load_boeing_txt()
    if df_txt is None or df_txt.empty:
        logger.error("Boeing_Perf_Data.txt not loaded or empty. Aborting.")
        return

    events_df, sheet_used = loader.load_first_available_events()
    logger.info("Events loaded from sheet: %s", sheet_used)

    # 2) Schema standardization and mappings
    schema = DataSchema(settings)
    df_txt = schema.standardize_columns(df_txt)
    df_txt = schema.apply_mapping_txt(df_txt)
    schema.validate_txt(df_txt)

    print("Colonnes après mapping:", df_txt.columns.tolist())
    print(df_txt.head(3))

    # 3) Cleaning
    cleaner = DataCleaner()
    df_txt = cleaner.build_timestamp(df_txt, date_col="recorded_date", time_col="time")
    df_txt = cleaner.fix_timestamps(df_txt)
    df_txt = cleaner.remove_duplicates(df_txt)
    df_txt = cleaner.flag_quality(df_txt)
    df_txt = cleaner.clean_numeric_columns(df_txt)

    if "timestamp" in df_txt.columns:
        df_txt = df_txt.dropna(subset=["timestamp"])

    # Events schema
    events_df = schema.standardize_columns(events_df)
    events_df = schema.apply_mapping_events(events_df)
    schema.validate_events(events_df)

    if "event_date" in events_df.columns:
        events_df["event_date"] = pd.to_datetime(events_df["event_date"], errors="coerce")

    # 4) Feature engineering
    fe = FeatureEngineer()
    if "perf_factor" in df_txt.columns and "timestamp" in df_txt.columns:
        df_txt = fe.rolling_baseline(df_txt, metric="perf_factor", window=30)
    else:
        logger.warning("Missing columns for rolling baseline (perf_factor/timestamp). Skipping.")

    agg_airac = fe.aggregate_by_airac(df_txt) if "timestamp" in df_txt.columns else pd.DataFrame()

    # 5) Domain models (APM)
    apm = APMModels(settings)
    df_txt = apm.apply_constants(df_txt)
    if "perf_factor" in df_txt.columns:
        df_txt = apm.perf_to_fuel_factor(df_txt, perf_col="perf_factor", out_col="fuel_factor")
    else:
        logger.warning("perf_factor not found. fuel_factor mapping skipped.")

    if "fuel_flow" in df_txt.columns:
        df_txt = apm.expected_fuel(df_txt, base_fuel_col="fuel_flow", factor_col="fuel_factor", out_col="fuel_expected_corr")
    else:
        logger.warning("fuel_flow not found. expected fuel computation skipped.")

    # 6) Impact analysis
    analyzer = ImpactAnalyzer()
    tol_days = settings["impact"]["merge_tolerance_days"]
    merged = analyzer.join_with_events(
        measures=df_txt,
        events=events_df,
        by=("tail_number",),
        left_on="timestamp",
        right_on="event_date",
        tolerance_days=tol_days
    )

    window_days = settings["impact"]["before_after_window_days"]
    deltas_ff = analyzer.before_after(
        df=merged,
        event_col="event",
        ts_col="timestamp",
        metric="fuel_flow",
        horizon_days=window_days
    )

    # 7) Economics and optimization
    catalog = MaintenanceCatalog.from_settings(settings)
    fuel_price = settings["economics"]["fuel_price_per_unit"]
    constraints = settings["economics"]["constraints"]

    scheduler = MaintenanceScheduler(
        catalog=catalog,
        constraints=constraints,
        fuel_price=fuel_price
    )

    if not deltas_ff.empty:
        if "delta_fuel_flow" in deltas_ff.columns and "delta_fuel" not in deltas_ff.columns:
            deltas_ff["delta_fuel"] = deltas_ff["delta_fuel_flow"]
        elif "delta_fuel" not in deltas_ff.columns:
            deltas_ff["delta_fuel"] = 0.0

    plan = scheduler.optimize(
        deltas=deltas_ff,
        event_col="event",
        delta_fuel_col="delta_fuel",
        default_delta_from_metric="delta_fuel_flow"
    )

    # 8) Reporting
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    reporter = Reporter(OUTPUTS_DIR)

    logger.info("Deltas (fuel_flow) before/after:")
    if not deltas_ff.empty:
        print(deltas_ff.head(10))
        reporter.summary_tables(deltas_ff, sort_col="delta_fuel")
    else:
        logger.warning("No deltas computed; check event alignment or metrics availability.")

    logger.info("Plotting fuel_flow timeline with event markers.")
    reporter.plot_metric(merged, metric="fuel_flow", event_col="event")

    logger.info("Proposed maintenance plan:")
    if not plan.empty:
        print(plan)
        reporter.export_csv(plan, filename="maintenance_plan.csv")
    else:
        logger.warning("No positive ROI events selected under constraints.")

    logger.info("Pipeline completed.")


if __name__ == "__main__":
    run_pipeline()

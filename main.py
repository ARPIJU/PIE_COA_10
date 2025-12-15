from pathlib import Path
import json
import logging
import sys
import pandas as pd

from classes.utils.logging_conf import setup_logging
from classes.io.data_loader import load_events, load_txt_series
from classes.io.schemas import DataSchema
from classes.processing.cleaning import DataCleaner
from classes.domain.apm_models import APMModels
from classes.domain.maintenance import MaintenanceCatalog
from classes.analysis.reporting import Reporter
from classes.optimization.scheduler import MaintenanceScheduler

from classes.analysis.impact_analysis import (
    build_event_intervals,
    compute_non_maintenance_metrics,
    estimate_type_rates,
    compute_maintenance_impacts,
    summarize_global
)

BASE = Path(__file__).resolve().parent
SETTINGS_PATH = BASE / "config" / "settings.json"
OUTPUTS_DIR = BASE / "outputs"


def run_pipeline():
    # Charger settings
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Logging
    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting pipeline")

    try:
        # 1) Chargement brut
        data_dir = settings["paths"]["data_dir"]
        excel_file = BASE / data_dir / settings["paths"]["excel_file"]
        txt_file = BASE / data_dir / settings["paths"]["txt_file"]

        sheet_priority = [s for s in settings["excel_sheets_priority"] if s != "FHMRI"]

        events_df = load_events(str(excel_file), sheet_priority=sheet_priority, ignore_sheets=["FHMRI"])
        df_txt = load_txt_series(str(txt_file), txt_read=settings["txt_read"], columns_mapping=settings["columns_mapping"])

        if df_txt.empty or events_df.empty:
            logger.error("Data not loaded or empty. Aborting.")
            return

        sheet_used = sheet_priority[0]
        events_df["tail_number"] = sheet_used
        logger.info("Events loaded from sheet: %s", sheet_used)

        # 2) Schéma et nettoyage
        schema = DataSchema(settings)

        df_txt = schema.standardize_columns(df_txt)
        df_txt = schema.apply_mapping_txt(df_txt)
        schema.validate_txt(df_txt)

        cleaner = DataCleaner()
        df_txt = cleaner.build_timestamp(df_txt, date_col="recorded_date", time_col="time")
        df_txt = cleaner.fix_timestamps(df_txt)
        df_txt = cleaner.remove_duplicates(df_txt)
        df_txt = cleaner.flag_quality(df_txt)
        df_txt = cleaner.clean_numeric_columns(df_txt)
        if "timestamp" in df_txt.columns:
            df_txt = df_txt.dropna(subset=["timestamp"])
            df_txt["timestamp"] = pd.to_datetime(df_txt["timestamp"], errors="coerce")
            df_txt = df_txt.dropna(subset=["timestamp"])
            df_txt = df_txt.sort_values("timestamp").reset_index(drop=True)

        events_df = schema.standardize_columns(events_df)
        events_df = schema.apply_mapping_events(events_df)
        schema.validate_events(events_df)
        if "date" in events_df.columns:
            events_df["date"] = pd.to_datetime(events_df["date"], errors="coerce")
            events_df = events_df.dropna(subset=["date"])
            events_df = events_df.sort_values("date").reset_index(drop=True)

        logger.info("TXT records: %d | Event records: %d", df_txt.shape[0], events_df.shape[0])

        # 3) Analyse d’impact robuste
        intervals = build_event_intervals(events_df)
        if intervals.empty:
            logger.warning("No intervals could be built. Aborting analysis.")
            return

        non_main = compute_non_maintenance_metrics(df_txt, intervals, settings)
        type_rates = estimate_type_rates(non_main, events_df, settings)
        maint_impacts = compute_maintenance_impacts(events_df, non_main, type_rates, settings)
        summary = summarize_global(non_main, type_rates, maint_impacts)

        # 4) Économie et optimisation
        catalog = MaintenanceCatalog.from_settings(settings)
        fuel_price = settings["economics"]["fuel_price_per_unit"]
        constraints = settings["economics"]["constraints"]

        scheduler = MaintenanceScheduler(
            catalog=catalog,
            constraints=constraints,
            fuel_price=fuel_price
        )

        # Choix de la colonne delta
        delta_col = "impact_model"
        if delta_col not in maint_impacts.columns or maint_impacts[delta_col].isna().all():
            logger.warning("No modeled impact available; falling back to observed impacts if present.")
            if "impact_observed" in maint_impacts.columns and not maint_impacts["impact_observed"].isna().all():
                delta_col = "impact_observed"
            else:
                logger.error("No usable delta found for optimization. Skipping scheduler.")
                plan = pd.DataFrame()
        else:
            plan = scheduler.optimize(
                deltas=maint_impacts,
                event_col="event_name",
                delta_fuel_col=delta_col,
                default_delta_from_metric="impact_observed"
            )

        # 5) Reporting et exports
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        reporter = Reporter(OUTPUTS_DIR)

        reporter.export_csv(non_main, filename="impact_interval_non_maintenance.csv")
        reporter.export_csv(type_rates, filename="maintenance_type_rates.csv")
        reporter.export_csv(maint_impacts, filename="maintenance_impacts_modeled.csv")
        reporter.export_csv(summary, filename="impact_summary.csv")

        if plan is not None and not plan.empty:
            reporter.export_csv(plan, filename="maintenance_plan.csv")
        else:
            logger.warning("No positive ROI events selected or no deltas available under constraints.")

        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.exception("Pipeline failed with an unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()

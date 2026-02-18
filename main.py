from pathlib import Path
import json
import logging
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from classes.utils.logging_conf import setup_logging
from classes.io.data_loader import load_events, load_txt_series
from classes.io.schemas import DataSchema
from classes.processing.cleaning import DataCleaner
from classes.domain.apm_models import APMModels
from classes.domain.maintenance import MaintenanceCatalog
from classes.analysis.reporting import Reporter
from classes.optimization.scheduler import MaintenanceScheduler
from classes.analysis.correlation import correlation

from classes.analysis.impact_analysis import (
    build_event_intervals,
    compute_non_maintenance_metrics,
    estimate_type_rates,
    compute_maintenance_impacts,
    summarize_global
)
from classes.processing.low_pass_filtering import (
    generate_filter_comparison_plots,
    apply_lowpass_filter,
    plot_lowpass_filter_comparison
)
from classes.processing.segregate_plane import segregate_plane_data

BASE = Path(__file__).resolve().parent
SETTINGS_PATH = BASE / "config" / "settings.json"
OUTPUTS_DIR = BASE / "outputs"

def run_pipeline():
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")
    
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting pipeline")

    try:
        # --- 1) Chargement des données ---
        data_dir = settings["paths"]["data_dir"]
        excel_file = BASE / data_dir / settings["paths"]["excel_file"]
        txt_file = BASE / data_dir / settings["paths"]["txt_file"]

        # Lire les événements
        xls = pd.ExcelFile(excel_file)
        frames = []
        for s in settings["excel_sheets_priority"]:
            if s == "FHMRI":
                continue
            if s in xls.sheet_names:
                df_s = pd.read_excel(excel_file, sheet_name=s)
                df_s["tail_number"] = s
                frames.append(df_s)
        events_df = pd.concat(frames, ignore_index=True)

        # Lire la série TXT
        df_txt = load_txt_series(
            str(txt_file),
            txt_read=settings["txt_read"],
            columns_mapping=settings["columns_mapping"]
        )
        if df_txt.empty or events_df.empty:
            logger.error("Data not loaded or empty. Aborting.")
            return

        # --- 2) Nettoyage et standardisation ---
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
        df_txt = df_txt.dropna(subset=["timestamp"])
        df_txt["timestamp"] = pd.to_datetime(df_txt["timestamp"], errors="coerce")
        df_txt = df_txt.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        events_df = schema.standardize_columns(events_df)
        events_df = schema.apply_mapping_events(events_df)
        schema.validate_events(events_df)
        if "date" in events_df.columns:
            events_df["date"] = pd.to_datetime(events_df["date"], errors="coerce")
            events_df = events_df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

        # --- 3) Sélection des avions ---
        selected_tails = settings.get("selected_tail_numbers", [])
        if isinstance(selected_tails, str):
            selected_tails = [selected_tails]

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

        for tail in selected_tails:
            df_tail = df_txt[df_txt["tail_number"] == tail].copy().reset_index(drop=True)
            events_tail = events_df[events_df["tail_number"] == tail].copy().reset_index(drop=True)

            if df_tail.empty:
                logger.warning(f"No data for tail {tail}, skipping.")
                continue

            # --- 4) Filtrage passe-bas ---
            if "%ff_dev_total_(%)" in df_tail.columns:
                lowpass_config = settings.get("lowpass_filter", {})
                cutoff_period_weeks = lowpass_config.get("cutoff_period_weeks", 4)
                cutoff_period_sec = cutoff_period_weeks * 7 * 24 * 3600
                cutoff_freq = 1 / cutoff_period_sec
                order = lowpass_config.get("order", 5)

                df_tail = apply_lowpass_filter(
                    df_tail,
                    time_col="timestamp",
                    value_col="%ff_dev_total_(%)",
                    cutoff_freq_hz=cutoff_freq,
                    order=order
                )

            # --- 5) Sauvegarde CSV filtré par avion ---
            tail_csv_path = OUTPUTS_DIR / f"data_{tail}.csv"
            df_tail.to_csv(tail_csv_path, index=False)
            logger.info(f"Filtered data for tail {tail} saved: {tail_csv_path}")

            # --- 6) Génération graphique par avion ---
            plot_path = OUTPUTS_DIR / f"lowpass_filter_{tail}.png"
            plot_lowpass_filter_comparison(
                df_tail,
                time_col="timestamp",
                value_col="%ff_dev_total_(%)",
                filtered_col="%ff_dev_total_(%)_filtered",
                events_df=events_tail,
                event_date_col="date_of_event",
                output_path=plot_path
            )
            logger.info(f"Graph for tail {tail} saved: {plot_path}")

        # --- 7) Analyse de corrélation ---
        correlation(
            files=[
                str(OUTPUTS_DIR / f"data_{tail}.csv") for tail in selected_tails
            ],
            target="%ff_dev_total_(%)_filtered"
        )

        # --- 8) Reporting global ---
        reporter = Reporter(OUTPUTS_DIR)
        reporter.export_csv(df_txt, filename="data_processed.csv")
        logger.info("Global data_processed.csv saved.")

        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.exception("Pipeline failed with an unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()

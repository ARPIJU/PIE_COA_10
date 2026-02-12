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

        # 2.4) Segregate plane data and filter for FHMRB / all planes
        try:
            logger.info("Segregating flight data by tail number...")
            tail_numbers = settings["excel_sheets_priority"]
            segregate_plane_data(df_txt, tail_numbers, output_dir=OUTPUTS_DIR)
            logger.info("Plane data segregation completed")
            
            # Filter df_txt/events_df to only include selected tail numbers from settings
            selected_tails = settings.get("selected_tail_numbers", [sheet_used])
            # allow a single string in settings as well
            if isinstance(selected_tails, str):
                selected_tails = [selected_tails]

            df_txt = df_txt[df_txt["tail_number"].isin(selected_tails)].copy().reset_index(drop=True)
            logger.info(f"Filtered data for tails {selected_tails}: {df_txt.shape[0]} records remaining")

            events_df = events_df[events_df["tail_number"].isin(selected_tails)].copy().reset_index(drop=True)
            logger.info(f"Filtered events for tails {selected_tails}: {events_df.shape[0]} events remaining")

            if df_txt.empty:
                logger.error(f"No data found for aircraft tails {selected_tails}. Aborting.")
                return
            if events_df.empty:
                logger.error(f"No events found for aircraft tails {selected_tails}. Aborting.")
                return
        except Exception as e:
            logger.warning(f"Error during plane segregation or filtering: {e}")
            return

        # 2.5) Appliquer le filtre passe bas sur %ff_dev_total_(%)

        # Lire la configuration du filtre passe bas depuis settings
        lowpass_config = settings.get("lowpass_filter", {})
        display_graph_lowpassed_vs_original = lowpass_config.get("display_graph", False)
        if "%ff_dev_total_(%)" in df_txt.columns:
            try:
                
                # Appliquer le filtre avec la fréquence lue depuis settings
                lowpass_config = settings.get("lowpass_filter", {})
                cutoff_period_lowpass_sec = lowpass_config.get("cutoff_period_weeks", 4) * 7 * 24 * 3600  # Convertir semaines en secondes
                cutoff_frequency = 1 / cutoff_period_lowpass_sec
                filter_order = lowpass_config.get("order", 5)
                
                logger.info(f"Paramètres du filtre: cutoff_freq={cutoff_frequency:.2e} Hz (période ~{cutoff_period_lowpass_sec / (7*24*3600):.0f} semaines), order={filter_order}")
                
                df_txt = apply_lowpass_filter(
                    df_txt,
                    time_col="timestamp",
                    value_col="%ff_dev_total_(%)",
                    cutoff_freq_hz=cutoff_frequency,
                    order=filter_order
                )
                logger.info("Filtre passe bas appliqué sur %ff_dev_total_(%) avec succès")
                
                # Afficher le graphique de comparaison si demandé
                if display_graph_lowpassed_vs_original:
                    logger.info("Affichage du graphique de comparaison signal brut vs filtré")
                    plot_lowpass_filter_comparison(
                        df_txt,
                        time_col="timestamp",
                        value_col="%ff_dev_total_(%)",
                        filtered_col="%ff_dev_total_(%)_filtered",
                        events_df=events_df,
                        event_date_col="date_of_event"
                    )
            except Exception as e:
                logger.warning(f"Impossible d'appliquer le filtre passe bas: {e}")
        else:
            logger.warning("Colonne '%ff_dev_total_(%)' non trouvée pour appliquer le filtre")

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
        reporter.export_csv(df_txt, filename="data_processed.csv")
        
        # Exporter le graphique de comparaison filtre vs brut si demandé (sauvegarde uniquement, pas d'affichage)
        if display_graph_lowpassed_vs_original and "%ff_dev_total_(%)_filtered" in df_txt.columns:
            try:
                import matplotlib.pyplot as plt
                plot_path = OUTPUTS_DIR / "lowpass_filter_comparison.png"
                
                # Créer et sauvegarder le graphique sans affichage
                plt.figure(figsize=(14, 6))
                plt.plot(df_txt["timestamp"], df_txt["%ff_dev_total_(%)"], label='Signal brut', alpha=0.5, linewidth=0.8)
                plt.plot(df_txt["timestamp"], df_txt["%ff_dev_total_(%)_filtered"], label='Signal filtré', color='red', linewidth=1.5)
                plt.xlabel('Temps')
                plt.ylabel('% Déviation Débit Carburant')
                plt.title('Comparaison Signal Brut vs Signal Filtré (Passe Bas)')
                plt.legend()
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                logger.info(f"Graphique de comparaison sauvegardé: {plot_path}")
                plt.close()
            except Exception as e:
                logger.warning(f"Impossible de générer le graphique de comparaison: {e}")


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

"""
Le but de ce script est d’identifier la période de coupure du filtre passe-bas
qui maximise la précision du calcul de D(t), en minimisant l’intégrale de D_std(t).
"""

from pathlib import Path
import json
import logging
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from classes.utils.logging_conf import setup_logging
from classes.io.data_loader import load_events, load_txt_series
from classes.io.schemas import DataSchema
from classes.processing.cleaning import DataCleaner
from classes.domain.maintenance import MaintenanceCatalog
from classes.optimization.scheduler import MaintenanceScheduler
from classes.analysis.reporting import Reporter

from classes.processing.low_pass_filtering import apply_lowpass_filter
from classes.analysis.global_drift import GlobalDriftEstimator


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE = Path(__file__).resolve().parent.parent.parent
SETTINGS_PATH = BASE / "config" / "settings.json"
OUTPUTS_DIR = BASE / "outputs"

# Tailles de filtre à tester (périodes de coupure en semaines)
cutoff_periods = [1, 2, 3, 4, 5, 6, 7, 8]


# ============================================================================
# UTILITAIRES
# ============================================================================

# def integrate_D_std(D: pd.DataFrame) -> float:
#     """
#     Intègre D_std(t) par méthode des trapèzes.
#     Utilise numpy.trapz (compatible Python 3.14).
#     """
#     D_valid = D.dropna(subset=["D_std", "t_days"])

#     if len(D_valid) < 2:
#         return float("nan")

#     return np.trapz(
#         y=D_valid["D_std"].values,
#         x=D_valid["t_days"].values
#     )

def integrate_D_std(D: pd.DataFrame) -> float:
    """
    Intégration trapézoïdale manuelle compatible Python 3.14
    (sans numpy.trapz ni scipy).
    """
    D_valid = D.dropna(subset=["D_std", "t_days"])

    if len(D_valid) < 2:
        return float("nan")

    x = D_valid["t_days"].to_numpy()
    y = D_valid["D_std"].to_numpy()

    integral = 0.0
    for i in range(1, len(x)):
        dx = x[i] - x[i - 1]
        integral += 0.5 * (y[i] + y[i - 1]) * dx

    return float(integral)


# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def run_pipeline():

    # ----------------------------------------------------------------------
    # Chargement settings
    # ----------------------------------------------------------------------
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")

    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting cutoff frequency sensitivity analysis")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    reporter = Reporter(OUTPUTS_DIR)

    # ----------------------------------------------------------------------
    # Chargement des données
    # ----------------------------------------------------------------------
    data_dir = settings["paths"]["data_dir"]
    excel_file = BASE / data_dir / settings["paths"]["excel_file"]
    txt_file = BASE / data_dir / settings["paths"]["txt_file"]

    sheet_priority = [s for s in settings["excel_sheets_priority"] if s != "FHMRI"]

    events_df = load_events(
        str(excel_file),
        sheet_priority=sheet_priority,
        ignore_sheets=["FHMRI"]
    )

    df_txt = load_txt_series(
        str(txt_file),
        txt_read=settings["txt_read"],
        columns_mapping=settings["columns_mapping"]
    )

    if df_txt.empty or events_df.empty:
        logger.error("Data not loaded or empty. Aborting.")
        return

    # ----------------------------------------------------------------------
    # Nettoyage et standardisation
    # ----------------------------------------------------------------------
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
    df_txt["timestamp"] = pd.to_datetime(df_txt["timestamp"])
    df_txt = df_txt.sort_values("timestamp").reset_index(drop=True)

    events_df = schema.standardize_columns(events_df)
    events_df = schema.apply_mapping_events(events_df)
    schema.validate_events(events_df)

    events_df["date"] = pd.to_datetime(events_df["date"], errors="coerce")
    events_df = events_df.dropna(subset=["date"])
    events_df = events_df.sort_values("date").reset_index(drop=True)

    logger.info(
        "TXT records: %d | Event records: %d",
        df_txt.shape[0],
        events_df.shape[0]
    )

    # ----------------------------------------------------------------------
    # Analyse de sensibilité au filtrage
    # ----------------------------------------------------------------------
    lowpass_config = settings.get("lowpass_filter", {})
    filter_order = lowpass_config.get("order", 5)

    drift_results = []

    for cutoff_weeks in cutoff_periods:
        logger.info(f"Processing cutoff = {cutoff_weeks} weeks")

        df_filt = df_txt.copy()

        cutoff_period_sec = cutoff_weeks * 7 * 24 * 3600
        cutoff_freq = 1.0 / cutoff_period_sec

        df_filt = apply_lowpass_filter(
            df_filt,
            time_col="timestamp",
            value_col="%ff_dev_total_(%)",
            cutoff_freq_hz=cutoff_freq,
            order=filter_order
        )

        filtered_col = "%ff_dev_total_(%)_filtered"

        reporter.export_csv(
            df_filt[["timestamp", filtered_col]],
            filename=f"fuel_factor_filtered_{cutoff_weeks}w.csv"
        )

        estimator = GlobalDriftEstimator(
            df_txt=df_filt,
            events_df=events_df,
            time_col="timestamp",
            signal_col=filtered_col,
            maintenance_col="date",
            stabilization_days=10,
            time_step_days=1.0
        )

        D = estimator.compute_D()

        reporter.export_csv(
            D,
            filename=f"D_curve_{cutoff_weeks}w.csv"
        )

        J = integrate_D_std(D)

        drift_results.append({
            "cutoff_weeks": cutoff_weeks,
            "cutoff_days": cutoff_weeks * 7,
            "integral_D_std": J,
            "n_bins": len(D),
            "mean_n_samples": D["n_samples"].mean()
        })

    # ----------------------------------------------------------------------
    # Résumé global et tracé
    # ----------------------------------------------------------------------
    df_results = pd.DataFrame(drift_results)

    reporter.export_csv(
        df_results,
        filename="D_std_integral_vs_cutoff.csv"
    )

    plt.figure(figsize=(8, 5))
    plt.plot(
        df_results["cutoff_days"],
        df_results["integral_D_std"],
        marker="o",
        linewidth=2
    )
    plt.xlabel("Période de coupure du filtre (jours)")
    plt.ylabel("∫ D_std(t) dt")
    plt.title("Précision de D(t) en fonction de la fréquence de coupure")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    run_pipeline()

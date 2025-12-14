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
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting pipeline")

    loader = DataLoader(BASE, SETTINGS_PATH)
    df_txt = loader.load_boeing_txt()
    if df_txt is None or df_txt.empty:
        logger.error("Boeing_Perf_Data.txt not loaded or empty. Aborting.")
        return

    events_df, sheet_used = loader.load_first_available_events()
    logger.info("Events loaded from sheet: %s", sheet_used)

    schema = DataSchema(settings)
    df_txt = schema.standardize_columns(df_txt)
    df_txt = schema.apply_mapping_txt(df_txt)
    schema.validate_txt(df_txt)

    print("Colonnes après mapping:", df_txt.columns

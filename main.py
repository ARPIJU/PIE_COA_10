# main.py
from pathlib import Path
import json
import logging
import pandas as pd

from classes.utils.logging_conf import setup_logging
from classes.io.data_loader import DataLoader


BASE = Path(__file__).resolve().parent
SETTINGS_PATH = BASE / "config" / "settings.json"


def run_pipeline():
    # 0) Settings + logging
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        settings = json.load(f)

    setup_logging(settings.get("logging", {}).get("level", "INFO"))
    logger = logging.getLogger("main")
    logger.info("Starting pipeline")

    # 1) Load data with debug
    loader = DataLoader(BASE, SETTINGS_PATH)
    df_txt = loader.load_boeing_txt(debug=True)
    if df_txt is None or df_txt.empty:
        logger.error("Boeing_Perf_Data.txt not loaded or empty. Aborting.")
        return

    # Debug: afficher colonnes et premières lignes
    print("\n=== DEBUG FINAL ===")
    print("Colonnes après lecture:", df_txt.columns.tolist())
    print("\nPremières lignes du TXT (10x10):")
    print(df_txt.iloc[:10, :10])
    print("=== FIN DEBUG ===\n")

    # Stop here: on ne lance pas la suite du pipeline tant que le mapping n’est pas corrigé
    return


if __name__ == "__main__":
    run_pipeline()

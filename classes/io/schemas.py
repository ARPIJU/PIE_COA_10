import logging
import pandas as pd

logger = logging.getLogger(__name__)

class DataSchema:
    def __init__(self, settings: dict):
        self.settings = settings
        self.txt_map = settings["columns_mapping"]["txt"]
        self.events_map = settings["columns_mapping"]["excel_events"]

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.rename(columns=lambda c: c.strip().lower().replace(" ", "_"))
        return df

    def apply_mapping_txt(self, df: pd.DataFrame) -> pd.DataFrame:
        canon = {}
        for src, dst in self.txt_map.items():
            if src in df.columns:
                canon[src] = dst
        if canon:
            df = df.rename(columns=canon)
        return df

    def apply_mapping_events(self, df: pd.DataFrame) -> pd.DataFrame:
        canon = {}
        for src, dst in self.events_map.items():
            if src in df.columns:
                canon[src] = dst
        if canon:
            df = df.rename(columns=canon)
        return df

    def coerce_types(self, df: pd.DataFrame, date_cols=()) -> pd.DataFrame:
        for c in date_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        return df

    def validate_txt(self, df: pd.DataFrame) -> None:
        # Colonnes critiques seulement
        required = {"recorded_date", "fuel_flow"}
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.error("TXT missing critical columns: %s", missing)
            raise ValueError(f"TXT missing critical columns: {missing}")
        else:
            logger.info("TXT validation OK, colonnes critiques présentes.")

    def validate_events(self, df: pd.DataFrame) -> None:
        required = {"date", "event"}
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.error("Events missing critical columns: %s", missing)
            raise ValueError(f"Events missing critical columns: {missing}")
        else:
            logger.info("Events validation OK, colonnes critiques présentes.")

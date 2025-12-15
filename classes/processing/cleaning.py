import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DataCleaner:
    def fix_timestamps(self, df: pd.DataFrame, min_year=2000) -> pd.DataFrame:
        if "timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            years = df["timestamp"].dt.year
            df["is_year_plausible"] = years >= min_year
        return df

    def remove_duplicates(self, df: pd.DataFrame, keys=("tail_number","timestamp")) -> pd.DataFrame:
        for k in keys:
            if k not in df.columns:
                return df
        before = df.shape[0]
        df = df.drop_duplicates(subset=list(keys))
        logger.info("Removed %d duplicates", before - df.shape[0])
        return df

    def flag_quality(self, df: pd.DataFrame, metric_cols=("perf_factor","fuel_flow")) -> pd.DataFrame:
        for m in metric_cols:
            if m in df.columns:
                df[f"{m}_isna"] = df[m].isna()
        return df

    def build_timestamp(self, df: pd.DataFrame, date_col="recorded_date", time_col="time") -> pd.DataFrame:
        if date_col in df.columns and time_col in df.columns:
            try:
                df["timestamp"] = pd.to_datetime(
                    df[date_col].astype(str) + " " + df[time_col].astype(str),
                    errors="coerce",
                    dayfirst=True
                )
            except Exception:
                df["timestamp"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
        elif date_col in df.columns:
            df["timestamp"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)

        # ⚠️ Correction: ne pas dropper toutes les lignes ici
        # On garde les NaT pour analyse ultérieure
        logger.info("build_timestamp: %d timestamps valides / %d lignes", df["timestamp"].notna().sum(), df.shape[0])
        return df

    def clean_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        if "perf_factor" in df.columns:
            df["perf_factor"] = (
                df["perf_factor"].astype(str)
                .str.replace("..", ".", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df["perf_factor"] = pd.to_numeric(df["perf_factor"], errors="coerce")

        if "fuel_flow" in df.columns:
            df["fuel_flow"] = (
                df["fuel_flow"].astype(str)
                .str.replace("..", ".", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df["fuel_flow"] = pd.to_numeric(df["fuel_flow"], errors="coerce")

        # ⚠️ Correction: drop uniquement si fuel_flow est NaN
        before = df.shape[0]
        df = df.dropna(subset=["fuel_flow"])
        logger.info("clean_numeric_columns: %d lignes supprimées (fuel_flow NaN)", before - df.shape[0])
        return df

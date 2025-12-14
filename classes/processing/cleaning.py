import pandas as pd

class DataCleaner:
    def fix_timestamps(self, df: pd.DataFrame, min_year=2020) -> pd.DataFrame:
        if "timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            years = df["timestamp"].dt.year
            df["is_year_plausible"] = years >= min_year
        return df

    def remove_duplicates(self, df: pd.DataFrame, keys=("tail_number","timestamp")) -> pd.DataFrame:
        for k in keys:
            if k not in df.columns:
                return df
        return df.drop_duplicates(subset=list(keys))

    def flag_quality(self, df: pd.DataFrame, metric_cols=("perf_factor","fuel_flow")) -> pd.DataFrame:
        for m in metric_cols:
            if m in df.columns:
                df[f"{m}_isna"] = df[m].isna()
        return df

    def build_timestamp(self, df: pd.DataFrame, date_col="date", time_col="time") -> pd.DataFrame:
        if date_col in df.columns and time_col in df.columns:
            df["timestamp"] = pd.to_datetime(
                df[date_col].astype(str) + " " + df[time_col].astype(str),
                errors="coerce"
            )
        elif date_col in df.columns:
            df["timestamp"] = pd.to_datetime(df[date_col], errors="coerce")
        return df

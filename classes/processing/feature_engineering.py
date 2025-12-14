import pandas as pd

class FeatureEngineer:
    def rolling_baseline(self, df: pd.DataFrame, key=("tail_number",), metric="perf_factor", window=30) -> pd.DataFrame:
        needed = list(key) + ["timestamp", metric]
        if not all(c in df.columns for c in needed):
            return df
        df = df.sort_values(list(key)+["timestamp"])
        df[f"{metric}_baseline_{window}d"] = (
            df.groupby(list(key))[metric].transform(lambda s: s.rolling(window, min_periods=5).mean())
        )
        return df

    def aggregate_by_airac(self, df: pd.DataFrame) -> pd.DataFrame:
        # If 'airac' not available, approximate monthly period as placeholder
        if "timestamp" not in df.columns or "tail_number" not in df.columns:
            return df
        df["airac"] = df["timestamp"].dt.to_period("M").astype(str)
        agg = df.groupby(["tail_number","airac"]).agg(
            perf_factor=("perf_factor","mean"),
            fuel_flow=("fuel_flow","mean")
        ).reset_index()
        return agg


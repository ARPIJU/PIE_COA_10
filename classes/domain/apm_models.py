import pandas as pd

class APMModels:
    def __init__(self, settings: dict):
        self.settings = settings
        self.basic_pf = settings["apm"]["basic_perf_factor"]
        self.slope = settings["apm"]["perf_to_fuel_factor_linear"]["slope"]
        self.intercept = settings["apm"]["perf_to_fuel_factor_linear"]["intercept"]

    def apply_constants(self, df: pd.DataFrame) -> pd.DataFrame:
        df["basic_perf_factor"] = self.basic_pf
        return df

    def perf_to_fuel_factor(self, df: pd.DataFrame, perf_col="perf_factor", out_col="fuel_factor") -> pd.DataFrame:
        if perf_col in df.columns:
            df[out_col] = df[perf_col] * self.slope + self.intercept
        return df

    def expected_fuel(self, df: pd.DataFrame, base_fuel_col="fuel_flow", factor_col="fuel_factor", out_col="fuel_expected_corr") -> pd.DataFrame:
        if base_fuel_col in df.columns and factor_col in df.columns:
            df[out_col] = df[base_fuel_col] * (1.0 + df[factor_col])
        return df


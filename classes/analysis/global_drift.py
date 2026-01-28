import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple


class GlobalDriftEstimator:
    """
    Calcule un D(t) global à partir d'un signal filtré et des dates de maintenance,
    par recentrage post-maintenance.
    """

    def __init__(
        self,
        df_txt: pd.DataFrame,
        events_df: pd.DataFrame,
        time_col: str = "timestamp",
        signal_col: str = "%ff_dev_total_(%)_filtered",
        maintenance_col: str = "date",
        stabilization_days: int = 10,
        time_step_days: float = 1.0,
    ):
        self.df_txt = df_txt.copy()
        self.events_df = events_df.copy()
        self.time_col = time_col
        self.signal_col = signal_col
        self.maintenance_col = maintenance_col
        self.stabilization_days = stabilization_days
        self.time_step_days = time_step_days

        self._prepare()

    def _prepare(self):
        # Sécurité et tri
        self.df_txt[self.time_col] = pd.to_datetime(self.df_txt[self.time_col])
        self.events_df[self.maintenance_col] = pd.to_datetime(self.events_df[self.maintenance_col])

        self.df_txt = self.df_txt.sort_values(self.time_col).reset_index(drop=True)
        self.events_df = self.events_df.sort_values(self.maintenance_col).reset_index(drop=True)

    def compute_D(self) -> pd.DataFrame:
        """
        Retourne un DataFrame avec :
          - t_days
          - D_mean
          - D_std
          - n_samples
        """

        contributions = []

        maint_dates = self.events_df[self.maintenance_col].values

        for i in range(len(maint_dates) - 1):
            t0 = maint_dates[i]
            t1 = maint_dates[i + 1]

            start = t0 + pd.Timedelta(days=self.stabilization_days)

            seg = self.df_txt[
                (self.df_txt[self.time_col] >= start) &
                (self.df_txt[self.time_col] < t1)
            ]

            if seg.empty:
                continue

            # Référence locale
            ref_value = seg.iloc[0][self.signal_col]

            t_days = (
                (seg[self.time_col] - start)
                .dt.total_seconds()
                .values / (24 * 3600)
            )

            delta_ff = seg[self.signal_col].values - ref_value

            contributions.append(
                pd.DataFrame({
                    "t_days": t_days,
                    "delta_ff": delta_ff
                })
            )

        if not contributions:
            return pd.DataFrame(columns=["t_days", "D_mean", "D_std", "n_samples"])

        all_contrib = pd.concat(contributions, ignore_index=True)

        # Binning temporel
        all_contrib["t_bin"] = (
            np.floor(all_contrib["t_days"] / self.time_step_days)
            * self.time_step_days
        )

        D = (
            all_contrib
            .groupby("t_bin")
            .agg(
                D_mean=("delta_ff", "mean"),
                D_std=("delta_ff", "std"),
                n_samples=("delta_ff", "size")
            )
            .reset_index()
            .rename(columns={"t_bin": "t_days"})
        )

        # Forcer D(0) = 0
        if 0.0 not in D["t_days"].values:
            D = pd.concat([
                pd.DataFrame({
                    "t_days": [0.0],
                    "D_mean": [0.0],
                    "D_std": [0.0],
                    "n_samples": [len(maint_dates) - 1]
                }),
                D
            ], ignore_index=True)

        D = D.sort_values("t_days").reset_index(drop=True)
        D.loc[D["t_days"] == 0.0, ["D_mean", "D_std"]] = 0.0

        return D

    @staticmethod
    def plot_D(D: pd.DataFrame, with_confidence: bool = True):
        """
        Trace la courbe D(t)
        """
        plt.figure(figsize=(10, 5))
        plt.plot(D["t_days"], D["D_mean"], label="D(t)", linewidth=2)

        if with_confidence and "D_std" in D.columns:
            plt.fill_between(
                D["t_days"],
                D["D_mean"] - D["D_std"],
                D["D_mean"] + D["D_std"],
                alpha=0.3,
                label="±1σ"
            )

        plt.axhline(0.0, color="black", linewidth=0.8, linestyle="--")
        plt.xlabel("Temps depuis maintenance (jours)")
        plt.ylabel("Δ Fuel Factor (%)")
        plt.title("Dérive globale après maintenance — D(t)")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import UnivariateSpline
from typing import Optional


class GlobalDriftSplineEstimator:
    """
    Calcule D(t) global sur une période donnée à partir d'un signal filtré
    et des dates de maintenance, avec spline pour D_mean et sigma cumulatif.
    Pour les jours sans données, σ croît artificiellement.
    """

    def __init__(
        self,
        df_txt: pd.DataFrame,
        events_df: pd.DataFrame,
        time_col: str = "timestamp",
        signal_col: str = "%ff_dev_total_(%)_filtered",
        maintenance_col: str = "date",
        stabilization_days: int = 10,
        horizon_days: int = 40,
        spline_smoothing: Optional[float] = None,
    ):
        self.df_txt = df_txt.copy()
        self.events_df = events_df.copy()
        self.time_col = time_col
        self.signal_col = signal_col
        self.maintenance_col = maintenance_col
        self.stabilization_days = stabilization_days
        self.horizon_days = horizon_days
        self.spline_smoothing = spline_smoothing

        self._prepare()

    def _prepare(self):
        self.df_txt[self.time_col] = pd.to_datetime(self.df_txt[self.time_col])
        self.events_df[self.maintenance_col] = pd.to_datetime(self.events_df[self.maintenance_col])
        self.df_txt = self.df_txt.sort_values(self.time_col).reset_index(drop=True)
        self.events_df = self.events_df.sort_values(self.maintenance_col).reset_index(drop=True)

    def compute_D_spline(self) -> pd.DataFrame:
        contributions = []
        maint_dates = self.events_df[self.maintenance_col].values

        # Parcours de tous les intervalles entre maintenances
        for i in range(len(maint_dates) - 1):
            t0 = maint_dates[i]
            t1 = maint_dates[i + 1]

            start = t0 + pd.Timedelta(days=self.stabilization_days)
            end = min(t1, start + pd.Timedelta(days=self.horizon_days))

            seg = self.df_txt[
                (self.df_txt[self.time_col] >= start) &
                (self.df_txt[self.time_col] < end)
            ]

            if seg.empty:
                continue

            # Delta cumulatif depuis le début de la période post-maintenance
            ref_value = seg.iloc[0][self.signal_col]
            t_days = (seg[self.time_col] - start).dt.total_seconds().values / (24*3600)
            delta_ff_cumul = seg[self.signal_col].values - ref_value

            contributions.append(pd.DataFrame({
                "t_days": t_days,
                "delta_ff_cumul": delta_ff_cumul
            }))

        if not contributions:
            return pd.DataFrame({
                "t_days": np.arange(0, self.horizon_days + 1),
                "D_mean_spline": np.zeros(self.horizon_days + 1),
                "D_std_spline": np.zeros(self.horizon_days + 1)
            })

        # Concaténer toutes les contributions de toutes les maintenances
        all_contrib = pd.concat(contributions, ignore_index=True)
        all_contrib["t_bin"] = np.floor(all_contrib["t_days"])

        # Calcul de la moyenne et de l'écart-type cumulatif par jour
        daily_stats = all_contrib.groupby("t_bin")["delta_ff_cumul"].agg(["mean", "std"]).reset_index()
        daily_stats["std"] = daily_stats["std"].fillna(0)

        # spline pour la moyenne
        mean_spline = UnivariateSpline(daily_stats["t_bin"], daily_stats["mean"], s=self.spline_smoothing)
        t_eval = np.arange(0, self.horizon_days + 1)
        D_mean_spline = mean_spline(t_eval)

        # interpolation linéaire pour σ jusqu'au dernier jour observé
        D_std_spline = np.interp(t_eval, daily_stats["t_bin"], daily_stats["std"])

        # Croissance artificielle pour les jours sans observation
        t_max_real = daily_stats["t_bin"].max()
        last_std = daily_stats["std"].iloc[-1]

        for i, t in enumerate(t_eval):
            if t > t_max_real:
                # σ croît proportionnellement à sqrt(t / t_max_real)
                D_std_spline[i] = last_std * np.sqrt(t / t_max_real)

        # Forcer D(0)
        D_mean_spline[0] = 0
        D_std_spline[0] = daily_stats["std"].iloc[0] if not daily_stats.empty else 0

        return pd.DataFrame({
            "t_days": t_eval,
            "D_mean_spline": D_mean_spline,
            "D_std_spline": D_std_spline
        })

    @staticmethod
    def plot_D_spline(D: pd.DataFrame):
        """
        Trace D(t) spline avec bande ±1σ cumulatif + croissance artificielle
        """
        plt.figure(figsize=(10, 5))
        plt.plot(D["t_days"], D["D_mean_spline"], label="D(t) spline", linewidth=2)
        plt.fill_between(
            D["t_days"],
            D["D_mean_spline"] - D["D_std_spline"],
            D["D_mean_spline"] + D["D_std_spline"],
            color="orange",
            alpha=0.3,
            label="±1σ cumulatif"
        )
        plt.axhline(0, color="black", linestyle="--", linewidth=0.8)
        plt.xlabel("Temps depuis maintenance (jours)")
        plt.ylabel("Δ Fuel Factor (%)")
        plt.title("Dérive globale après maintenance — D(t) spline ±σ cumulatif")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.show()

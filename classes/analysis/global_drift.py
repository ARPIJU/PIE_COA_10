from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


class GlobalDriftEstimator:
    """
    Calcule un D(t) global en utilisant les données filtrées
    sauvegardées dans outputs/data_<TAIL>.csv.

    Agrège tous les intervalles inter-maintenance
    de tous les avions sélectionnés.
    """

    def __init__(
        self,
        settings_path: str,
        outputs_dir: str,
        signal_col: str = "%ff_dev_total_(%)_filtered",
        time_col: str = "timestamp",
        stabilization_days: int = 10,
        time_step_days: float = 1.0,
    ):
        self.settings_path = Path(settings_path)
        self.outputs_dir = Path(outputs_dir)

        self.signal_col = signal_col
        self.time_col = time_col
        self.stabilization_days = stabilization_days
        self.time_step_days = time_step_days

        self.selected_tails = self._load_selected_tails()
        self.df_txt = self._load_all_tails()
        self.events_df = self._load_events()

    # --------------------------------------------------
    # LOAD SETTINGS
    # --------------------------------------------------

    def _load_selected_tails(self):

        if not self.settings_path.exists():
            raise FileNotFoundError(self.settings_path)

        with open(self.settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        tails = settings.get("selected_tail_numbers", [])

        if isinstance(tails, str):
            tails = [tails]

        if not tails:
            raise ValueError("selected_tail_numbers est vide dans settings.json")

        return tails

    # --------------------------------------------------
    # LOAD FILTERED DATA (CSV PER AIRCRAFT)
    # --------------------------------------------------

    def _load_all_tails(self):

        frames = []

        for tail in self.selected_tails:
            path = self.outputs_dir / f"data_{tail}.csv"

            if not path.exists():
                print(f"⚠ CSV introuvable pour {tail}")
                continue

            df = pd.read_csv(path)

            if self.time_col not in df.columns:
                print(f"⚠ timestamp absent pour {tail}")
                continue

            if self.signal_col not in df.columns:
                print(f"⚠ signal filtré absent pour {tail}")
                continue

            df[self.time_col] = pd.to_datetime(df[self.time_col])
            df["tail_number"] = tail

            frames.append(df)

        if not frames:
            raise ValueError("Aucune donnée filtrée chargée depuis outputs/")

        df_all = pd.concat(frames, ignore_index=True)
        df_all = df_all.sort_values(self.time_col).reset_index(drop=True)

        print(f"✔ {len(df_all)} points chargés pour {len(frames)} avions")

        return df_all

    # --------------------------------------------------
    # LOAD MAINTENANCE EVENTS
    # --------------------------------------------------

    def _load_events(self):

        events_path = self.outputs_dir / "maintenance_impacts_modeled.csv"

        if not events_path.exists():
            raise FileNotFoundError(events_path)

        events_df = pd.read_csv(events_path)

        # compatibilité colonne date
        if "event_date" in events_df.columns:
            events_df["date"] = pd.to_datetime(events_df["event_date"])
        elif "date" in events_df.columns:
            events_df["date"] = pd.to_datetime(events_df["date"])
        else:
            raise ValueError(
                "maintenance_impacts_modeled.csv doit contenir 'event_date' ou 'date'"
            )

        if "tail_number" not in events_df.columns:
            raise ValueError("Colonne 'tail_number' absente dans maintenance_impacts_modeled.csv")

        return events_df.sort_values("date").reset_index(drop=True)

    # --------------------------------------------------
    # COMPUTE GLOBAL D(t)
    # --------------------------------------------------

    def compute_D(self):

        contributions = []
        total_intervals = 0

        for tail in self.selected_tails:

            df_tail = self.df_txt[self.df_txt["tail_number"] == tail]
            events_tail = self.events_df[
                self.events_df["tail_number"] == tail
            ].sort_values("date")

            maint_dates = events_tail["date"].values

            if len(maint_dates) < 2:
                continue

            for i in range(len(maint_dates) - 1):

                t0 = maint_dates[i]
                t1 = maint_dates[i + 1]

                start = t0 + pd.Timedelta(days=self.stabilization_days)

                seg = df_tail[
                    (df_tail[self.time_col] >= start)
                    & (df_tail[self.time_col] < t1)
                ]

                if seg.empty:
                    continue

                ref_value = seg.iloc[0][self.signal_col]

                t_days = (
                    (seg[self.time_col] - start)
                    .dt.total_seconds()
                    / 86400.0
                )

                delta = seg[self.signal_col] - ref_value

                contributions.append(
                    pd.DataFrame(
                        {
                            "t_days": t_days,
                            "delta_ff": delta,
                        }
                    )
                )

                total_intervals += 1

        if not contributions:
            print("⚠ Aucun intervalle exploitable")
            return pd.DataFrame()

        print(f"✔ {total_intervals} intervalles inter-maintenance utilisés")

        all_data = pd.concat(contributions, ignore_index=True)

        # binning temporel
        all_data["t_bin"] = (
            np.floor(all_data["t_days"] / self.time_step_days)
            * self.time_step_days
        )

        D = (
            all_data.groupby("t_bin")
            .agg(
                D_mean=("delta_ff", "mean"),
                D_std=("delta_ff", "std"),
                n_samples=("delta_ff", "size"),
            )
            .reset_index()
            .rename(columns={"t_bin": "t_days"})
            .sort_values("t_days")
        )

        # forcer D(0) = 0
        if 0.0 not in D["t_days"].values:
            D = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "t_days": [0.0],
                            "D_mean": [0.0],
                            "D_std": [0.0],
                            "n_samples": [total_intervals],
                        }
                    ),
                    D,
                ],
                ignore_index=True,
            )

        D.loc[D["t_days"] == 0.0, ["D_mean", "D_std"]] = 0.0

        return D.sort_values("t_days").reset_index(drop=True)

    # --------------------------------------------------
    # PLOT
    # --------------------------------------------------

    @staticmethod
    def plot_D(D: pd.DataFrame):

        plt.figure(figsize=(10, 5))
        plt.plot(D["t_days"], D["D_mean"], linewidth=2)

        if "D_std" in D.columns:
            plt.fill_between(
                D["t_days"],
                D["D_mean"] - D["D_std"],
                D["D_mean"] + D["D_std"],
                alpha=0.3,
            )

        plt.axhline(0, linestyle="--")
        plt.xlabel("jours depuis maintenance")
        plt.ylabel("Δ FF (%)")
        plt.title("Dérive globale D(t)")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()

    # --------------------------------------------------
    # PLOT WITH SAMPLE COUNT
    # --------------------------------------------------

    @staticmethod
    def plot_D_with_samples(D: pd.DataFrame, with_confidence: bool = True):

        if D.empty:
            print("⚠ D(t) vide — rien à tracer")
            return

        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=(10, 7),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]}
        )

        # ---- Courbe principale ----
        ax1.plot(D["t_days"], D["D_mean"], linewidth=2, label="D(t)")

        if with_confidence and "D_std" in D.columns:
            ax1.fill_between(
                D["t_days"],
                D["D_mean"] - D["D_std"],
                D["D_mean"] + D["D_std"],
                alpha=0.3,
                label="±1σ"
            )

        ax1.axhline(0, linestyle="--")
        ax1.set_ylabel("Δ FF (%)")
        ax1.set_title("Dérive globale D(t)")
        ax1.grid(alpha=0.3)
        ax1.legend()

        # ---- Nombre d'échantillons ----
        if "n_samples" in D.columns:
            ax2.step(
                D["t_days"],
                D["n_samples"],
                where="post",
                linewidth=2
            )
            ax2.set_ylabel("n samples")
            ax2.grid(alpha=0.3)

        ax2.set_xlabel("jours depuis maintenance")

        plt.tight_layout()
        plt.show()

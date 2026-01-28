import pandas as pd

from classes.analysis.global_drift import GlobalDriftEstimator
# ← adapte le chemin si besoin selon ton arborescence


def test_global_D(df_txt: pd.DataFrame, events_df: pd.DataFrame):
    """
    Test complet du calcul et du tracé de D(t)
    """

    # Paramètres
    SIGNAL_COL = "%ff_dev_total_(%)_filtered"
    TIME_COL = "timestamp"
    MAINT_COL = "date"

    STABILIZATION_DAYS = 10
    TIME_STEP_DAYS = 1.0  # bin journalier

    # Sécurité minimale
    required_cols_txt = {TIME_COL, SIGNAL_COL}
    required_cols_evt = {MAINT_COL}

    if not required_cols_txt.issubset(df_txt.columns):
        raise ValueError(f"Colonnes manquantes dans df_txt: {required_cols_txt - set(df_txt.columns)}")

    if not required_cols_evt.issubset(events_df.columns):
        raise ValueError(f"Colonnes manquantes dans events_df: {required_cols_evt - set(events_df.columns)}")

    print("▶ Initialisation du GlobalDriftEstimator")
    estimator = GlobalDriftEstimator(
        df_txt=df_txt,
        events_df=events_df,
        time_col=TIME_COL,
        signal_col=SIGNAL_COL,
        maintenance_col=MAINT_COL,
        stabilization_days=STABILIZATION_DAYS,
        time_step_days=TIME_STEP_DAYS,
    )

    print("▶ Calcul de D(t)")
    D = estimator.compute_D()

    if D.empty:
        print("⚠ D(t) vide — pas assez de données exploitables")
        return

    print("\n▶ Aperçu de D(t):")
    print(D.head(10))
    print("\n▶ Statistiques:")
    print(D.describe())

    # Vérification explicite de D(0) = 0
    D0 = D[D["t_days"] == 0.0]
    if not D0.empty:
        assert abs(D0.iloc[0]["D_mean"]) < 1e-12, "D(0) ≠ 0 !"
        print("✔ D(0) = 0 vérifié")
    else:
        print("⚠ D(0) non présent dans la table")

    print("▶ Tracé de D(t)")
    estimator.plot_D(D, with_confidence=True)


# ------------------------------------------------------------------
# Exemple d'utilisation dans ton pipeline ou un notebook
# ------------------------------------------------------------------

if __name__ == "__main__":

    # Exemple minimal : chargement depuis les exports du pipeline
    # (optionnel — adapte si tu préfères appeler directement run_pipeline)

    df_txt = pd.read_csv(
        "outputs/data_processed.csv",
        parse_dates=["timestamp"]
    )

    events_df = pd.read_csv(
        "outputs/maintenance_impacts_modeled.csv",
        parse_dates=["event_date"]
    ).rename(columns={"event_date": "date"})

    test_global_D(df_txt, events_df)

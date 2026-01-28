import pandas as pd
from classes.analysis.global_drift_extrapolated import GlobalDriftSplineEstimator
# ← adapte le chemin selon ton arborescence

def test_global_D_spline_croissance_sigma(df_txt: pd.DataFrame, events_df: pd.DataFrame):
    """
    Test complet du calcul et du tracé de D(t) spline sur 40 jours,
    avec sigma cumulatif et croissance artificielle pour les jours "loin".
    """

    # Paramètres
    SIGNAL_COL = "%ff_dev_total_(%)_filtered"
    TIME_COL = "timestamp"
    MAINT_COL = "date"

    STABILIZATION_DAYS = 15
    HORIZON_DAYS = 40
    SPLINE_SMOOTHING = None  # None = spline exacte, float >0 = lissage

    # Vérification des colonnes obligatoires
    required_cols_txt = {TIME_COL, SIGNAL_COL}
    required_cols_evt = {MAINT_COL}

    if not required_cols_txt.issubset(df_txt.columns):
        raise ValueError(f"Colonnes manquantes dans df_txt: {required_cols_txt - set(df_txt.columns)}")

    if not required_cols_evt.issubset(events_df.columns):
        raise ValueError(f"Colonnes manquantes dans events_df: {required_cols_evt - set(events_df.columns)}")

    print("▶ Initialisation du GlobalDriftSplineEstimator")
    estimator = GlobalDriftSplineEstimator(
        df_txt=df_txt,
        events_df=events_df,
        time_col=TIME_COL,
        signal_col=SIGNAL_COL,
        maintenance_col=MAINT_COL,
        stabilization_days=STABILIZATION_DAYS,
        horizon_days=HORIZON_DAYS,
        spline_smoothing=SPLINE_SMOOTHING,
    )

    print("▶ Calcul de D(t) spline avec σ cumulatif et croissance artificielle")
    D_spline = estimator.compute_D_spline()

    if D_spline.empty:
        print("⚠ D(t) spline vide — pas assez de données exploitables")
        return

    print("\n▶ Aperçu de D(t) spline:")
    print(D_spline.head(10))
    print("\n▶ Statistiques:")
    print(D_spline.describe())

    # Vérification D(0) ≈ 0
    D0 = D_spline[D_spline["t_days"] == 0]
    if not D0.empty:
        if abs(D0.iloc[0]["D_mean_spline"]) < 1e-12:
            print("✔ D(0) spline ≈ 0 vérifié")
        else:
            print(f"⚠ D(0) spline = {D0.iloc[0]['D_mean_spline']} ≠ 0")
    else:
        print("⚠ D(0) spline non présent dans la table")

    print("▶ Tracé de D(t) spline avec bande ±σ cumulatif et croissance artificielle")
    estimator.plot_D_spline(D_spline)


# ------------------------------------------------------------------
# Exemple d'utilisation
# ------------------------------------------------------------------

if __name__ == "__main__":

    # Chargement depuis exports du pipeline (ou adaptation)
    df_txt = pd.read_csv(
        "outputs/data_processed.csv",
        parse_dates=["timestamp"]
    )

    events_df = pd.read_csv(
        "outputs/maintenance_impacts_modeled.csv",
        parse_dates=["event_date"]
    ).rename(columns={"event_date": "date"})

    test_global_D_spline_croissance_sigma(df_txt, events_df)

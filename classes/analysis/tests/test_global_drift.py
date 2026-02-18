from pathlib import Path
import pandas as pd

from classes.analysis.global_drift import GlobalDriftEstimator


def test_global_D():
    """
    Test complet du calcul du D(t) global à partir
    des CSV filtrés par avion.
    """

    print("▶ Initialisation GlobalDriftEstimator")

    estimator = GlobalDriftEstimator(
        settings_path="config/settings.json",
        outputs_dir="outputs",
        stabilization_days=10,
        time_step_days=1.0,
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

    # ----------------------------
    # Vérification D(0) = 0
    # ----------------------------
    D0 = D[D["t_days"] == 0.0]

    if not D0.empty:
        assert abs(D0.iloc[0]["D_mean"]) < 1e-12, "D(0) ≠ 0 !"
        print("✔ D(0) = 0 vérifié")
    else:
        print("⚠ D(0) non présent")

    # ----------------------------
    # Vérifications statistiques
    # ----------------------------
    assert (D["n_samples"] > 0).all(), "Présence de bins sans échantillons"
    assert D["t_days"].is_monotonic_increasing, "t_days non trié"

    print("\n✔ Structure de D(t) valide")

    # ----------------------------
    # Tracé
    # ----------------------------
    print("▶ Tracé de D(t)")
    estimator.plot_D_with_samples(D, with_confidence=True)

    # ----------------------------
    # Sauvegarde figure
    # ----------------------------
    output_path = Path("outputs") / "global_drift_D.png"
    estimator.plot_D(D)
    print(f"✔ Figure sauvegardée : {output_path}")


# ------------------------------------------------------------------
# Lancement direct
# ------------------------------------------------------------------

if __name__ == "__main__":
    test_global_D()

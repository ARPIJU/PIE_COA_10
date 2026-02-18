import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def correlation(files, target):
    # -----------------------------
    # Fonction de nettoyage
    # -----------------------------


    # -----------------------------
    # Préparation de la figure
    # -----------------------------
    fig, axes = plt.subplots(1, 3, figsize=(26, 10))

    # -----------------------------
    # Boucle sur les fichiers
    # -----------------------------
    for i, file in enumerate(files):

        # Charger
        df = pd.read_csv(file)

        # Nettoyer la colonne cible
        df = clean_target_column(df, target)

        # Garder uniquement les colonnes numériques
        df_num = df.select_dtypes(include=["float64", "int64"])

        # Vérifier que la colonne existe
        if target not in df_num.columns:
            raise ValueError(f"La colonne {target} n'existe pas dans {file}")

        # Corrélation basique (Pearson par défaut)
        corr = df_num.corr()[target].sort_values(ascending=False)

        # Plot
        sns.barplot(
            x=corr.values,
            y=corr.index,
            ax=axes[i]
        )
        axes[i].set_title(f"Corrélations — {file.split('/')[-1]}")
        axes[i].set_xlabel("Corrélation")
        axes[i].set_ylabel("Variables")

    plt.tight_layout()
    plt.show()

def clean_target_column(df, col):
    df[col] = (
        df[col]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
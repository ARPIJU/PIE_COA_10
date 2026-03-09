import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import re


def _safe_filename(text: str) -> str:
    """Convertit une chaine en nom de fichier compatible."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")
    return cleaned or "target"


def correlation(files, target, output_path=None, show_plot=True):
    if not files:
        raise ValueError("La liste des fichiers est vide.")

    n_files = len(files)
    n_cols = min(3, n_files)
    n_rows = (n_files + n_cols - 1) // n_cols

    # Premiere passe: calcule les correlations pour construire un ordre global.
    corr_by_file = []
    for file in files:
        df = pd.read_csv(file)
        df = clean_target_column(df, target)
        df_num = df.select_dtypes(include=["float64", "int64"])

        if target not in df_num.columns:
            raise ValueError(f"La colonne {target} n'existe pas dans {file}")

        df_num = df_num.loc[:, df_num.nunique(dropna=True) > 1]
        if target not in df_num.columns:
            raise ValueError(
                f"La colonne {target} est constante ou vide dans {file}"
            )

        corr = (
            df_num.corr(numeric_only=True)[target]
            .dropna()
            .drop(labels=[target], errors="ignore")
        )
        corr_by_file.append(corr)

    all_corr = pd.concat(corr_by_file, axis=1)
    global_order = (
        all_corr.abs().mean(axis=1).sort_values(ascending=False).index.tolist()
    )

    # Context plus compact pour faire tenir les textes a l'ecran.
    sns.set_theme(style="whitegrid", context="notebook")
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(8 * n_cols, 4.8 * n_rows),
        constrained_layout=True
    )

    if not isinstance(axes, (list, tuple)):
        axes = [axes] if n_files == 1 else axes.flatten()
    else:
        axes = list(axes)

    if hasattr(axes, "flatten"):
        axes = axes.flatten()

    plot_order = list(range(n_files))
    if n_files >= 3:
        plot_order[1], plot_order[2] = plot_order[2], plot_order[1]

    for i, file_idx in enumerate(plot_order):
        file = files[file_idx]
        corr = corr_by_file[file_idx].reindex(global_order).dropna()

        ax = axes[i]

        if corr.empty:
            ax.text(
                0.5,
                0.5,
                "Aucune correlation exploitable",
                ha="center",
                va="center",
                fontsize=9
            )
            ax.set_axis_off()
            continue

        palette = ["#c62828" if val < 0 else "#2e7d32" for val in corr.values]

        sns.barplot(
            x=corr.values,
            y=corr.index,
            ax=ax,
            orient="h",
            palette=palette
        )

        for y, val in enumerate(corr.values):
            x_offset = 0.015 if val >= 0 else -0.015
            ha = "left" if val >= 0 else "right"
            ax.text(
                val + x_offset,
                y,
                f"{val:.2f}",
                va="center",
                ha=ha,
                fontsize=8,
                color="#222222"
            )


        max_abs = max(abs(corr.min()), abs(corr.max()), 0.1)
        x_limit = min(1.05, max_abs + 0.12)
        ax.set_xlim(-x_limit, x_limit)
        ax.axvline(0, color="#444444", linewidth=1.0, linestyle="--")

        title_file = Path(file).name
        ax.set_title(f"Correlations avec {target}\n{title_file}", fontsize=10)
        ax.set_xlabel("Coefficient de correlation (Pearson)", fontsize=9)
        ax.set_ylabel("Variables", fontsize=9)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(axis="x", linestyle=":", alpha=0.5)
        sns.despine(ax=ax, left=False, bottom=False)

    for j in range(n_files, len(axes)):
        axes[j].set_axis_off()

    if output_path is None:
        outputs_dir = Path(__file__).resolve().parents[2] / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        output_path = outputs_dir / f"correlation_{_safe_filename(target)}.png"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_path, dpi=300, bbox_inches="tight")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


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
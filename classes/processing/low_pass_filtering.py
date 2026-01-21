"""
Module for low-pass filtering operations on time series data.

Provides Butterworth low-pass filtering and visualization functions
to smooth noisy signals and extract trends.
"""

import logging
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import signal
import matplotlib.pyplot as plt


def generate_filter_comparison_plots(df, time_col="timestamp", value_col="%ff_dev_total_(%)", 
                                    output_dir=None):
    """
    Génère des graphiques de comparaison pour différentes fréquences de coupure
    permettant de choisir la plus adaptée.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame avec les données
    time_col : str
        Colonne timestamp
    value_col : str
        Colonne à filtrer
    output_dir : str or Path
        Répertoire de sortie pour les graphiques
    """
    df_work = df[[time_col, value_col]].copy()
    
    # Convertir timestamp et valeur en types appropriés AVANT de supprimer les NaN
    df_work[time_col] = pd.to_datetime(df_work[time_col], errors='coerce')
    df_work[value_col] = pd.to_numeric(df_work[value_col], errors='coerce')
    
    # Maintenant supprimer les NaN
    df_work = df_work.dropna()
    
    if len(df_work) < 100:
        logger = logging.getLogger(__name__)
        logger.warning("Pas assez de données pour générer les graphiques de comparaison")
        return
    
    values = df_work[value_col].values
    timestamps = df_work[time_col]  # Déjà convertis en datetime
    
    # Définir les périodes de coupure
    periods_dict = {
        "2 semaines": 14 * 24 * 3600,
        "1 mois": 30 * 24 * 3600,
        "3 mois": 90 * 24 * 3600,
    }
    
    frequencies_to_test = [(1 / period_sec, label) for label, period_sec in periods_dict.items()]
    
    fig, axes = plt.subplots(len(frequencies_to_test) + 1, 1, figsize=(14, 4 * (len(frequencies_to_test) + 1)))
    
    # Signal original
    axes[0].plot(timestamps, values, label='Signal original', color='black', linewidth=0.8, alpha=0.7)
    axes[0].set_title('Signal Brut', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('% Déviation FF', fontsize=10)
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    logger = logging.getLogger(__name__)
    
    # Tester chaque fréquence
    for idx, (cutoff_freq, period_label) in enumerate(frequencies_to_test):
        try:
            # Calculer fréquence d'échantillonnage
            time_diffs = timestamps.diff().dt.total_seconds().dropna()
            sampling_interval = time_diffs.mean()
            sampling_freq = 1 / sampling_interval if sampling_interval > 0 else 1
            
            # Filtre normalisé
            nyquist_freq = sampling_freq / 2
            normalized_cutoff = cutoff_freq / nyquist_freq
            
            if normalized_cutoff >= 1.0:
                normalized_cutoff = 0.99
            
            # Appliquer filtre
            b, a = signal.butter(5, normalized_cutoff, btype='low')
            filtered = signal.filtfilt(b, a, values)
            
            # Afficher
            ax = axes[idx + 1]
            ax.plot(timestamps, values, label='Signal brut', alpha=0.3, linewidth=0.5, color='lightgray')
            ax.plot(timestamps, filtered, label=f'Tendance ({period_label})', 
                   color='red', linewidth=2.0)
            ax.set_title(f'Filtre Période: {period_label}', fontsize=11, fontweight='bold')
            ax.set_ylabel('% Déviation FF', fontsize=10)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
        except Exception as e:
            logger.warning(f"Erreur pour période {period_label}: {e}")
            ax = axes[idx + 1]
            ax.text(0.5, 0.5, f'Erreur: {str(e)}', ha='center', va='center')
            ax.set_title(f'Période {period_label} (ERREUR)')
    
    axes[-1].set_xlabel('Temps', fontsize=10)
    plt.tight_layout()
    
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent.parent / "outputs"
    
    output_file = Path(output_dir) / "filter_comparison_multiple_frequencies.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"Graphiques de comparaison sauvegardés: {output_file}")
    plt.close()


def apply_lowpass_filter(df, time_col="timestamp", value_col="%ff_dev_total_(%)", 
                        cutoff_freq_hz=0.001, order=4):
    """
    Applique un filtre passe bas Butterworth sur une variable par rapport au temps.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame contenant les données
    time_col : str
        Nom de la colonne timestamp
    value_col : str
        Nom de la colonne à filtrer (variable d'intérêt)
    cutoff_freq_hz : float
        Fréquence de coupure en Hz (par défaut 0.001 Hz = période de ~1000 secondes)
    order : int
        Ordre du filtre Butterworth (par défaut 4)
    
    Returns:
    --------
    pd.DataFrame
        DataFrame avec colonne supplémentaire contenant les valeurs filtrées
    """
    df = df.copy()
    df = df.sort_values(time_col).reset_index(drop=True)
    
    logger = logging.getLogger(__name__)
    
    # Vérifier si les colonnes existent
    if time_col not in df.columns or value_col not in df.columns:
        raise ValueError(f"Colonnes requises manquantes: {time_col} ou {value_col}")
    
    # Convertir les timestamps en datetime AVANT de nettoyer
    try:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    except Exception as e:
        raise ValueError(f"Erreur lors de la conversion des timestamps: {e}")
    
    # Convertir la colonne de valeur en numérique
    try:
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    except Exception as e:
        raise ValueError(f"Erreur lors de la conversion de {value_col} en numérique: {e}")
    
    # Supprimer les valeurs NaN (timestamps ET values)
    mask = df[[time_col, value_col]].notna().all(axis=1)
    df_clean = df[mask].copy().reset_index(drop=True)
    
    if len(df_clean) < order + 1:
        raise ValueError(f"Pas assez de données valides pour appliquer le filtre d'ordre {order}")
    
    # Récupérer les timestamps (déjà convertis)
    timestamps = df_clean[time_col]
    
    if timestamps.isna().any():
        raise ValueError(f"Des NaN subsistent dans les timestamps")
    
    # Calculer la fréquence d'échantillonnage (moyenne)
    time_diffs = timestamps.diff().dt.total_seconds()
    time_diffs = time_diffs.dropna()
    
    if len(time_diffs) == 0:
        raise ValueError("Impossible de calculer les différences de temps")
    
    sampling_interval = time_diffs.mean()  # en secondes
    sampling_freq = 1 / sampling_interval if sampling_interval > 0 else 1
    
    # Vérifier la fréquence de coupure par rapport à Nyquist
    nyquist_freq = sampling_freq / 2
    normalized_cutoff = cutoff_freq_hz / nyquist_freq
    
    if normalized_cutoff >= 1.0:
        normalized_cutoff = 0.99
        logger.warning(f"Fréquence de coupure ajustée. Cutoff normalisé: {normalized_cutoff:.4f}")
    
    # Créer le filtre Butterworth
    b, a = signal.butter(order, normalized_cutoff, btype='low')
    
    # Appliquer le filtre (filtfilt pour pas de décalage de phase)
    filtered_values = signal.filtfilt(b, a, df_clean[value_col].values)
    
    # Ajouter la colonne filtrée directement au dataframe nettoyé
    df_clean[f"{value_col}_filtered"] = filtered_values
    
    # Fusionner avec l'original en utilisant l'indice original
    df.loc[df_clean.index, f"{value_col}_filtered"] = df_clean[f"{value_col}_filtered"].values
    
    logger.info(f"Filtre passe bas appliqué: fréquence d'échantillonnage={sampling_freq:.4f} Hz, "
                f"cutoff={cutoff_freq_hz:.6f} Hz, cutoff normalisé={normalized_cutoff:.4f}, ordre={order}")
    
    return df


def plot_lowpass_filter_comparison(df, time_col="timestamp", value_col="%ff_dev_total_(%)",
                                   filtered_col=None, output_path=None):
    """
    Visualise la comparaison entre les données brutes et filtrées.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame avec données brutes et filtrées
    time_col : str
        Nom de la colonne timestamp
    value_col : str
        Nom de la colonne brute
    filtered_col : str
        Nom de la colonne filtrée (si None, cherche {value_col}_filtered)
    output_path : str
        Chemin de sortie pour la figure (optionnel)
    """
    logger = logging.getLogger(__name__)
    
    if filtered_col is None:
        filtered_col = f"{value_col}_filtered"
    
    if filtered_col not in df.columns:
        raise ValueError(f"Colonne filtrée manquante: {filtered_col}")
    
    plt.figure(figsize=(14, 6))
    plt.plot(df[time_col], df[value_col], label='Signal brut', alpha=0.5, linewidth=0.8)
    plt.plot(df[time_col], df[filtered_col], label='Signal filtré', color='red', linewidth=1.5)
    plt.xlabel('Temps')
    plt.ylabel('% Déviation Débit Carburant')
    plt.title('Comparaison Signal Brut vs Signal Filtré (Passe Bas)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Graphique sauvegardé: {output_path}")
    
    plt.show()

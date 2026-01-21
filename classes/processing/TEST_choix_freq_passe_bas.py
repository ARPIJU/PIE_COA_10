"""
Script pour tester différentes fréquences de coupure du filtre passe bas
et visualiser l'effet sur le signal %ff_dev_total_(%)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import logging
from pathlib import Path

# Configuration
BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "outputs" / "data_processed.csv"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_lowpass_filter_test(values, timestamps, cutoff_freq_hz=0.001, order=5):
    """Applique le filtre passe bas avec logging détaillé"""
    
    # Vérifier les données
    if len(values) < order + 1:
        raise ValueError(f"Pas assez de données: {len(values)}")
    
    # Calculer la fréquence d'échantillonnage
    time_diffs = timestamps.diff().dt.total_seconds()
    time_diffs = time_diffs.dropna()
    
    sampling_interval = time_diffs.mean()
    sampling_freq = 1 / sampling_interval if sampling_interval > 0 else 1
    
    logger.info(f"Intervalle d'échantillonnage: {sampling_interval:.2f} secondes")
    logger.info(f"Fréquence d'échantillonnage: {sampling_freq:.6f} Hz")
    logger.info(f"Fréquence de Nyquist: {sampling_freq/2:.6f} Hz")
    
    # Fréquence de coupure normalisée
    nyquist_freq = sampling_freq / 2
    normalized_cutoff = cutoff_freq_hz / nyquist_freq
    
    logger.info(f"Fréquence de coupure demandée: {cutoff_freq_hz:.6f} Hz")
    logger.info(f"Fréquence de coupure normalisée: {normalized_cutoff:.4f}")
    
    if normalized_cutoff >= 1.0:
        logger.warning(f"Fréquence de coupure trop élevée! Ajustement de {normalized_cutoff:.4f} à 0.99")
        normalized_cutoff = 0.99
    
    # Créer et appliquer le filtre
    b, a = signal.butter(order, normalized_cutoff, btype='low')
    filtered = signal.filtfilt(b, a, values)
    
    return filtered

def test_multiple_frequencies():
    """Teste plusieurs fréquences de coupure adaptées aux tendances long terme"""
    
    # Charger les données
    if not DATA_FILE.exists():
        logger.error(f"Fichier de données non trouvé: {DATA_FILE}")
        logger.info("Assurez-vous d'avoir exécuté main.py d'abord")
        return
    
    logger.info(f"Chargement des données depuis {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    
    # Vérifier les colonnes
    if "%ff_dev_total_(%)" not in df.columns:
        logger.error("Colonne '%ff_dev_total_(%)' non trouvée")
        logger.info(f"Colonnes disponibles: {df.columns.tolist()}")
        return
    
    if "timestamp" not in df.columns:
        logger.error("Colonne 'timestamp' non trouvée")
        return
    
    # Préparer les données
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["%ff_dev_total_(%)"] = pd.to_numeric(df["%ff_dev_total_(%)"], errors="coerce")
    
    # Nettoyer les NaN
    mask = df[["timestamp", "%ff_dev_total_(%)"]].notna().all(axis=1)
    df_clean = df[mask].copy().sort_values("timestamp").reset_index(drop=True)
    
    logger.info(f"Données nettoyées: {len(df_clean)} enregistrements")
    logger.info(f"Plage de dates: {df_clean['timestamp'].min()} à {df_clean['timestamp'].max()}")
    logger.info(f"Durée totale: {(df_clean['timestamp'].max() - df_clean['timestamp'].min()).days} jours")
    
    values = df_clean["%ff_dev_total_(%)"].values
    timestamps = df_clean["timestamp"]
    
    # Calculer la fréquence d'échantillonnage
    time_diffs = timestamps.diff().dt.total_seconds()
    time_diffs = time_diffs.dropna()
    sampling_interval = time_diffs.mean()
    sampling_freq = 1 / sampling_interval if sampling_interval > 0 else 1
    
    logger.info(f"\nFréquence d'échantillonnage: {sampling_freq:.6f} Hz")
    logger.info(f"Intervalle d'échantillonnage: {sampling_interval:.2f} secondes ({sampling_interval/3600:.2f} heures)")
    
    # Définir les périodes de coupure souhaitées (en secondes)
    periods_dict = {
        "2 semaines": 0.5 * 30 * 24 * 3600,
        "1 mois": 1 * 30 * 24 * 3600,
        "1.5 mois": 1.5 * 30 * 24 * 3600,
    }
    
    # Convertir les périodes en fréquences de coupure
    frequencies_to_test = []
    period_labels = []
    for label, period_seconds in periods_dict.items():
        cutoff_freq = 1 / period_seconds  # Fréquence = 1 / période
        frequencies_to_test.append(cutoff_freq)
        period_labels.append(label)
        logger.info(f"Période {label:12s} → Fréquence de coupure: {cutoff_freq:.2e} Hz")
    
    filtered_signals = {}
    
    fig, axes = plt.subplots(len(frequencies_to_test) + 1, 1, figsize=(16, 4 * (len(frequencies_to_test) + 1)))
    
    # Afficher le signal original
    axes[0].plot(timestamps, values, label='Signal original', color='black', linewidth=0.8, alpha=0.7)
    axes[0].set_title('Signal Brut - Variations Journalières et Long Terme Mélangées', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('Déviation FF (%)', fontsize=10)
    axes[0].legend(fontsize=10)
    axes[0].grid(True, alpha=0.3)
    
    # Tester chaque fréquence
    for idx, (freq, period_label) in enumerate(zip(frequencies_to_test, period_labels)):
        logger.info(f"\n--- Test fréquence de coupure: {freq:.2e} Hz (Période: {period_label}) ---")
        try:
            filtered = apply_lowpass_filter_test(values, timestamps, cutoff_freq_hz=freq, order=5)
            filtered_signals[freq] = filtered
            
            # Afficher la comparaison
            ax = axes[idx + 1]
            ax.plot(timestamps, values, label='Signal brut', alpha=0.3, linewidth=0.5, color='lightgray')
            ax.plot(timestamps, filtered, label=f'Tendance ({period_label})', 
                   color='red', linewidth=2.0)
            ax.set_title(f'Signal Filtré - Tendances {period_label} (Cutoff: {freq:.2e} Hz)', 
                        fontsize=11, fontweight='bold')
            ax.set_ylabel('Déviation FF (%)', fontsize=10)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            
            logger.info(f"✓ Filtre appliqué avec succès (ordre=5)")
            logger.info(f"  Signal original - Min: {values.min():.4f}, Max: {values.max():.4f}, Std: {values.std():.4f}")
            logger.info(f"  Signal filtré   - Min: {filtered.min():.4f}, Max: {filtered.max():.4f}, Std: {filtered.std():.4f}")
            
        except Exception as e:
            logger.error(f"✗ Erreur avec période {period_label}: {e}")
            ax = axes[idx + 1]
            ax.text(0.5, 0.5, f'Erreur: {str(e)}', ha='center', va='center', fontsize=10)
            ax.set_title(f'Période {period_label} (ERREUR)', fontsize=11, fontweight='bold')
    
    # Ajouter l'étiquette X commune
    axes[-1].set_xlabel('Temps', fontsize=10)
    
    plt.tight_layout()
    output_file = BASE / "outputs" / "filter_tendances_long_terme.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    logger.info(f"\nGraphique sauvegardé: {output_file}")
    plt.show()

if __name__ == "__main__":
    test_multiple_frequencies()

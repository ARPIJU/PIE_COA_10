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
                                   filtered_col=None, output_path=None, events_df=None, 
                                   event_date_col="Date of Event"):
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
    events_df : pd.DataFrame, optional
        DataFrame contenant les événements de maintenance avec colonne de date
    event_date_col : str
        Nom de la colonne contenant les dates des événements (par défaut "date")
    """
    logger = logging.getLogger(__name__)
    
    if filtered_col is None:
        filtered_col = f"{value_col}_filtered"
    
    if filtered_col not in df.columns:
        raise ValueError(f"Colonne filtrée manquante: {filtered_col}")
    
    plt.figure(figsize=(14, 6))
    plt.plot(df[time_col], df[value_col], label='Signal brut', alpha=0.5, linewidth=0.8)
    plt.plot(df[time_col], df[filtered_col], label='Signal filtré', color='red', linewidth=1.5)
    
    # Ajouter les événements de maintenance si fournis (accepte noms mappés comme 'date_of_event')
    if events_df is not None and not events_df.empty:
        # build candidate names: original, lowercase, spaces->underscores, common mapped name
        candidates = [
            'date_of_event',
        ]
        # find first existing column
        date_col = next((c for c in candidates if c in events_df.columns), None)

        if date_col is not None:
            # collect valid event datetimes, labels and tail numbers (if present)
            events = []
            for _, row in events_df.loc[events_df[date_col].notna()].iterrows():
                event_date = row[date_col]
                try:
                    t = pd.to_datetime(event_date, errors='coerce')
                except Exception:
                    t = None
                if t is pd.NaT or t is None or pd.isna(t):
                    continue
                # event name (column 'event')
                ev_name = None
                if 'event' in events_df.columns:
                    ev_name = row.get('event')
                elif 'Event' in events_df.columns:
                    ev_name = row.get('Event')
                label_text = str(ev_name) if (ev_name is not None and pd.notna(ev_name)) else t.strftime("%Y-%m-%d")
                tail = row.get('tail_number') if 'tail_number' in events_df.columns else None
                events.append((t, label_text, tail))

            if events:
                # sort by time
                events.sort(key=lambda x: x[0])

                # determine minimum separation (in seconds) to avoid overlap, based on data span
                try:
                    span_secs = (pd.to_datetime(df[time_col]).max() - pd.to_datetime(df[time_col]).min()).total_seconds()
                    if span_secs <= 0 or pd.isna(span_secs):
                        span_secs = 1.0
                except Exception:
                    span_secs = 1.0

                num_events = max(1, len(events))
                min_sep = max(1.0, span_secs / max(10.0, float(num_events)))

                # greedy assignment of tiers: place each event in the lowest tier where it's at least min_sep from last placed
                tiers_last_time = []  # store last time in each tier
                events_with_tier = []
                for t, label_text, tail in events:
                    placed = False
                    for tier_idx, last_t in enumerate(tiers_last_time):
                        if abs((t - last_t).total_seconds()) >= min_sep:
                            tiers_last_time[tier_idx] = t
                            events_with_tier.append((t, label_text, tier_idx, tail))
                            placed = True
                            break
                    if not placed:
                        tiers_last_time.append(t)
                        events_with_tier.append((t, label_text, len(tiers_last_time) - 1, tail))

                # plot lines and annotate using tier to stagger vertically
                try:
                    ax = plt.gca()
                    y_min, y_max = ax.get_ylim()
                    if y_max is None or y_min is None or y_max == y_min:
                        y_max = (pd.to_numeric(df[value_col], errors='coerce').dropna().max() if value_col in df.columns else 0)
                        y_min = 0
                except Exception:
                    y_min, y_max = 0, 1

                # prepare color mapping per tail_number
                tails = [tail for (_, _, _, tail) in events_with_tier if tail is not None]
                unique_tails = list(dict.fromkeys(tails))
                # build a color list excluding the default blue and red (to maximize contrast
                # against the unfiltered (blue) and filtered (red) curves)
                base_cmap = plt.get_cmap('tab10') if len(unique_tails) <= 10 else plt.get_cmap('tab20')
                exclude_idxs = {0, 3}  # tab10: 0=blue, 3=red
                available_colors = [base_cmap(i) for i in range(base_cmap.N) if i not in exclude_idxs]
                if not available_colors:
                    available_colors = ['orange', 'green', 'purple', 'brown', 'olive', 'cyan']
                tail_colors = {t: available_colors[i % len(available_colors)] for i, t in enumerate(unique_tails)}

                seen_tails = set()
                for t, label_text, tier_idx, tail in events_with_tier:
                    color = tail_colors.get(tail, "orange")
                    # label each tail once for the legend
                    label = tail if (tail is not None and tail not in seen_tails) else ("_nolegend_" if tail is not None else 'Événement')
                    if tail is not None:
                        seen_tails.add(tail)
                    plt.axvline(t, color=color, linestyle="--", alpha=0.6, linewidth=1.5, label=label)
                    # truncate long labels
                    max_len = 40
                    if len(label_text) > max_len:
                        label_text_trunc = label_text[: max_len - 3] + "..."
                    else:
                        label_text_trunc = label_text

                    # compute vertical offset in points
                    vert_offset_pts = 6 + tier_idx * 12
                    try:
                        bbox_kwargs = dict(boxstyle='round,pad=0.2', fc='white', alpha=0.95)
                        if tail is not None:
                            bbox_kwargs['ec'] = tail_colors.get(tail, 'orange')
                        else:
                            bbox_kwargs['ec'] = 'orange'
                        ax.annotate(
                            label_text_trunc,
                            xy=(t, y_max),
                            xytext=(0, -vert_offset_pts),
                            textcoords='offset points',
                            ha='center',
                            va='top',
                            fontsize=8,
                            color='black',
                            rotation=0,
                            bbox=bbox_kwargs,
                            clip_on=True
                        )
                    except Exception:
                        pass

                # removed generic 'Événements de maintenance' legend entry — tails are labeled individually
        else:
            logger.warning(f"Colonne d'événement de maintenance introuvable (candidates tried: {candidates})")
            
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



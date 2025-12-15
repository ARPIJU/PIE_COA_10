import pandas as pd
import numpy as np
from typing import Dict, List
from classes.analysis.event_types import EventTypeConfig


def build_event_intervals(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Construit les intervalles [event_i, event_{i+1}) avec références au précédent,
    en conservant le nom et le tail_number (si présent) pour filtrage ciblé.
    """
    df = events_df.copy()
    df["event"] = df["event"].astype(str)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    df["next_event_date"] = df["date"].shift(-1)
    df["prev_event_date"] = df["date"].shift(1)
    df["event_idx"] = df.index
    df["event_name"] = df["event"].astype(str)

    keep_cols = ["event_idx", "date", "prev_event_date", "next_event_date", "event_name"]
    if "tail_number" in df.columns:
        keep_cols.append("tail_number")

    intervals = df.dropna(subset=["next_event_date"]).copy()
    return intervals[keep_cols].rename(columns={"date": "event_date"})


def slice_series(df_txt: pd.DataFrame,
                 start: pd.Timestamp,
                 end: pd.Timestamp,
                 metric: str,
                 tail_number: str = None) -> pd.DataFrame:
    """
    Extrait un segment temporel [start, end) sur la métrique choisie,
    optionnellement filtré par tail_number.
    """
    df = df_txt
    if tail_number is not None and "tail_number" in df.columns:
        df = df[df["tail_number"] == tail_number]

    mask = (df["timestamp"] >= start) & (df["timestamp"] < end)
    return df.loc[mask, ["timestamp", metric]].copy()


def fit_drift_rate(segment: pd.DataFrame,
                   start: pd.Timestamp,
                   time_axis: str = "days",
                   min_points: int = 2,
                   metric_col: str = "fuel_flow") -> float:
    """
    Estime la pente (dérive) de la métrique par unité de temps via régression linéaire.
    Retourne NaN si pas assez de points ou si l'étendue temporelle est nulle.
    """
    if segment.empty or segment.shape[0] < min_points:
        return np.nan

    ts = pd.to_datetime(segment["timestamp"], errors="coerce")
    y = segment[metric_col].astype(float).values

    if time_axis == "days":
        t = (ts - start).dt.total_seconds().values / (24 * 3600.0)
    elif time_axis == "hours":
        t = (ts - start).dt.total_seconds().values / 3600.0
    else:
        # fallback: indices
        t = np.arange(y.size, dtype=float)

    if np.ptp(t) == 0:
        return np.nan

    slope, _ = np.polyfit(t, y, 1)
    return float(slope)


def mean_in_stabilization_window(df_txt: pd.DataFrame,
                                 event_date: pd.Timestamp,
                                 window_days: int,
                                 metric: str,
                                 tail_number: str = None) -> float:
    """
    Moyenne de la métrique sur la fenêtre de stabilisation [event_date, event_date + window_days).
    """
    end = event_date + pd.Timedelta(days=window_days)
    seg = slice_series(df_txt, event_date, end, metric=metric, tail_number=tail_number)
    if seg.empty:
        return np.nan
    return float(seg[metric].astype(float).mean())


def compute_non_maintenance_metrics(df_txt: pd.DataFrame,
                                    intervals: pd.DataFrame,
                                    settings: Dict) -> pd.DataFrame:
    """
    Calcule pour chaque intervalle entre deux événements :
      - baseline_before: moyenne avant l’événement sur l’intervalle précédent
      - mean_after: moyenne sur la fenêtre de stabilisation après l’événement
      - drift_rate: pente sur l’intervalle courant (derrière l’événement)
      - valid: booléen selon les seuils (min_points, présence baseline, etc.)
    Utilise la métrique 'perf_factor' si disponible, sinon 'fuel_flow'.
    """
    out_rows: List[Dict] = []
    time_axis = settings["impact"]["time_axis"]
    window_days = int(settings["impact"]["stabilization_window_days"])
    min_points = int(settings["impact"]["min_points_per_interval"])
    require_prev = bool(settings["impact"]["require_prev_interval"])
    fallback_days = int(settings["impact"]["fallback_baseline_days"])

    metric = "perf_factor" if "perf_factor" in df_txt.columns else "fuel_flow"
    df_txt = df_txt.copy()
    df_txt["timestamp"] = pd.to_datetime(df_txt["timestamp"], errors="coerce")
    df_txt = df_txt.dropna(subset=["timestamp", metric]).sort_values("timestamp")

    for _, row in intervals.iterrows():
        event_date = row["event_date"]
        next_event_date = row["next_event_date"]
        prev_event_date = row["prev_event_date"]
        event_name = str(row["event_name"])
        tail_num = row["tail_number"] if "tail_number" in intervals.columns else None

        use_fallback = False
        if pd.isna(prev_event_date):
            use_fallback = True
            prev_event_date = event_date - pd.Timedelta(days=fallback_days)

        seg_prev = slice_series(df_txt, prev_event_date, event_date, metric=metric, tail_number=tail_num)
        seg_curr = slice_series(df_txt, event_date, next_event_date, metric=metric, tail_number=tail_num)

        n_prev = seg_prev.shape[0]
        n_curr = seg_curr.shape[0]

        baseline = float(seg_prev[metric].mean()) if n_prev > 0 else np.nan
        mean_after = mean_in_stabilization_window(df_txt, event_date, window_days, metric=metric, tail_number=tail_num)
        drift_rate = fit_drift_rate(seg_curr, event_date, time_axis=time_axis, min_points=min_points, metric_col=metric)

        valid_baseline = (not np.isnan(baseline)) and (n_prev >= (1 if not require_prev else min_points))
        valid_after = not np.isnan(mean_after)
        valid_interval = (n_curr >= min_points)
        valid = valid_baseline and valid_after and valid_interval and (not use_fallback or not require_prev)

        out_rows.append({
            "event_idx": int(row["event_idx"]),
            "event_date": event_date,
            "next_event_date": next_event_date,
            "event_name": event_name,
            "prev_event_date": (row["prev_event_date"] if not use_fallback else pd.NaT),
            "tail_number": tail_num,
            "metric": metric,
            "baseline_before": baseline,
            "mean_after": mean_after,
            "drift_rate": drift_rate,
            "n_points_prev": int(n_prev),
            "n_points_curr": int(n_curr),
            "valid": bool(valid)
        })

    return pd.DataFrame(out_rows)


def estimate_type_rates(non_main_table: pd.DataFrame,
                        events_df: pd.DataFrame,
                        settings: Dict) -> pd.DataFrame:
    """
    Estime un taux par type d’événement (impact par unité de temps) :
      rate = (baseline_before - mean_after) / delta_t
    où delta_t est le temps depuis la précédente même maintenance.
    """
    cfg = EventTypeConfig(settings["impact"]["allowed_maintenance_types"])
    accum: Dict[str, List[float]] = {}

    ev = events_df.copy()
    ev["event"] = ev["event"].astype(str)
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    ev = ev.dropna(subset=["date"]).sort_values("date")

    for _, row in non_main_table.iterrows():
        if not bool(row["valid"]):
            continue
        tname = str(row["event_name"])
        if not cfg.is_allowed(tname):
            continue

        # Filtrer par tail_number si disponible
        ev_subset = ev
        if "tail_number" in ev.columns and not pd.isna(row.get("tail_number", np.nan)):
            ev_subset = ev_subset[ev_subset["tail_number"] == row["tail_number"]]

        prev_same = ev_subset[(ev_subset["event"] == tname) & (ev_subset["date"] < row["event_date"])]
        if prev_same.empty:
            continue
        last_prev_date = prev_same["date"].max()

        # Delta temps selon l'axe
        if settings["impact"]["time_axis"] == "days":
            delta_t = (row["event_date"] - last_prev_date).days
        else:
            delta_t = (row["event_date"] - last_prev_date).total_seconds() / 3600.0

        if delta_t <= 0:
            continue

        # Impact observé instantané (amélioration = baseline_before - mean_after)
        J_obs = float(row["baseline_before"]) - float(row["mean_after"])
        rate = J_obs / float(delta_t)
        accum.setdefault(tname, []).append(rate)

    rows = []
    for t, vals in accum.items():
        n = len(vals)
        rate_mean = float(np.mean(vals)) if n > 0 else np.nan
        rate_std = float(np.std(vals, ddof=1)) if n > 1 else np.nan
        rows.append({
            "type": t,
            "rate_mean": rate_mean,
            "rate_std": rate_std,
            "n": int(n)
        })

    return pd.DataFrame(rows)


def compute_maintenance_impacts(events_df: pd.DataFrame,
                                non_main_table: pd.DataFrame,
                                type_rates_df: pd.DataFrame,
                                settings: Dict) -> pd.DataFrame:
    """
    Impact instantané d'une maintenance:
      impact_model = rate_type_mean * (temps depuis la dernière même maintenance)
    Fallback demandé par Pierre:
      si pas de rate_type_mean disponible, utiliser drift_non_maintenance_mean * delta_t.
    """
    cfg = EventTypeConfig(settings["impact"]["allowed_maintenance_types"])

    # Carte des taux par type
    rate_map: Dict[str, Dict] = {}
    for _, r in type_rates_df.iterrows():
        rate_map[str(r["type"])] = {
            "rate_mean": float(r["rate_mean"]),
            "rate_std": float(r["rate_std"]) if not pd.isna(r["rate_std"]) else np.nan,
            "n": int(r["n"])
        }

    # Moyenne des dérives sur les intervalles valides (fallback)
    valid_nm = non_main_table[non_main_table["valid"] == True]
    drift_rate_mean = float(valid_nm["drift_rate"].mean()) if not valid_nm.empty else np.nan

    ev = events_df.copy()
    ev["event"] = ev["event"].astype(str)
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    ev = ev.dropna(subset=["date"]).sort_values("date")

    impacts = []
    for _, row in non_main_table.iterrows():
        tname = str(row["event_name"])
        if not cfg.is_allowed(tname):
            continue

        # Sélection de la série d'événements pour le même tail si dispo
        ev_subset = ev
        if "tail_number" in ev.columns and not pd.isna(row.get("tail_number", np.nan)):
            ev_subset = ev_subset[ev_subset["tail_number"] == row["tail_number"]]

        prev_same = ev_subset[(ev_subset["event"] == tname) & (ev_subset["date"] < row["event_date"])]
        if prev_same.empty:
            continue
        last_prev_date = prev_same["date"].max()

        # Delta t selon axe
        if settings["impact"]["time_axis"] == "days":
            delta_t = (row["event_date"] - last_prev_date).days
        else:
            delta_t = (row["event_date"] - last_prev_date).total_seconds() / 3600.0

        if delta_t <= 0:
            continue

        # Modèle: produit "taux" * "temps depuis dernière même maintenance"
        rate_mean_type = rate_map.get(tname, {}).get("rate_mean", np.nan)
        if not pd.isna(rate_mean_type):
            impact_model = rate_mean_type * float(delta_t)
            rate_std_type = rate_map.get(tname, {}).get("rate_std", np.nan)
            rate_n_type = rate_map.get(tname, {}).get("n", 0)
            source = "type_rate"
        else:
            # Fallback demandé: utiliser drift non-maintenance moyen
            if pd.isna(drift_rate_mean):
                # Pas de fallback possible → ignorer
                continue
            impact_model = drift_rate_mean * float(delta_t)
            rate_std_type = np.nan
            rate_n_type = 0
            source = "fallback_drift"

        # Observé (si intervalle valide)
        J_obs = np.nan
        if bool(row["valid"]):
            # amélioration observée sur la fenêtre de stabilisation
            J_obs = float(row["baseline_before"]) - float(row["mean_after"])

        impacts.append({
            "event_date": row["event_date"],
            "event_name": tname,
            "tail_number": row.get("tail_number", None),
            "metric": row.get("metric", "fuel_flow"),
            "delta_t": float(delta_t),
            "impact_model": float(impact_model),
            "impact_observed": J_obs,
            "rate_mean_type": (rate_mean_type if not pd.isna(rate_mean_type) else drift_rate_mean),
            "rate_std_type": rate_std_type,
            "rate_n_type": int(rate_n_type),
            "rate_source": source
        })

    return pd.DataFrame(impacts)


def summarize_global(non_main_table: pd.DataFrame,
                     type_rates_df: pd.DataFrame,
                     maint_impacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Synthèse globale en une ligne:
      - n_intervals_valid, drift_rate_mean, drift_rate_std
      - maintenance_types_covered, avg_rate_mean_across_types
      - n_modeled_events, impact_model_mean, impact_model_std
      - n_fallback_drift (nombre d'impacts calculés via fallback drift)
    """
    # Non-maintenance
    valid_nm = non_main_table[non_main_table["valid"] == True]
    drift_mean = float(valid_nm["drift_rate"].mean()) if not valid_nm.empty else np.nan
    drift_std = float(valid_nm["drift_rate"].std(ddof=1)) if valid_nm.shape[0] > 1 else np.nan

    # Type rates
    n_types = type_rates_df.shape[0]
    avg_rate_mean = float(type_rates_df["rate_mean"].mean()) if n_types > 0 else np.nan

    # Modeled impacts
    n_modeled = maint_impacts_df.shape[0]
    impact_model_mean = float(maint_impacts_df["impact_model"].mean()) if n_modeled > 0 else np.nan
    impact_model_std = float(maint_impacts_df["impact_model"].std(ddof=1)) if n_modeled > 1 else np.nan
    n_fallback = int(maint_impacts_df[maint_impacts_df["rate_source"] == "fallback_drift"].shape[0]) if n_modeled > 0 else 0

    return pd.DataFrame([{
        "n_intervals_valid": int(valid_nm.shape[0]),
        "drift_rate_mean": drift_mean,
        "drift_rate_std": drift_std,
        "maintenance_types_covered": int(n_types),
        "avg_rate_mean_across_types": avg_rate_mean,
        "n_modeled_events": int(n_modeled),
        "impact_model_mean": impact_model_mean,
        "impact_model_std": impact_model_std,
        "n_fallback_drift": n_fallback
    }])

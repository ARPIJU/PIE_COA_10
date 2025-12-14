import pandas as pd

class ImpactAnalyzer:
    def join_with_events(self, measures: pd.DataFrame, events: pd.DataFrame,
                         by=("tail_number",), left_on="timestamp", right_on="date",
                         tolerance_days=14) -> pd.DataFrame:
        """
        Joint les mesures avec les événements en utilisant merge_asof.
        Les DataFrames doivent être triés par les colonnes de jointure.
        """

        # Tri explicite des clés avant merge_asof
        if left_on in measures.columns:
            measures = measures.sort_values(left_on).reset_index(drop=True)
        if right_on in events.columns:
            events = events.sort_values(right_on).reset_index(drop=True)

        merged = pd.merge_asof(
            left=measures,
            right=events,
            by=list(by),
            left_on=left_on,
            right_on=right_on,
            tolerance=pd.Timedelta(days=tolerance_days),
            direction="backward"
        )
        return merged

    def before_after(self, df: pd.DataFrame, event_col="event", ts_col="timestamp",
                     metric="fuel_flow", horizon_days=14) -> pd.DataFrame:
        """
        Calcule les deltas avant/après un événement pour une métrique donnée.
        """

        results = []
        if event_col not in df.columns or ts_col not in df.columns or metric not in df.columns:
            return pd.DataFrame()

        # S'assurer que la colonne temporelle est bien triée
        df = df.sort_values(ts_col).reset_index(drop=True)

        for ev in df[event_col].dropna().unique():
            ev_rows = df[df[event_col] == ev]
            if ev_rows.empty:
                continue

            ev_time = ev_rows[ts_col].min()
            before = df[(df[ts_col] >= ev_time - pd.Timedelta(days=horizon_days)) &
                        (df[ts_col] < ev_time)][metric]
            after = df[(df[ts_col] > ev_time) &
                       (df[ts_col] <= ev_time + pd.Timedelta(days=horizon_days))][metric]

            if not before.empty and not after.empty:
                delta = after.mean() - before.mean()
                results.append({"event": ev, "delta_" + metric: delta})

        return pd.DataFrame(results)

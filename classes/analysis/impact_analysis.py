import pandas as pd

class ImpactAnalyzer:
    def join_with_events(self, measures: pd.DataFrame, events: pd.DataFrame,
                         by=("tail_number",), left_on="timestamp", right_on="date",
                         tolerance_days=14) -> pd.DataFrame:
        measures = measures.sort_values(list(by)+[left_on]) if all(b in measures.columns for b in by) else measures.sort_values([left_on])
        events = events.sort_values(list(by)+[right_on]) if all(b in events.columns for b in by) else events.sort_values([right_on])
        tol = pd.Timedelta(days=tolerance_days)
        merged = pd.merge_asof(
            measures, events,
            left_on=left_on, right_on=right_on,
            by=list(by) if all(b in events.columns for b in by) else None,
            direction="backward", tolerance=tol
        )
        return merged

    def before_after(self, df: pd.DataFrame, event_col="event", ts_col="timestamp",
                     metric="fuel_flow", horizon_days=14) -> pd.DataFrame:
        if event_col not in df.columns or ts_col not in df.columns or metric not in df.columns:
            return pd.DataFrame()
        res = []
        df_events = df.dropna(subset=[event_col])
        for idx, ev in df_events.iterrows():
            t0 = ev[ts_col]
            pre = df[(df[ts_col] >= t0 - pd.Timedelta(days=horizon_days)) & (df[ts_col] < t0)]
            post = df[(df[ts_col] > t0) & (df[ts_col] <= t0 + pd.Timedelta(days=horizon_days))]
            res.append({
                "event": ev[event_col],
                "t0": t0,
                f"pre_{metric}": pre[metric].mean(),
                f"post_{metric}": post[metric].mean(),
                f"delta_{metric}": post[metric].mean() - pre[metric].mean() if len(pre) and len(post) else None
            })
        return pd.DataFrame(res)


import pandas as pd

def to_timedelta_days(days: int) -> pd.Timedelta:
    return pd.Timedelta(days=days)


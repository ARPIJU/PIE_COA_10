import pandas as pd

class MaintenanceScheduler:
    def __init__(self, catalog, constraints: dict, fuel_price: float):
        self.catalog = catalog
        self.constraints = constraints
        self.fuel_price = fuel_price

    def optimize(self, deltas: pd.DataFrame, event_col="event", delta_fuel_col="delta_fuel", default_delta_from_metric="delta_fuel_flow") -> pd.DataFrame:
        # Use delta_fuel if present, else derive from delta_fuel_flow
        if delta_fuel_col not in deltas.columns:
            if default_delta_from_metric in deltas.columns:
                deltas[delta_fuel_col] = deltas[default_delta_from_metric]
            else:
                deltas[delta_fuel_col] = 0.0

        budget = self.constraints.get("budget", float("inf"))
        max_downtime = self.constraints.get("max_downtime_hours", float("inf"))

        chosen = []
        cost_sum = 0.0
        downtime_sum = 0.0

        # Greedy: sort events by estimated ROI (gain * fuel_price - cost)
        tmp = []
        for m in self.catalog.list_all():
            mask = deltas[event_col] == m.name
            mean_gain_units = deltas.loc[mask, delta_fuel_col].mean() if mask.any() else 0.0
            roi = (mean_gain_units * self.fuel_price) - m.cost
            tmp.append((m.name, m.cost, m.downtime_hours, mean_gain_units, roi))

        tmp_sorted = sorted(tmp, key=lambda x: x[-1], reverse=True)

        for name, cost, dt, gain_units, roi in tmp_sorted:
            if roi > 0 and cost_sum + cost <= budget and downtime_sum + dt <= max_downtime:
                chosen.append({
                    "event": name,
                    "cost": cost,
                    "downtime_hours": dt,
                    "expected_gain_units": gain_units,
                    "roi": roi
                })
                cost_sum += cost
                downtime_sum += dt

        return pd.DataFrame(chosen)


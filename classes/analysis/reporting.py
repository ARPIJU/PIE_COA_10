import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

class Reporter:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _remove_if_exists(self, path: Path):
        """Supprime le fichier s'il existe déjà."""
        if path.exists():
            os.remove(path)
            logger.info("Old file %s removed", path)

    def summary_tables(self, impacts: pd.DataFrame, sort_col="delta_fuel") -> pd.DataFrame:
        summary = impacts.sort_values(sort_col, ascending=False) if not impacts.empty else impacts
        out_path = self.output_dir / "impact_summary.csv"
        self._remove_if_exists(out_path)   # Suppression avant écriture
        summary.to_csv(out_path, index=False)
        logger.info("Impact summary exported to %s", out_path)
        return summary

    def plot_metric(self, df: pd.DataFrame, metric="fuel_flow", event_col="event"):
        out_path = self.output_dir / f"{metric}_timeline.png"
        self._remove_if_exists(out_path)   # Suppression avant écriture
        plt.figure(figsize=(10,5))
        if metric in df.columns and "timestamp" in df.columns and not df.empty:
            plt.plot(df["timestamp"], df[metric], label=metric)
            if event_col in df.columns:
                for t, e in zip(df["timestamp"], df[event_col]):
                    if pd.notna(e):
                        plt.axvline(t, color="red", linestyle="--", alpha=0.3)
        else:
            plt.text(0.5, 0.5, "No data available", ha="center", va="center")
        plt.title(f"{metric} over time with events")
        plt.xlabel("Date")
        plt.ylabel(metric)
        plt.legend()
        plt.savefig(out_path)
        plt.close()
        logger.info("Plot exported to %s", out_path)

    def export_csv(self, df: pd.DataFrame, filename="maintenance_plan.csv"):
        out_path = self.output_dir / filename
        self._remove_if_exists(out_path)   # Suppression avant écriture
        df.to_csv(out_path, index=False)
        logger.info("CSV exported to %s", out_path)

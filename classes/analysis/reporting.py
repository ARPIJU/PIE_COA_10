import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Reporter:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def summary_tables(self, impacts: pd.DataFrame, sort_col="delta_fuel") -> pd.DataFrame:
        if impacts.empty:
            logger.warning("No impacts to summarize.")
            return impacts
        summary = impacts.sort_values(sort_col, ascending=False)
        out_path = self.output_dir / "impact_summary.csv"
        summary.to_csv(out_path, index=False)
        logger.info("Impact summary exported to %s", out_path)
        return summary

    def plot_metric(self, df: pd.DataFrame, metric="fuel_flow", event_col="event"):
        if metric not in df.columns or "timestamp" not in df.columns:
            logger.warning("Cannot plot: missing columns.")
            return
        plt.figure(figsize=(10,5))
        plt.plot(df["timestamp"], df[metric], label=metric)
        if event_col in df.columns:
            for t, e in zip(df["timestamp"], df[event_col]):
                if pd.notna(e):
                    plt.axvline(t, color="red", linestyle="--", alpha=0.3)
        plt.title(f"{metric} over time with events")
        plt.xlabel("Date")
        plt.ylabel(metric)
        plt.legend()
        out_path = self.output_dir / f"{metric}_timeline.png"
        plt.savefig(out_path)
        plt.close()
        logger.info("Plot exported to %s", out_path)

    def export_csv(self, df: pd.DataFrame, filename="export.csv"):
        out_path = self.output_dir / filename
        df.to_csv(out_path, index=False)
        logger.info("CSV exported to %s", out_path)


from pathlib import Path
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, base_path: Path, settings_path: Path):
        self.base_path = Path(base_path)
        self.settings_path = Path(settings_path)
        self.settings = self._load_settings()

    def _load_settings(self) -> dict:
        with open(self.settings_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_data_dir(self) -> Path:
        return self.base_path / self.settings["paths"]["data_dir"]

    def load_boeing_txt(self) -> pd.DataFrame:
        data_dir = self.get_data_dir()
        txt_file = data_dir / self.settings["paths"]["txt_file"]

        enc = self.settings["txt_read"]["encoding"]
        fallback_enc = self.settings["txt_read"]["fallback_encoding"]
        seps = self.settings["txt_read"]["possible_separators"]
        parse_dates = self.settings["txt_read"]["parse_dates"]
        dayfirst = self.settings["txt_read"]["dayfirst"]

        # Try auto-sep
        try:
            df = pd.read_csv(txt_file, sep=None, engine="python", encoding=enc)
            logger.info("Loaded TXT with sep=None and encoding=%s", enc)
        except Exception as e:
            logger.warning("Auto-sep failed: %s. Trying candidates...", e)
            df = None
            for s in seps:
                try:
                    df = pd.read_csv(txt_file, sep=s, engine="python", encoding=enc)
                    logger.info("Loaded TXT with sep='%s'", s)
                    break
                except Exception as e2:
                    logger.debug("Failed with sep='%s': %s", s, e2)
            if df is None:
                logger.warning("Trying fallback encoding=%s", fallback_enc)
                for s in seps:
                    try:
                        df = pd.read_csv(txt_file, sep=s, engine="python", encoding=fallback_enc)
                        logger.info("Loaded TXT with sep='%s' and fallback encoding", s)
                        break
                    except Exception as e3:
                        logger.debug("Fallback failed sep='%s': %s", s, e3)
        # Parse dates if present
        if df is not None:
            for col in parse_dates:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=dayfirst)
        return df

    def load_excel_sheet(self, sheet_name: str) -> pd.DataFrame:
        excel_path = self.get_data_dir() / self.settings["paths"]["excel_file"]
        return pd.read_excel(excel_path, sheet_name=sheet_name)

    def load_first_available_events(self) -> pd.DataFrame:
        excel_path = self.get_data_dir() / self.settings["paths"]["excel_file"]
        xls = pd.ExcelFile(excel_path)
        priority = self.settings.get("excel_sheets_priority", [])
        chosen = None
        for name in priority:
            if name in xls.sheet_names:
                chosen = name
                break
        if chosen is None:
            chosen = xls.sheet_names[0]
            logger.info("Priority sheets not found. Using first sheet: %s", chosen)
        return pd.read_excel(xls, sheet_name=chosen), chosen


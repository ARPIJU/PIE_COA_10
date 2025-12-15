import pandas as pd

def detect_separator(sample_path: str, possible_separators):
    """Détecte le séparateur probable en lisant les premières lignes du fichier TXT."""
    with open(sample_path, "r", encoding="utf-8", errors="ignore") as f:
        head = "".join([next(f) for _ in range(10)])
    for sep in possible_separators:
        if sep in head:
            return sep
    return ","  # défaut


def load_events(filepath: str, sheet_priority: list, ignore_sheets: list = None) -> pd.DataFrame:
    """Charge les événements depuis l’Excel CMA-FORM-FOE-10."""
    xls = pd.ExcelFile(filepath)
    available = xls.sheet_names

    ignore_sheets = ignore_sheets or []
    target_sheet = None
    for s in sheet_priority:
        if s in available and s not in ignore_sheets:
            target_sheet = s
            break
    if target_sheet is None:
        raise ValueError(f"Aucune feuille cible trouvée parmi {sheet_priority}, disponibles={available}")

    df = pd.read_excel(filepath, sheet_name=target_sheet)

    rename_map = {}
    for col in df.columns:
        lc = str(col).strip().lower()
        if lc == "date":
            rename_map[col] = "date"
        elif lc == "event":
            rename_map[col] = "event"
        elif lc == "remarks":
            rename_map[col] = "remarks"
        elif lc in ("update ?", "update_?"):
            rename_map[col] = "update_flag"
    df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise ValueError("Colonne 'date' manquante dans la feuille d'événements.")
    if "event" not in df.columns:
        df["event"] = ""

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def parse_recorded_date(val):
    """Essaye plusieurs formats pour parser les dates du TXT."""
    if pd.isna(val):
        return pd.NaT
    try:
        return pd.to_datetime(val, format="%Y/%m/%d", errors="coerce")
    except Exception:
        pass
    try:
        return pd.to_datetime(val, format="%Y/%d/%m", errors="coerce")
    except Exception:
        pass
    return pd.NaT


def load_txt_series(filepath: str, txt_read: dict, columns_mapping: dict) -> pd.DataFrame:
    """Charge le TXT avec mapping et construit timestamp, sans debug prints."""
    encoding = txt_read.get("encoding", "utf-8")
    fallback = txt_read.get("fallback_encoding", "latin-1")
    skip_rows = int(txt_read.get("skip_rows", 5))
    possible_separators = txt_read.get("possible_separators", [",", ";", "\t", "|"])

    sep = detect_separator(filepath, possible_separators)

    try:
        df = pd.read_csv(filepath, sep=sep, skiprows=skip_rows, encoding=encoding)
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, sep=sep, skiprows=skip_rows, encoding=fallback)

    # Appliquer le mapping fourni
    txt_map = columns_mapping.get("txt", {})
    for src, dst in txt_map.items():
        if src in df.columns:
            df = df.rename(columns={src: dst})

    if "recorded_date" not in df.columns:
        raise ValueError("Colonne 'recorded_date' manquante après mapping.")

    df["recorded_date"] = df["recorded_date"].apply(parse_recorded_date)

    if "time" in df.columns and df["time"].notna().any():
        df["timestamp"] = pd.to_datetime(
            df["recorded_date"].dt.strftime("%Y-%m-%d") + " " + df["time"].astype(str),
            errors="coerce"
        )
    else:
        df["timestamp"] = df["recorded_date"]

    if "fuel_flow" not in df.columns:
        raise ValueError("Colonne 'fuel_flow' manquante après mapping.")

    # Forcer fuel_flow en numérique
    df["fuel_flow"] = pd.to_numeric(df["fuel_flow"], errors="coerce")

    df = df.dropna(subset=["timestamp", "fuel_flow"]).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

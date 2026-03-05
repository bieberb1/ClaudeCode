"""
ingest.py — Load raw data files into DataFrames.

Supports: SAS (.sas7bdat), CSV, Excel (.xlsx/.xls)
Logs shape and null counts after every load.
Raises errors on missing files or unrecognized formats.

SAS equivalent: PROC IMPORT / LIBNAME
"""

import pandas as pd
import pyreadstat
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def _log_summary(df: pd.DataFrame, label: str) -> None:
    """Print shape and columns with null counts. Never prints row-level data."""
    print(f"\n{'─'*50}")
    print(f"[ingest] {label}")
    print(f"  Shape:   {df.shape[0]:,} rows × {df.shape[1]} columns")
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if nulls.empty:
        print("  Nulls:   none")
    else:
        print("  Nulls:")
        for col, n in nulls.items():
            pct = n / len(df) * 100
            print(f"    {col}: {n:,} ({pct:.1f}%)")
    print(f"{'─'*50}\n")


def _check_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return p


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_sas(path: str | Path, encoding: str = "latin1") -> tuple[pd.DataFrame, object]:
    """
    Load a SAS7BDAT file.
    Returns (DataFrame, metadata).
    Metadata contains variable labels — useful for documenting columns.

    SAS equivalent: LIBNAME mylib '/path/'; data = mylib.dataset;
    """
    p = _check_path(path)
    df, meta = pyreadstat.read_sas7bdat(str(p), encoding=encoding)
    _log_summary(df, f"SAS: {p.name}")
    return df, meta


def load_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    """
    Load a CSV file.
    Pass any pandas read_csv kwargs (e.g., parse_dates=['enc_dt']).

    SAS equivalent: PROC IMPORT datafile='...' out=ds dbms=csv replace;
    """
    p = _check_path(path)
    df = pd.read_csv(p, **kwargs)
    _log_summary(df, f"CSV: {p.name}")
    return df


def load_excel(path: str | Path, sheet_name: int | str = 0, **kwargs) -> pd.DataFrame:
    """
    Load an Excel file (.xlsx or .xls).

    SAS equivalent: PROC IMPORT datafile='...' out=ds dbms=xlsx replace;
    """
    p = _check_path(path)
    df = pd.read_excel(p, sheet_name=sheet_name, **kwargs)
    _log_summary(df, f"Excel: {p.name}, sheet={sheet_name}")
    return df


def load_any(path: str | Path, **kwargs) -> pd.DataFrame:
    """
    Auto-detect file type and load.
    Returns DataFrame only (no metadata for SAS — use load_sas() if you need labels).
    """
    p = _check_path(path)
    ext = p.suffix.lower()
    if ext == ".sas7bdat":
        df, _ = load_sas(p, **kwargs)
    elif ext == ".csv":
        df = load_csv(p, **kwargs)
    elif ext in (".xlsx", ".xls"):
        df = load_excel(p, **kwargs)
    else:
        raise ValueError(f"Unrecognized file extension: {ext}. "
                         f"Supported: .sas7bdat, .csv, .xlsx, .xls")
    return df


# ── SAS variable labels ───────────────────────────────────────────────────────

def sas_labels_to_df(meta) -> pd.DataFrame:
    """
    Convert pyreadstat metadata into a readable DataFrame of variable labels.
    Useful for documenting what SAS columns mean.

    Returns DataFrame with columns: variable, label
    """
    labels = [
        {"variable": var, "label": meta.column_names_to_labels.get(var, "")}
        for var in meta.column_names
    ]
    return pd.DataFrame(labels)

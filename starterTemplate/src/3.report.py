"""
report.py — Generate standardized output files.

Outputs: Excel workbooks, figure PNGs, plain-text run logs.
No patient-level data is written to reports/ — summaries only.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime


# ── Excel output ──────────────────────────────────────────────────────────────

def save_excel(
    sheets: dict[str, pd.DataFrame],
    output_path: str | Path,
    freeze_header: bool = True,
) -> None:
    """
    Write multiple DataFrames to named sheets in a single Excel workbook.

    Parameters
    ----------
    sheets : dict of {sheet_name: DataFrame}

    SAS equivalent: ODS EXCEL file='...' style=journal;
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            if freeze_header:
                ws = writer.sheets[sheet_name[:31]]
                ws.freeze_panes = "A2"

    print(f"[report] Excel workbook saved: {p} ({len(sheets)} sheets)")


# ── Figure saving ─────────────────────────────────────────────────────────────

def save_figure(
    fig: plt.Figure,
    output_path: str | Path,
    dpi: int = 150,
) -> None:
    """Save a matplotlib figure. Creates parent directories if needed."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[report] Figure saved: {p}")


# ── Run log ───────────────────────────────────────────────────────────────────

class RunLog:
    """
    Append-only text log for a single analysis run.
    Records steps, row counts, and analyst notes.
    Saved to reports/run_log_YYYYMMDD.txt.

    Useful for audit trail and reproducibility documentation.
    """

    def __init__(self, output_dir: str | Path = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.output_dir / f"run_log_{ts}.txt"
        self._write(f"Run started: {datetime.now().isoformat()}\n{'='*60}\n")

    def _write(self, text: str) -> None:
        with open(self.path, "a") as f:
            f.write(text + "\n")

    def log(self, step: str, details: str = "") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {step}"
        if details:
            entry += f"\n         {details}"
        print(entry)
        self._write(entry)

    def log_shape(self, df: pd.DataFrame, label: str) -> None:
        self.log(label, f"{df.shape[0]:,} rows × {df.shape[1]} columns")

    def finalize(self) -> None:
        self._write(f"\n{'='*60}\nRun completed: {datetime.now().isoformat()}")
        print(f"[report] Run log saved: {self.path}")

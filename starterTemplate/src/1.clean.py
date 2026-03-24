"""
clean.py — Data validation and QA checks.

All checks return a QAResult (passed flag + details).
Results are collected and written to reports/qa_report.csv.
No silent fixes — all issues are flagged for researcher review.

SAS equivalent: custom PROC SQL checks + data step validation
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date


# ── QA Result container ───────────────────────────────────────────────────────

@dataclass
class QAResult:
    check_name: str
    passed: bool
    n_flagged: int = 0
    details: str = ""
    flagged_ids: list = field(default_factory=list)  # member IDs, not data rows


def summarize_qa(results: list[QAResult], output_path: str | Path | None = None) -> pd.DataFrame:
    """
    Summarize all QA results into a DataFrame.
    Optionally write to CSV for the research record.
    """
    rows = [
        {
            "check": r.check_name,
            "passed": r.passed,
            "n_flagged": r.n_flagged,
            "details": r.details,
        }
        for r in results
    ]
    df = pd.DataFrame(rows)

    n_fail = (~df["passed"]).sum()
    print(f"\n[QA Summary] {len(df)} checks | {n_fail} failed\n")
    print(df.to_string(index=False))

    if output_path:
        df.to_csv(output_path, index=False)
        print(f"\n[QA] Report saved to {output_path}")

    return df


# ── Individual checks ─────────────────────────────────────────────────────────

def check_required_columns(df: pd.DataFrame, required: list[str]) -> QAResult:
    """
    Confirm that all required columns are present.

    SAS equivalent: %if %sysfunc(varnum(&ds, &var)) = 0 %then ...
    """
    missing = [c for c in required if c not in df.columns]
    passed = len(missing) == 0
    return QAResult(
        check_name="required_columns",
        passed=passed,
        n_flagged=len(missing),
        details=f"Missing columns: {missing}" if missing else "All required columns present",
    )


def check_duplicates(df: pd.DataFrame, subset: list[str], id_col: str | None = None) -> QAResult:
    """
    Flag duplicate rows on a given key (e.g., member-date duplicates).

    SAS equivalent: PROC SORT data=ds nodupkey dupout=dups by mbr_id enc_dt;
    """
    dup_mask = df.duplicated(subset=subset, keep=False)
    n = dup_mask.sum()
    ids = df.loc[dup_mask, id_col].unique().tolist() if id_col and n > 0 else []
    return QAResult(
        check_name=f"duplicates_on_{'+'.join(subset)}",
        passed=n == 0,
        n_flagged=int(n),
        details=f"{n:,} duplicate rows on {subset}" if n > 0 else "No duplicates",
        flagged_ids=ids[:100],  # cap to avoid enormous output
    )


def check_nulls(df: pd.DataFrame, critical_cols: list[str]) -> QAResult:
    """
    Flag records where any critical column is null.

    SAS equivalent: WHERE missing(mbr_id) OR missing(enc_dt);
    """
    mask = df[critical_cols].isnull().any(axis=1)
    n = mask.sum()
    null_counts = df[critical_cols].isnull().sum().to_dict()
    return QAResult(
        check_name=f"nulls_in_critical_cols",
        passed=n == 0,
        n_flagged=int(n),
        details=f"Null counts: {null_counts}" if n > 0 else "No nulls in critical columns",
    )


def check_date_range(
    df: pd.DataFrame,
    date_col: str,
    start: str | date,
    end: str | date,
) -> QAResult:
    """
    Flag dates outside the expected study period.

    SAS equivalent: WHERE enc_dt < '01JAN2021'd OR enc_dt > '31DEC2023'd;
    """
    col = pd.to_datetime(df[date_col], errors="coerce")
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)

    out_of_range = (col < start_dt) | (col > end_dt)
    unparseable = col.isnull() & df[date_col].notna()
    n_range = int(out_of_range.sum())
    n_parse = int(unparseable.sum())
    n_total = n_range + n_parse

    details_parts = []
    if n_range > 0:
        details_parts.append(f"{n_range:,} dates outside [{start}, {end}]")
    if n_parse > 0:
        details_parts.append(f"{n_parse:,} dates could not be parsed")

    return QAResult(
        check_name=f"date_range_{date_col}",
        passed=n_total == 0,
        n_flagged=n_total,
        details="; ".join(details_parts) if details_parts else f"All dates in range [{start}, {end}]",
    )


def check_impossible_values(
    df: pd.DataFrame,
    col: str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> QAResult:
    """
    Flag numeric values outside a plausible range.
    E.g., age < 0, LOS > 365, cost < 0.

    SAS equivalent: WHERE age < 0 OR age > 120;
    """
    mask = pd.Series(False, index=df.index)
    if min_val is not None:
        mask |= df[col] < min_val
    if max_val is not None:
        mask |= df[col] > max_val
    n = int(mask.sum())
    return QAResult(
        check_name=f"impossible_values_{col}",
        passed=n == 0,
        n_flagged=n,
        details=f"{n:,} values outside [{min_val}, {max_val}]" if n > 0 else f"All values in range",
    )


def check_orphaned_records(
    df_child: pd.DataFrame,
    df_parent: pd.DataFrame,
    key: str,
) -> QAResult:
    """
    Flag records in df_child with no matching key in df_parent.
    E.g., claims with no matching member record.

    SAS equivalent: PROC SQL; ... WHERE b.mbr_id IS NULL (left join check)
    """
    orphans = ~df_child[key].isin(df_parent[key])
    n = int(orphans.sum())
    return QAResult(
        check_name=f"orphaned_{key}",
        passed=n == 0,
        n_flagged=n,
        details=f"{n:,} records in child table with no matching {key} in parent" if n > 0 else "No orphaned records",
    )


def check_event_before_index(
    df: pd.DataFrame,
    event_col: str,
    index_col: str,
) -> QAResult:
    """
    Flag records where an outcome event date precedes the index date.
    Common data integrity issue in claims.
    """
    event_dt = pd.to_datetime(df[event_col], errors="coerce")
    index_dt = pd.to_datetime(df[index_col], errors="coerce")
    mask = event_dt < index_dt
    n = int(mask.sum())
    return QAResult(
        check_name=f"event_before_index_{event_col}_vs_{index_col}",
        passed=n == 0,
        n_flagged=n,
        details=f"{n:,} records where {event_col} < {index_col}" if n > 0 else "No event-before-index issues",
    )

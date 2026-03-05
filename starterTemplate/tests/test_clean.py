"""
tests/test_clean.py — Unit tests for QA checks in clean.py.

All tests use synthetic data only. Never import from data/raw/.
Run with: pytest tests/
"""

import pandas as pd
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from clean import (
    check_required_columns,
    check_duplicates,
    check_nulls,
    check_date_range,
    check_impossible_values,
    check_orphaned_records,
    check_event_before_index,
)


# ── Synthetic data fixtures ───────────────────────────────────────────────────

@pytest.fixture
def clean_encounters():
    """A minimal valid encounter table."""
    return pd.DataFrame({
        "mbr_id":   [1, 2, 3, 4, 5],
        "enc_dt":   pd.to_datetime(["2022-01-15", "2022-03-01", "2022-06-10",
                                    "2022-09-20", "2022-11-05"]),
        "los_days": [3, 1, 5, 2, 4],
        "disch_dt": pd.to_datetime(["2022-01-18", "2022-03-02", "2022-06-15",
                                    "2022-09-22", "2022-11-09"]),
    })


@pytest.fixture
def members():
    return pd.DataFrame({"mbr_id": [1, 2, 3, 4, 5]})


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRequiredColumns:
    def test_all_present(self, clean_encounters):
        result = check_required_columns(clean_encounters, ["mbr_id", "enc_dt"])
        assert result.passed

    def test_missing_column(self, clean_encounters):
        result = check_required_columns(clean_encounters, ["mbr_id", "missing_col"])
        assert not result.passed
        assert result.n_flagged == 1
        assert "missing_col" in result.details


class TestDuplicates:
    def test_no_duplicates(self, clean_encounters):
        result = check_duplicates(clean_encounters, subset=["mbr_id"])
        assert result.passed
        assert result.n_flagged == 0

    def test_with_duplicates(self, clean_encounters):
        df = pd.concat([clean_encounters, clean_encounters.iloc[[0]]], ignore_index=True)
        result = check_duplicates(df, subset=["mbr_id"])
        assert not result.passed
        assert result.n_flagged == 2  # both copies flagged


class TestNulls:
    def test_no_nulls(self, clean_encounters):
        result = check_nulls(clean_encounters, critical_cols=["mbr_id", "enc_dt"])
        assert result.passed

    def test_null_in_critical(self, clean_encounters):
        df = clean_encounters.copy()
        df.loc[0, "mbr_id"] = np.nan
        result = check_nulls(df, critical_cols=["mbr_id", "enc_dt"])
        assert not result.passed
        assert result.n_flagged == 1


class TestDateRange:
    def test_dates_in_range(self, clean_encounters):
        result = check_date_range(clean_encounters, "enc_dt", "2022-01-01", "2022-12-31")
        assert result.passed

    def test_date_out_of_range(self, clean_encounters):
        df = clean_encounters.copy()
        df.loc[0, "enc_dt"] = pd.Timestamp("2019-01-01")
        result = check_date_range(df, "enc_dt", "2022-01-01", "2022-12-31")
        assert not result.passed
        assert result.n_flagged == 1


class TestImpossibleValues:
    def test_valid_los(self, clean_encounters):
        result = check_impossible_values(clean_encounters, "los_days", min_val=0, max_val=365)
        assert result.passed

    def test_negative_los(self, clean_encounters):
        df = clean_encounters.copy()
        df.loc[2, "los_days"] = -1
        result = check_impossible_values(df, "los_days", min_val=0)
        assert not result.passed
        assert result.n_flagged == 1


class TestOrphanedRecords:
    def test_no_orphans(self, clean_encounters, members):
        result = check_orphaned_records(clean_encounters, members, key="mbr_id")
        assert result.passed

    def test_orphaned_encounter(self, clean_encounters, members):
        df = clean_encounters.copy()
        df.loc[0, "mbr_id"] = 999  # not in members table
        result = check_orphaned_records(df, members, key="mbr_id")
        assert not result.passed
        assert result.n_flagged == 1


class TestEventBeforeIndex:
    def test_valid_sequence(self, clean_encounters):
        result = check_event_before_index(clean_encounters, "disch_dt", "enc_dt")
        assert result.passed

    def test_event_before_index(self, clean_encounters):
        df = clean_encounters.copy()
        df.loc[1, "disch_dt"] = pd.Timestamp("2022-01-01")  # before enc_dt
        result = check_event_before_index(df, "disch_dt", "enc_dt")
        assert not result.passed
        assert result.n_flagged == 1

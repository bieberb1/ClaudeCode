"""
analyze.py — Statistical analysis functions.

Covers:
  - Descriptive statistics (Table 1 style)
  - Kaplan-Meier survival curves
  - Cox proportional hazards model

IMPORTANT: This module handles computation only.
Analytic decisions (event definitions, covariate selection,
censoring rules) must be specified by the researcher.

SAS equivalents noted throughout.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


# ── Descriptive statistics ────────────────────────────────────────────────────

def descriptive_table(
    df: pd.DataFrame,
    continuous_cols: list[str],
    categorical_cols: list[str],
    group_col: str | None = None,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Generate a Table 1-style descriptive summary.
    Continuous: mean (SD), median [IQR].
    Categorical: n (%).

    SAS equivalent: PROC MEANS + PROC FREQ, optionally BY group.
    """
    groups = [None]
    if group_col:
        groups = sorted(df[group_col].dropna().unique())

    rows = []

    for col in continuous_cols:
        row = {"variable": col, "type": "continuous"}
        for g in groups:
            sub = df[df[group_col] == g] if group_col and g is not None else df
            vals = sub[col].dropna()
            label = str(g) if group_col else "overall"
            row[f"{label}_mean_sd"] = f"{vals.mean():.2f} ({vals.std():.2f})"
            row[f"{label}_median_iqr"] = (
                f"{vals.median():.2f} [{vals.quantile(0.25):.2f}, {vals.quantile(0.75):.2f}]"
            )
            row[f"{label}_n_missing"] = int(sub[col].isnull().sum())
        rows.append(row)

    for col in categorical_cols:
        cats = df[col].dropna().unique()
        for cat in sorted(cats):
            row = {"variable": f"{col} = {cat}", "type": "categorical"}
            for g in groups:
                sub = df[df[group_col] == g] if group_col and g is not None else df
                label = str(g) if group_col else "overall"
                n = int((sub[col] == cat).sum())
                pct = n / len(sub) * 100 if len(sub) > 0 else np.nan
                row[f"{label}_n_pct"] = f"{n:,} ({pct:.1f}%)"
            rows.append(row)

    result = pd.DataFrame(rows)

    if output_path:
        result.to_excel(output_path, index=False)
        print(f"[analyze] Table 1 saved to {output_path}")

    return result


# ── Kaplan-Meier ──────────────────────────────────────────────────────────────

def kaplan_meier(
    df: pd.DataFrame,
    duration_col: str,
    event_col: str,
    group_col: str | None = None,
    label: str = "KM Curve",
    output_path: str | Path | None = None,
) -> object:
    """
    Fit and plot Kaplan-Meier survival curves.

    Requires: pip install lifelines

    Parameters
    ----------
    duration_col : time from index to event or censoring (in days or other unit)
    event_col    : 1 = event occurred, 0 = censored
                   *** Researcher must define this — do not assume ***
    group_col    : optional stratification variable

    SAS equivalent: PROC LIFETEST data=ds plots=survival(atrisk);
                      time time_to_event*event_flag(0);
                      strata group;
    """
    try:
        from lifelines import KaplanMeierFitter
        from lifelines.statistics import logrank_test
    except ImportError:
        raise ImportError("lifelines is required: pip install lifelines")

    fig, ax = plt.subplots(figsize=(8, 5))
    results = {}

    groups = [None]
    if group_col:
        groups = sorted(df[group_col].dropna().unique())

    kmfs = {}
    for g in groups:
        sub = df[df[group_col] == g] if group_col and g is not None else df
        kmf = KaplanMeierFitter()
        name = str(g) if group_col else "Overall"
        kmf.fit(
            sub[duration_col],
            event_observed=sub[event_col],
            label=name,
        )
        kmf.plot_survival_function(ax=ax, ci_show=True)
        kmfs[name] = kmf

    # Log-rank test if two groups
    if group_col and len(groups) == 2:
        g0, g1 = groups
        sub0 = df[df[group_col] == g0]
        sub1 = df[df[group_col] == g1]
        lr = logrank_test(
            sub0[duration_col], sub1[duration_col],
            sub0[event_col], sub1[event_col],
        )
        ax.set_title(f"{label}\nLog-rank p = {lr.p_value:.4f}")
        results["logrank_p"] = lr.p_value
    else:
        ax.set_title(label)

    ax.set_xlabel("Time")
    ax.set_ylabel("Survival probability")
    ax.set_ylim(0, 1.05)

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[analyze] KM plot saved to {output_path}")
        plt.close(fig)
    else:
        plt.show()

    results["kmf"] = kmfs
    return results


# ── Cox proportional hazards ──────────────────────────────────────────────────

def cox_model(
    df: pd.DataFrame,
    duration_col: str,
    event_col: str,
    covariates: list[str],
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Fit a Cox proportional hazards model.

    Requires: pip install lifelines

    Parameters
    ----------
    covariates : list of column names to include as predictors
                 *** Researcher must specify — do not select automatically ***

    Returns hazard ratio table with 95% CI and p-values.

    SAS equivalent: PROC PHREG data=ds;
                      model time_to_event*event_flag(0) = var1 var2 var3;
    """
    try:
        from lifelines import CoxPHFitter
    except ImportError:
        raise ImportError("lifelines is required: pip install lifelines")

    cols_needed = [duration_col, event_col] + covariates
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    model_df = df[cols_needed].dropna()
    n_dropped = len(df) - len(model_df)
    if n_dropped > 0:
        print(f"[cox] WARNING: {n_dropped:,} rows dropped due to missing values in model columns")

    cph = CoxPHFitter()
    cph.fit(model_df, duration_col=duration_col, event_col=event_col)

    summary = cph.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%", "p"]].copy()
    summary.columns = ["HR", "HR_lower_95", "HR_upper_95", "p_value"]
    summary = summary.reset_index().rename(columns={"index": "covariate"})
    summary["HR_fmt"] = summary.apply(
        lambda r: f"{r.HR:.3f} ({r.HR_lower_95:.3f}–{r.HR_upper_95:.3f})", axis=1
    )

    print("\n[cox] Cox PH Model Results:")
    print(summary[["covariate", "HR_fmt", "p_value"]].to_string(index=False))
    print(f"\n  Events: {int(model_df[event_col].sum())} | N: {len(model_df):,}")

    if output_path:
        summary.to_csv(output_path, index=False)
        print(f"[analyze] Cox results saved to {output_path}")

    return summary

"""
Quantitative transformations for expected losses, migrations, and cohorts.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd


def compute_expected_losses(
    harmonized,
) -> Dict[str, pd.DataFrame]:
    """
    Compute expected loss metrics needed for the backtest page.
    """
    from wow_risk_dashboard.io.schemas import (
        EAD_PRIORITY,
        LGD_FIELDS,
        PD_PRIORITY,
        DATE_FIELDS,
        IDENTIFIER_FIELDS,
    )
    from .harmonize import HarmonizedDataset

    if not isinstance(harmonized, HarmonizedDataset):
        raise TypeError("compute_expected_losses expects a HarmonizedDataset.")

    risk_df = harmonized.risk_metric.copy()
    if risk_df.empty:
        return {}

    def pick_column(df: pd.DataFrame, candidates) -> str | None:
        for name in candidates:
            if name in df.columns:
                return name
        return None

    pd_col = pick_column(risk_df, PD_PRIORITY)
    lgd_col = pick_column(risk_df, LGD_FIELDS) or None
    ead_col = pick_column(risk_df, EAD_PRIORITY) or None

    # Enrich EAD from result or cashflow when not present in risk metrics.
    if ead_col is None:
        for source in (harmonized.result, harmonized.cashflow):
            if source.empty:
                continue
            alt = pick_column(source, EAD_PRIORITY)
            if alt:
                alt_df = source[[col for col in IDENTIFIER_FIELDS if col in source.columns] + [alt]].copy()
                risk_df = risk_df.merge(
                    alt_df,
                    on=[col for col in IDENTIFIER_FIELDS if col in alt_df.columns],
                    how="left",
                    suffixes=("", "_alt"),
                )
                ead_col = alt
                break

    if pd_col is None:
        return {}

    risk_df["pd_value"] = pd.to_numeric(risk_df[pd_col], errors="coerce").fillna(0.0)
    if lgd_col and lgd_col in risk_df.columns:
        risk_df["lgd_value"] = pd.to_numeric(risk_df[lgd_col], errors="coerce").fillna(0.45)
    else:
        risk_df["lgd_value"] = 0.45

    if ead_col and ead_col in risk_df.columns:
        risk_df["ead_value"] = pd.to_numeric(risk_df[ead_col], errors="coerce").fillna(0.0)
    else:
        risk_df["ead_value"] = 0.0

    risk_df["expected_loss"] = risk_df["pd_value"] * risk_df["lgd_value"] * risk_df["ead_value"]

    instrument_cols = [col for col in ["instrumentIdentifier", "portfolioIdentifier"] if col in risk_df.columns]
    if "portfolioIdentifier" not in instrument_cols:
        risk_df["portfolioIdentifier"] = "All portfolios"
        instrument_cols.append("portfolioIdentifier")
    instrument_df = risk_df[instrument_cols + ["pd_value", "lgd_value", "ead_value", "expected_loss"]]

    portfolio_df = (
        instrument_df.groupby("portfolioIdentifier", dropna=False)
        .agg(expected_loss=("expected_loss", "sum"), total_ead=("ead_value", "sum"))
        .reset_index()
    )
    portfolio_df["expected_loss_rate"] = portfolio_df["expected_loss"] / portfolio_df["total_ead"].replace(0, pd.NA)

    date_col = next((col for col in DATE_FIELDS if col in risk_df.columns), None)
    if date_col:
        risk_df["period"] = pd.to_datetime(risk_df[date_col], errors="coerce").dt.to_period("Q")
        timeline = (
            risk_df.dropna(subset=["period"])
            .groupby("period")
            .agg(expected_loss=("expected_loss", "sum"), total_ead=("ead_value", "sum"))
            .reset_index()
        )
        timeline["expected_loss_rate"] = timeline["expected_loss"] / timeline["total_ead"].replace(0, pd.NA)
    else:
        timeline = pd.DataFrame(columns=["period", "expected_loss", "total_ead", "expected_loss_rate"])

    return {
        "instrument": instrument_df,
        "portfolio": portfolio_df,
        "timeline": timeline,
    }


def build_rating_migration(
    results: pd.DataFrame,
    risk_metrics: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Construct rating migration analytics outputs:
      * Sankey edge list
      * Transition matrix
      * Top movers summary
    """
    if results.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    rating_order = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
    rating_rank = {value: idx for idx, value in enumerate(rating_order)}

    def normalize_rating(series: pd.Series) -> pd.Series:
        cleaned = series.fillna("").astype(str).str.strip().str.upper()
        return cleaned.replace({"NR": "UNRATED", "": "UNRATED"})

    results = results.copy()
    results["rating"] = normalize_rating(results["rating"])
    results["period"] = results["period"].astype(str)

    if not risk_metrics.empty and "pd_value" not in risk_metrics.columns:
        candidates = [col for col in risk_metrics.columns if col not in {"instrumentIdentifier", "period"}]
        pd_col = candidates[0] if candidates else None
        if pd_col:
            risk_metrics = risk_metrics.rename(columns={pd_col: "pd_value"})

    def pd_to_rating(pd_value: float) -> str:
        if pd_value <= 0.005:
            return "A"
        if pd_value <= 0.015:
            return "BBB"
        if pd_value <= 0.03:
            return "BB"
        if pd_value <= 0.06:
            return "B"
        return "CCC"

    if not risk_metrics.empty:
        risk_metrics = risk_metrics.copy()
        risk_metrics["rating"] = risk_metrics["pd_value"].astype(float).apply(pd_to_rating)
        risk_metrics["rating"] = normalize_rating(risk_metrics["rating"])
        fallback = risk_metrics[["instrumentIdentifier", "period", "rating"]]
        results = pd.concat([results, fallback], ignore_index=True)

    pivot = results.pivot_table(
        index="instrumentIdentifier",
        columns="period",
        values="rating",
        aggfunc="first",
    )
    start = pivot.get("2023Q2")
    end = pivot.get("2025Q2")
    if start is None or end is None:
        empty = pd.DataFrame()
        return empty, empty, empty

    transitions = pd.DataFrame({"start": start, "end": end}).dropna()
    transitions["start"] = normalize_rating(transitions["start"])
    transitions["end"] = normalize_rating(transitions["end"])
    transitions["direction"] = transitions.apply(
        lambda row: "Upgrade"
        if rating_rank.get(row["end"], 99) < rating_rank.get(row["start"], 99)
        else ("Downgrade" if rating_rank.get(row["end"], 99) > rating_rank.get(row["start"], 99) else "Unchanged"),
        axis=1,
    )

    matrix = pd.crosstab(transitions["start"], transitions["end"]).reset_index()
    total = transitions.shape[0] or 1
    edges = (
        transitions.groupby(["start", "end"])
        .size()
        .reset_index(name="count")
        .assign(share=lambda df: df["count"] / total)
    )

    movers = transitions.reset_index().rename(columns={"index": "instrumentIdentifier"})
    movers["magnitude"] = movers.apply(
        lambda row: rating_rank.get(row["end"], 99) - rating_rank.get(row["start"], 99),
        axis=1,
    )
    movers = movers.sort_values("magnitude", key=lambda s: s.abs(), ascending=False)

    return edges, matrix, movers


def build_default_cohorts(
    risk_metrics: pd.DataFrame,
    chargeoffs: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Build defaulted cohorts and matched control analytics.
    """
    from wow_risk_dashboard.io.schemas import PD_PRIORITY, DATE_FIELDS

    if chargeoffs.empty or risk_metrics.empty:
        return {}

    chargeoffs = chargeoffs.copy()
    chargeoffs["event_date"] = pd.NaT
    for field in DATE_FIELDS:
        if field in chargeoffs.columns and chargeoffs["event_date"].isna().all():
            chargeoffs["event_date"] = pd.to_datetime(chargeoffs[field], errors="coerce")
    chargeoffs = chargeoffs.dropna(subset=["event_date"])

    events = (
        chargeoffs.groupby("instrumentIdentifier")["event_date"].min().reset_index()
    )

    risk = risk_metrics.copy()
    pd_col = next((col for col in PD_PRIORITY if col in risk.columns), None)
    if pd_col is None:
        return {}
    risk["pd_value"] = pd.to_numeric(risk[pd_col], errors="coerce")
    date_col = next((col for col in DATE_FIELDS if col in risk.columns), None)
    if date_col is None:
        return {}
    risk["obs_date"] = pd.to_datetime(risk[date_col], errors="coerce")

    merged = events.merge(risk, on="instrumentIdentifier", how="left")
    merged["months_to_default"] = ((merged["event_date"] - merged["obs_date"]).dt.days // 30).astype("Int64")
    window = merged[(merged["months_to_default"] <= 0) & (merged["months_to_default"] >= -36)]

    pd_path = (
        window.groupby("months_to_default")["pd_value"]
        .mean()
        .reset_index()
        .sort_values("months_to_default")
    )

    cohort_summary = (
        events.assign(event_quarter=lambda df: df["event_date"].dt.to_period("Q"))
        .groupby("event_quarter")
        .size()
        .reset_index(name="defaults")
        .sort_values("event_quarter")
    )

    latest_pd = (
        window.sort_values("obs_date")
        .groupby("instrumentIdentifier")
        .tail(1)[["instrumentIdentifier", "pd_value", "event_date"]]
        .rename(columns={"pd_value": "pd_before_default"})
    )

    return {
        "events": events,
        "pd_path": pd_path,
        "cohort_summary": cohort_summary,
        "latest_pd": latest_pd,
    }

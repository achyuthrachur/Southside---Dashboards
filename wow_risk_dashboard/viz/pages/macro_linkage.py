"""
Streamlit page for Southside Bank macro linkage analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from wow_risk_dashboard.components import (
    HeaderExpectation,
    PageInputConfig,
    export_controls,
    render_inputs_panel,
    load_input_dataframe,
)
from wow_risk_dashboard.io.schemas import PD_PRIORITY, GEOGRAPHY_PRIORITY

PAGE_KEY = "macro_linkage"
EXPECTED_START = datetime(2023, 1, 1)
EXPECTED_END = datetime(2025, 6, 30)

INPUT_CONFIGS = [
    PageInputConfig(
        key="risk_metrics_timeseries",
        title="Instrument Risk Metric (2023 through 2025)",
        dataset_key="instrument_risk_metric",
        required=True,
        description=(
            "Time-series probability of default and LGD data spanning 2023 through mid 2025."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Observation date",
                candidates=["reportingDate", "asOfDate"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Probability of default",
                candidates=[
                    "annualizedCumulativePD",
                    "forwardPD",
                    "cumulativePD",
                    "marginalPD",
                    "maturityRiskPD",
                ],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Loss given default",
                candidates=["lgd"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="reference_enrichment",
        title="Instrument Reference (Geography Enrichment)",
        dataset_key="instrument_reference",
        required=True,
        description=(
            "Provides ZIP, CBSA, state, and portfolio identifiers for geography mapping."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=True,
                match="all",
            ),
            HeaderExpectation(
                name="Latest snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="Geography (CBSA/ZIP priority)",
                candidates=["geographyCode", "borrowerZipCode", "collateralZipCode"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="State fallback",
                candidates=["borrowerState", "collateralState"],
                required=True,
                match="any",
            ),
        ],
    ),
]


def _render_readiness(panel_state) -> bool:
    missing_files = panel_state.missing_required_files
    missing_headers = panel_state.missing_required_headers
    if not missing_files and not missing_headers:
        return True

    lines: List[str] = []
    if missing_files:
        lines.append(
            "Missing required file(s): " + ", ".join(f"{name}" for name in missing_files)
        )
    if missing_headers:
        header_lines = [
            f"- **{title}**: {', '.join(headers)}"
            for title, headers in missing_headers.items()
        ]
        lines.append("Missing required column(s):\n" + "\n".join(header_lines))
    st.warning(
        "Southside Bank macro linkage inputs are incomplete.\n\n" + "\n".join(lines)
    )
    return False


def _parse_dates(path: str, column: Optional[str]) -> pd.Series:
    if not path or not column:
        return pd.Series(dtype="datetime64[ns]")
    df = load_input_dataframe(path, (column,))
    return pd.to_datetime(df[column], errors="coerce").dropna()


def _validate_timespan(panel_state) -> List[str]:
    errors: List[str] = []
    risk_status = panel_state.statuses.get("risk_metrics_timeseries")
    if risk_status and risk_status.is_loaded:
        date_column = (
            risk_status.selected_columns.get("reportingDate")
            or risk_status.selected_columns.get("asOfDate")
        )
        dates = _parse_dates(risk_status.file_path, date_column)
        if dates.empty:
            errors.append(
                "Risk metric time series lacks valid reporting/as-of dates. "
                "Ensure the file contains observations from 2023 through 2025."
            )
        else:
            if dates.min() > EXPECTED_START:
                errors.append(
                    f"Risk metric series begins on {dates.min().date()}, "
                    "but should include observations on or before 2023-01-01."
                )
            if dates.max() < EXPECTED_END:
                errors.append(
                    f"Risk metric series ends on {dates.max().date()}, "
                    "but should extend through at least mid-2025."
                )
    return errors


def _pick_column(df: pd.DataFrame, candidates) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _load_risk_series(status) -> pd.DataFrame:
    if not status.is_loaded:
        return pd.DataFrame()
    columns = list(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    pd_col = _pick_column(df, PD_PRIORITY)
    date_col = _pick_column(df, ["reportingDate", "asOfDate"])
    if not pd_col or not date_col:
        return pd.DataFrame()
    df["pd_value"] = pd.to_numeric(df[pd_col], errors="coerce")
    df["observation_date"] = pd.to_datetime(df[date_col], errors="coerce")
    keep = ["instrumentIdentifier", "pd_value", "observation_date"]
    return df[keep]


def _load_reference(status) -> pd.DataFrame:
    if not status.is_loaded:
        return pd.DataFrame()
    columns = list(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    keep = ["instrumentIdentifier"] + [col for col in GEOGRAPHY_PRIORITY if col in df.columns] + ["borrowerState", "collateralState"]
    keep = [col for col in keep if col in df.columns]
    return df[keep]


def _normalize_state(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.upper().str.strip()
    return cleaned.where(cleaned.str.len() == 2)


def _attach_geography(risk_df: pd.DataFrame, reference_df: pd.DataFrame) -> pd.DataFrame:
    merged = risk_df.merge(reference_df, on="instrumentIdentifier", how="left")
    state = merged["borrowerState"] if "borrowerState" in merged.columns else merged.get("collateralState")
    merged["state"] = _normalize_state(state) if state is not None else pd.NA
    geo_col = _pick_column(merged, list(GEOGRAPHY_PRIORITY))
    if geo_col:
        merged["geography"] = merged[geo_col]
    else:
        merged["geography"] = merged["state"]
    return merged


def render_macro_linkage_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    validation_errors = _validate_timespan(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    risk_df = _load_risk_series(panel_state.statuses["risk_metrics_timeseries"])
    ref_df = _load_reference(panel_state.statuses["reference_enrichment"])
    if risk_df.empty or ref_df.empty:
        st.warning("Risk metric time series or reference geography file is empty.")
        export_controls("macro_linkage")
        return

    merged = _attach_geography(risk_df, ref_df)
    merged = merged.dropna(subset=["observation_date"])
    merged["month"] = merged["observation_date"].dt.to_period("M")

    monthly_trend = (
        merged.groupby("month")["pd_value"]
        .mean()
        .reset_index()
        .sort_values("month")
    )

    geo_summary = (
        merged.groupby(["geography", "month"])["pd_value"]
        .mean()
        .reset_index()
        .sort_values("month")
    )

    st.markdown("### Portfolio PD trend")
    fig = px.line(
        monthly_trend,
        x="month",
        y="pd_value",
        labels={"pd_value": "Average PD", "month": "Month"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Geography movers (PD change from start to end)")
    geo_first_last = (
        geo_summary.groupby("geography")["pd_value"]
        .agg(start="first", end="last")
        .reset_index()
    )
    geo_first_last["change"] = geo_first_last["end"] - geo_first_last["start"]
    movers = geo_first_last.sort_values("change", ascending=False).head(15)
    bar = px.bar(
        movers,
        x="geography",
        y="change",
        labels={"geography": "Geography", "change": "PD change"},
    )
    bar.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(bar, use_container_width=True)

    st.markdown("### Latest PD by geography")
    latest_month = merged["month"].max()
    latest = geo_summary[geo_summary["month"] == latest_month].rename(columns={"pd_value": "average_pd"})
    st.dataframe(latest, use_container_width=True, hide_index=True)

    export_controls(
        "macro_linkage",
        dataframes={
            "portfolio_trend": monthly_trend,
            "geo_trend": geo_summary,
            "geo_movers": geo_first_last,
        },
    )

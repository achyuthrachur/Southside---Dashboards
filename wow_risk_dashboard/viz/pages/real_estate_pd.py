"""
Interactive Real Estate risk heatmap for Southside Bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from wow_risk_dashboard.components import (
    HeaderExpectation,
    PageInputConfig,
    export_controls,
    load_input_dataframe,
    render_inputs_panel,
)

PAGE_KEY = "real_estate_pd"

INPUT_CONFIGS = [
    PageInputConfig(
        key="reference_current",
        title="Instrument Reference",
        dataset_key="instrument_reference",
        required=True,
        description=(
            "Instrument characteristics, geography, and segmentation attributes "
            "for the selected quarter."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifier",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Portfolio identifier",
                candidates=["portfolioIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="Geography",
                candidates=["geographyCode", "borrowerZipCode", "collateralZipCode"],
                required=False,
                match="any",
                note="CBSA when available, ZIP fallback otherwise.",
            ),
            HeaderExpectation(
                name="State",
                candidates=["borrowerState", "collateralState"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Occupancy",
                candidates=["occupancyStatus"],
                required=False,
            ),
            HeaderExpectation(
                name="Property grouping",
                candidates=["propertyStatus", "loanPropertyGroupIdentifier", "assetClass"],
                required=False,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="result_current",
        title="Instrument Result",
        dataset_key="instrument_result",
        required=True,
        description=(
            "Credit quality metrics (PD, LGD) and balances for the same quarter."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifier",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Portfolio identifier",
                candidates=["portfolioIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="One-year PD",
                candidates=["annualizedPDOneYear"],
                required=True,
            ),
            HeaderExpectation(
                name="Lifetime LGD",
                candidates=["lgdLifetime"],
                required=True,
            ),
            HeaderExpectation(
                name="Amortized cost",
                candidates=["amortizedCost"],
                required=True,
            ),
        ],
    ),
]


@dataclass
class HeatmapData:
    frame: pd.DataFrame
    state_summary: pd.DataFrame
    metric_columns: Dict[str, str]
    tooltip_fields: List[str]


def _render_readiness(panel_state) -> bool:
    missing_files = panel_state.missing_required_files
    missing_headers = panel_state.missing_required_headers
    if not missing_files and not missing_headers:
        return True

    messages: List[str] = []
    if missing_files:
        messages.append(
            "Missing required file(s): " + ", ".join(f"{title}" for title in missing_files)
        )
    if missing_headers:
        details = [
            f"- **{title}**: {', '.join(headers)}"
            for title, headers in missing_headers.items()
        ]
        messages.append("Missing required column(s):\n" + "\n".join(details))
    st.warning("Southside Bank heatmap inputs are incomplete.\n\n" + "\n".join(messages))
    return False


def _get_selected_column(status, canonical: str) -> Optional[str]:
    return status.selected_columns.get(canonical)


def _load_reference_dataframe(status) -> pd.DataFrame:
    columns = set(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns))
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    return df


def _load_result_dataframe(status) -> pd.DataFrame:
    columns = set(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns))
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    return df


def _normalize_state(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.upper()
        .str.strip()
        .str.extract(r"([A-Z]{2})", expand=False)
    )


def _map_occupancy(raw: pd.Series) -> pd.Series:
    mapping = {
        "owner": "Owner-occupied",
        "owner occupied": "Owner-occupied",
        "owner-occupied": "Owner-occupied",
        "owner occupied property": "Owner-occupied",
        "non-owner": "Non-owner-occupied",
        "non owner": "Non-owner-occupied",
        "non-owner-occupied": "Non-owner-occupied",
        "tenant": "Non-owner-occupied",
    }
    normalized = raw.fillna("").str.lower().str.strip()
    return normalized.map(mapping).fillna("Unknown")


def _choose_property_group(row: pd.Series) -> str:
    for field in ["propertyStatus", "loanPropertyGroupIdentifier", "assetClass"]:
        value = row.get(field)
        if pd.notna(value) and str(value).strip():
            return str(value)
    return "Unclassified"


def _derive_quarter(df: pd.DataFrame) -> pd.Series:
    """
    Determine the reporting quarter using any reporting/as-of date columns present.
    """
    quarter = pd.Series(pd.Period("1970Q1"), index=df.index, dtype="object")
    quarter[:] = pd.NaT
    candidate_columns = [
        column
        for column in df.columns
        if column.startswith("reportingDate") or column.startswith("asOfDate")
    ]
    for column in candidate_columns:
        dates = pd.to_datetime(df[column], errors="coerce")
        mask = quarter.isna() & dates.notna()
        quarter.loc[mask] = dates.loc[mask].dt.to_period("Q")
    return quarter


def _summarize_by_state(frame: pd.DataFrame) -> pd.DataFrame:
    summary = (
        frame.groupby("state", dropna=True)
        .agg(
            avg_pd=("annualizedPDOneYear", "mean"),
            avg_lgd=("lgdLifetime", "mean"),
            exposure=("amortizedCost", "sum"),
            instrument_count=("instrumentIdentifier", "nunique"),
        )
        .reset_index()
    )
    total_exposure = summary["exposure"].sum()
    if total_exposure > 0:
        summary["exposure_share"] = summary["exposure"] / total_exposure
    else:
        summary["exposure_share"] = np.nan
    return summary


def _prepare_heatmap_data(panel_state) -> HeatmapData:
    reference_status = panel_state.statuses["reference_current"]
    result_status = panel_state.statuses["result_current"]

    ref_df = _load_reference_dataframe(reference_status)
    res_df = _load_result_dataframe(result_status)

    merged = pd.merge(ref_df, res_df, on="instrumentIdentifier", how="inner", suffixes=("_ref", "_res"))

    merged["state"] = _normalize_state(
        merged["borrowerState"].where(merged["borrowerState"].notna(), merged.get("collateralState"))
    )
    merged = merged[merged["state"].notna()]

    merged["occupancy"] = _map_occupancy(merged.get("occupancyStatus"))
    merged["propertyGroup"] = merged.apply(_choose_property_group, axis=1)

    merged["quarter"] = _derive_quarter(merged)

    for column in ["annualizedPDOneYear", "lgdLifetime", "amortizedCost"]:
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce")

    merged = merged.dropna(subset=["annualizedPDOneYear", "lgdLifetime", "amortizedCost"], how="all")

    state_summary = _summarize_by_state(merged)

    metric_columns = {
        "Average PD (1Y)": "avg_pd",
        "Average LGD (Lifetime)": "avg_lgd",
        "Exposure Share": "exposure_share",
    }
    tooltip_fields = [
        "avg_pd",
        "avg_lgd",
        "exposure",
        "exposure_share",
        "instrument_count",
    ]

    return HeatmapData(merged, state_summary, metric_columns, tooltip_fields)


def _apply_filters(data: HeatmapData, filters: Dict[str, str]) -> HeatmapData:
    frame = data.frame.copy()
    quarter_filter = filters.get("quarter", "Auto-detect")
    if quarter_filter and quarter_filter != "Auto-detect" and "quarter" in frame.columns:
        cleaned = quarter_filter.replace(" ", "").upper()
        normalized_quarter = cleaned
        if cleaned.startswith("Q") and len(cleaned) >= 5:
            quarter_number = cleaned[1]
            year = cleaned[-4:]
            normalized_quarter = f"{year}Q{quarter_number}"
        mask = frame["quarter"].astype(str) == normalized_quarter
        frame = frame[mask]

    occupancy_filter = filters.get("occupancy", "All")
    if occupancy_filter and occupancy_filter != "All":
        frame = frame[frame["occupancy"] == occupancy_filter]

    portfolio_filter = filters.get("portfolio", "All portfolios")
    if portfolio_filter and portfolio_filter != "All portfolios":
        requested = {p.strip().lower() for p in portfolio_filter.split(",") if p.strip()}
        if requested:
            portfolio_column = None
            for candidate in ["portfolioIdentifier_ref", "portfolioIdentifier_res", "portfolioIdentifier"]:
                if candidate in frame.columns:
                    portfolio_column = candidate
                    break
            if portfolio_column:
                frame = frame[
                    frame[portfolio_column]
                    .fillna("")
                    .str.lower()
                    .isin(requested)
                ]

    property_filter = filters.get("property_group", "All property groups")
    if property_filter and property_filter != "All property groups":
        requested = {p.strip().lower() for p in property_filter.split(",") if p.strip()}
        if requested:
            frame = frame[
                frame["propertyGroup"]
                .fillna("")
                .str.lower()
                .isin(requested)
            ]

    state_summary = _summarize_by_state(frame)
    return HeatmapData(frame, state_summary, data.metric_columns, data.tooltip_fields)


def _render_kpis(summary: pd.DataFrame) -> None:
    total_instruments = int(summary["instrument_count"].sum())
    avg_pd = summary["avg_pd"].mean()
    avg_lgd = summary["avg_lgd"].mean()
    total_exposure = summary["exposure"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Instruments", f"{total_instruments:,}")
    col2.metric("Average PD (1Y)", f"{avg_pd:.2%}" if pd.notna(avg_pd) else "N/A")
    col3.metric("Average LGD", f"{avg_lgd:.2%}" if pd.notna(avg_lgd) else "N/A")
    col4.metric("Total Amortized Cost", f"")


def _render_heatmap(summary: pd.DataFrame, metric_label: str, metric_column: str) -> None:
    if summary.empty:
        st.warning("No data available after applying filters.")
        return

    color_scale = {
        "avg_pd": "PuBu",
        "avg_lgd": "Reds",
        "exposure_share": "Viridis",
    }[metric_column]

    fig = px.choropleth(
        summary,
        locations="state",
        locationmode="USA-states",
        color=metric_column,
        scope="usa",
        color_continuous_scale=color_scale,
        labels={
            "avg_pd": "Avg PD (1Y)",
            "avg_lgd": "Avg LGD",
            "exposure_share": "Exposure Share",
        },
        hover_data={
            "avg_pd": ":.2%",
            "avg_lgd": ":.2%",
            "exposure_share": ":.1%",
            "exposure": ":,.0f",
            "instrument_count": ":,",
        },
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(title=metric_label))
    st.plotly_chart(fig, use_container_width=True)


def _render_detail_table(summary: pd.DataFrame) -> None:
    display = summary.copy()
    display = display.sort_values("exposure", ascending=False)
    display["avg_pd"] = display["avg_pd"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    display["avg_lgd"] = display["avg_lgd"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    display["exposure_share"] = display["exposure_share"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    display = display.rename(
        columns={
            "state": "State",
            "avg_pd": "Avg PD (1Y)",
            "avg_lgd": "Avg LGD",
            "exposure": "Amortized Cost",
            "exposure_share": "Exposure Share",
            "instrument_count": "Instruments",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_real_estate_pd_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    base_data = _prepare_heatmap_data(panel_state)
    filtered_data = _apply_filters(base_data, filters)

    _render_kpis(filtered_data.state_summary)

    metric_label = st.segmented_control(
        "View",
        options=list(filtered_data.metric_columns.keys()),
        default="Average PD (1Y)",
    )
    metric_column = filtered_data.metric_columns[metric_label]

    if filters.get("geography") == "CBSA":
        st.info(
            "CBSA-level mapping will be introduced in a future update. Displaying state-level aggregates instead."
        )

    _render_heatmap(filtered_data.state_summary, metric_label, metric_column)

    st.markdown("### State Detail")
    _render_detail_table(filtered_data.state_summary)

    export_controls("real_estate_pd")

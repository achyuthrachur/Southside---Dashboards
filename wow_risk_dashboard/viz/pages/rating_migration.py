"""
Streamlit page for the Southside Bank risk rating migration analysis.
"""

from __future__ import annotations

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
from wow_risk_dashboard.io.schemas import PD_PRIORITY, RATING_PRIORITY
from wow_risk_dashboard.transforms.metrics import build_rating_migration

PAGE_KEY = "rating_migration"
RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
RATING_RANK = {value: idx for idx, value in enumerate(RATING_ORDER)}

INPUT_CONFIGS = [
    PageInputConfig(
        key="result_q2_2023",
        title="Instrument Result - Q2 2023",
        dataset_key="instrument_result",
        required=True,
        description="Starting-point classifications for the Q2 2023 cohort.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=True,
                match="all",
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Risk rating (priority)",
                candidates=[
                    "riskClassification",
                    "longTermRatingFromStageAllocation",
                    "longTermRatingFromStageAllocationScenarioBased",
                ],
                required=True,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="result_q2_2025",
        title="Instrument Result - Q2 2025",
        dataset_key="instrument_result",
        required=True,
        description="End-point classifications for the Q2 2025 cohort.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=True,
                match="all",
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Risk rating (priority)",
                candidates=[
                    "riskClassification",
                    "longTermRatingFromStageAllocation",
                    "longTermRatingFromStageAllocationScenarioBased",
                ],
                required=True,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="risk_q2_2023",
        title="Instrument Risk Metric - Q2 2023 (optional)",
        dataset_key="instrument_risk_metric",
        required=False,
        description="Fallback PD measures used when ratings are missing in Q2 2023.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
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
                required=False,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="risk_q2_2025",
        title="Instrument Risk Metric - Q2 2025 (optional)",
        dataset_key="instrument_risk_metric",
        required=False,
        description="Fallback PD measures used when ratings are missing in Q2 2025.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
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
                required=False,
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
            "Missing required file(s): " + ", ".join(f"`{name}`" for name in missing_files)
        )
    if missing_headers:
        header_lines = [
            f"- **{title}**: {', '.join(headers)}"
            for title, headers in missing_headers.items()
        ]
        lines.append("Missing required column(s):\n" + "\n".join(header_lines))
    st.warning(
        "Southside Bank migration inputs are incomplete.\n\n" + "\n".join(lines)
    )
    return False


def _dates_from_status(status, column_name: Optional[str]) -> pd.Series:
    if not column_name or column_name not in status.selected_columns.values():
        return pd.Series(dtype="datetime64[ns]")
    if not status.file_path:
        return pd.Series(dtype="datetime64[ns]")
    df = load_input_dataframe(status.file_path, (column_name,), encoding=status.encoding)
    return pd.to_datetime(df[column_name], errors="coerce").dropna()


def _validate_quarters(panel_state) -> List[str]:
    errors: List[str] = []
    for status in panel_state.statuses.values():
        if not status.is_loaded:
            continue
        selected = status.selected_columns
        quarter_column = selected.get("reportingDate") or selected.get("asOfDate")
        dates = _dates_from_status(status, quarter_column)
        expected_quarter = "2023Q2" if "2023" in status.config.key else "2025Q2"

        if dates.empty:
            errors.append(
                f"{status.config.title} is missing reporting/as-of date columns needed "
                "for quarter validation."
            )
            continue

        quarter_values = dates.dt.to_period("Q").unique()
        if len(quarter_values) != 1:
            errors.append(
                f"{status.config.title} contains multiple quarters ({', '.join(str(q) for q in quarter_values)}). "
                f"Expected {expected_quarter}."
            )
            continue

        if str(quarter_values[0]) != expected_quarter:
            errors.append(
                f"{status.config.title} appears to use {quarter_values[0]} data. "
                f"Expected {expected_quarter}."
            )
    return errors


def _select_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def _load_result(status, period_label: str) -> pd.DataFrame:
    if not status.is_loaded:
        return pd.DataFrame()
    columns = list(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    rating_col = _select_column(df, list(RATING_PRIORITY))
    if rating_col:
        df = df.rename(columns={rating_col: "rating"})
    df["period"] = period_label
    keep = [col for col in ["instrumentIdentifier", "portfolioIdentifier", "rating", "period"] if col in df.columns]
    return df[keep]


def _load_risk_metric(status, period_label: str) -> pd.DataFrame:
    if not status.is_loaded:
        return pd.DataFrame()
    columns = list(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    pd_col = _select_column(df, list(PD_PRIORITY))
    if not pd_col:
        return pd.DataFrame()
    df["period"] = period_label
    df = df.rename(columns={pd_col: "pd_value"})
    keep = [col for col in ["instrumentIdentifier", "pd_value", "period"] if col in df.columns]
    return df[keep]


def _render_transition_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        st.warning("No migration pairs available to render the heatmap.")
        return
    mat = matrix.set_index(matrix.columns[0])
    fig = px.imshow(
        mat,
        labels={"x": "End rating", "y": "Start rating", "color": "Count"},
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_movers(movers: pd.DataFrame) -> None:
    if movers.empty:
        st.info("No instruments with valid start and end ratings.")
        return
    display = movers.copy()
    display = display.rename(
        columns={
            "instrumentIdentifier": "Instrument",
            "start": "Start",
            "end": "End",
            "direction": "Direction",
        }
    )
    columns = ["Instrument", "Start", "End", "Direction"]
    if "magnitude" in display.columns:
        columns.append("magnitude")
    st.dataframe(display[columns], use_container_width=True, hide_index=True)


def render_rating_migration_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    validation_errors = _validate_quarters(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    res_2023 = _load_result(panel_state.statuses["result_q2_2023"], "2023Q2")
    res_2025 = _load_result(panel_state.statuses["result_q2_2025"], "2025Q2")
    risk_2023 = _load_risk_metric(panel_state.statuses["risk_q2_2023"], "2023Q2")
    risk_2025 = _load_risk_metric(panel_state.statuses["risk_q2_2025"], "2025Q2")

    results = pd.concat([res_2023, res_2025], ignore_index=True)
    risk_metrics = pd.concat([risk_2023, risk_2025], ignore_index=True)

    edges, matrix, movers = build_rating_migration(results, risk_metrics)
    if edges.empty:
        st.warning("No overlapping instruments with start and end ratings were found.")
        export_controls("rating_migration")
        return

    total = edges["count"].sum()

    def _rank(value: str) -> int:
        return RATING_RANK.get(str(value), len(RATING_ORDER))

    upgrades = edges[edges.apply(lambda row: _rank(row["end"]) < _rank(row["start"]), axis=1)]["count"].sum()
    downgrades = edges[edges.apply(lambda row: _rank(row["end"]) > _rank(row["start"]), axis=1)]["count"].sum()
    unchanged = total - upgrades - downgrades

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cohort", f"{total:,} instruments")
    c2.metric("Upgrades", f"{upgrades:,}")
    c3.metric("Downgrades", f"{downgrades:,}")
    c4.metric("Unchanged", f"{unchanged:,}")

    st.markdown("### Transition matrix")
    _render_transition_heatmap(matrix)

    st.markdown("### Top movers")
    top_movers = movers.head(25)
    _render_movers(top_movers)

    export_controls(
        "rating_migration",
        dataframes={
            "edges": edges,
            "matrix": matrix,
            "movers": movers,
        },
    )

"""
Streamlit page for the Southside Bank risk rating migration analysis.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from wow_risk_dashboard.components import (
    HeaderExpectation,
    PageInputConfig,
    export_controls,
    render_inputs_panel,
    load_input_dataframe,
)

PAGE_KEY = "rating_migration"

INPUT_CONFIGS = [
    PageInputConfig(
        key="result_q2_2023",
        title="Instrument Result – Q2 2023",
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
        title="Instrument Result – Q2 2025",
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
        title="Instrument Risk Metric – Q2 2023 (optional)",
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
        title="Instrument Risk Metric – Q2 2025 (optional)",
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
    df = load_input_dataframe(status.file_path, (column_name,))
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


def render_rating_migration_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    validation_errors = _validate_quarters(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    st.info(
        "Risk rating migration visuals for Southside Bank will appear here once the "
        "transition analytics are wired to processed datasets."
    )
    export_controls("rating_migration")

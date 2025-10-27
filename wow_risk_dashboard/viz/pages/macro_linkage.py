"""
Streamlit page for Southside Bank macro linkage analytics.
"""

from __future__ import annotations

from datetime import datetime
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


def render_macro_linkage_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    validation_errors = _validate_timespan(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    st.info(
        "Macro linkage dashboards for Southside Bank will be displayed here once "
        "internal PD/LGD trends are joined with external macroeconomic series."
    )
    export_controls("macro_linkage")

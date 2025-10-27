"""
Streamlit page for Southside Bank defaulted cohort analytics.
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

PAGE_KEY = "default_cohorts"
LEAD_MONTHS = 36

INPUT_CONFIGS = [
    PageInputConfig(
        key="chargeoff_events",
        title="Charge-off Events (preferred)",
        dataset_key="chargeoff",
        required=False,
        description="Primary default event source used when available.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Charge-off date",
                candidates=["chargeOffDate", "reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="Charge-off amount",
                candidates=["netChargeOffAmount", "chargeOffAmount"],
                required=False,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="cashflow_events",
        title="Instrument Cash Flow (default inference)",
        dataset_key="instrument_cashflow",
        required=False,
        description=(
            "Used to infer defaults when charge-off files are unavailable. "
            "Requires defaultAmount and cashFlowDate."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Cash flow date",
                candidates=["cashFlowDate"],
                required=False,
            ),
            HeaderExpectation(
                name="Default amount",
                candidates=["defaultAmount"],
                required=False,
            ),
            HeaderExpectation(
                name="Principal recovery",
                candidates=["principalRecoveryAmount"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="risk_metrics_history",
        title="Instrument Risk Metric History",
        dataset_key="instrument_risk_metric",
        required=True,
        description=(
            "Time series of PD/LGD observations sufficient to cover at least 36 months "
            "prior to each default event."
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
        "Southside Bank default cohort inputs are incomplete.\n\n" + "\n".join(lines)
    )
    return False


def _dates_from_dataset(path: Optional[str], column: Optional[str]) -> pd.Series:
    if not path or not column:
        return pd.Series(dtype="datetime64[ns]")
    df = load_input_dataframe(path, (column,))
    return pd.to_datetime(df[column], errors="coerce").dropna()


def _event_dates(panel_state) -> pd.Series:
    chargeoff = panel_state.statuses["chargeoff_events"]
    if chargeoff.is_loaded:
        column = (
            chargeoff.selected_columns.get("chargeOffDate")
            or chargeoff.selected_columns.get("reportingDate")
            or chargeoff.selected_columns.get("asOfDate")
        )
        series = _dates_from_dataset(chargeoff.file_path, column)
        if not series.empty:
            return series

    cashflow = panel_state.statuses["cashflow_events"]
    if cashflow.is_loaded:
        column = cashflow.selected_columns.get("cashFlowDate")
        series = _dates_from_dataset(cashflow.file_path, column)
        if not series.empty:
            return series

    return pd.Series(dtype="datetime64[ns]")


def _validate_history(panel_state) -> List[str]:
    errors: List[str] = []

    events = _event_dates(panel_state)
    if events.empty:
        errors.append(
            "Provide either a charge-off file or a cash flow file with default events "
            "to define the cohort."
        )
        return errors

    risk_status = panel_state.statuses["risk_metrics_history"]
    if not risk_status.is_loaded:
        errors.append("Risk metric history is required to evaluate defaulted cohorts.")
        return errors

    date_column = (
        risk_status.selected_columns.get("reportingDate")
        or risk_status.selected_columns.get("asOfDate")
    )
    risk_dates = _dates_from_dataset(risk_status.file_path, date_column)
    if risk_dates.empty:
        errors.append(
            "Risk metric history lacks valid reporting/as-of dates. Supply the full history."
        )
        return errors

    earliest_event = events.min()
    required_start = earliest_event - pd.DateOffset(months=LEAD_MONTHS)
    if risk_dates.min() > required_start:
        errors.append(
            f"Risk metric history begins on {risk_dates.min().date()}, but defaults as early as "
            f"{earliest_event.date()} require history back to at least {required_start.date()}."
        )
    latest_event = events.max()
    if risk_dates.max() < latest_event:
        errors.append(
            f"Risk metric history ends on {risk_dates.max().date()}, which predates the "
            f"latest default event ({latest_event.date()}). Extend the history."
        )

    return errors


def render_default_cohorts_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    if not (
        panel_state.statuses["chargeoff_events"].is_loaded
        or panel_state.statuses["cashflow_events"].is_loaded
    ):
        st.warning(
            "Upload either the charge-off events file or the instrument cash flow file "
            "to define default cohorts."
        )
        return

    validation_errors = _validate_history(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    st.info(
        "Defaulted cohort visualizations for Southside Bank will appear here once the "
        "event-study pipeline is connected to processed data."
    )
    export_controls("default_cohorts")

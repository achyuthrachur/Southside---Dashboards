"""
Streamlit page for Southside Bank defaulted cohort analytics.
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
from wow_risk_dashboard.transforms.metrics import build_default_cohorts
from wow_risk_dashboard.io.schemas import PD_PRIORITY, DATE_FIELDS, CHARGEOFF_AMOUNT_PRIORITY

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


def _pick_column(df: pd.DataFrame, candidates) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _load_status(status) -> pd.DataFrame:
    if not status.is_loaded:
        return pd.DataFrame()
    columns = list(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    return df.rename(columns=rename_map)


def _prepare_events(chargeoff: pd.DataFrame, cashflow: pd.DataFrame) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    if not chargeoff.empty:
        amount_col = _pick_column(chargeoff, CHARGEOFF_AMOUNT_PRIORITY)
        date_col = _pick_column(chargeoff, DATE_FIELDS)
        if amount_col and date_col:
            df = chargeoff[["instrumentIdentifier", amount_col, date_col]].rename(
                columns={amount_col: "event_amount", date_col: "event_date"}
            )
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
            frames.append(df)
    if not cashflow.empty:
        amount_col = _pick_column(cashflow, ["defaultAmount"])
        date_col = _pick_column(cashflow, DATE_FIELDS)
        if amount_col and date_col:
            df = cashflow[["instrumentIdentifier", amount_col, date_col]].rename(
                columns={amount_col: "event_amount", date_col: "event_date"}
            )
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    events = pd.concat(frames, ignore_index=True)
    return events.dropna(subset=["event_date"])


def _prepare_risk_history(status) -> pd.DataFrame:
    df = _load_status(status)
    if df.empty:
        return df
    pd_col = _pick_column(df, PD_PRIORITY)
    date_col = _pick_column(df, DATE_FIELDS)
    if not pd_col or not date_col:
        return pd.DataFrame()
    df["pd_value"] = pd.to_numeric(df[pd_col], errors="coerce")
    df["obs_date"] = pd.to_datetime(df[date_col], errors="coerce")
    return df[["instrumentIdentifier", "pd_value", "obs_date"]]


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

    chargeoff_df = _load_status(panel_state.statuses["chargeoff_events"])
    cashflow_df = _load_status(panel_state.statuses["cashflow_events"])
    risk_history = _prepare_risk_history(panel_state.statuses["risk_metrics_history"])

    events = _prepare_events(chargeoff_df, cashflow_df)
    if events.empty or risk_history.empty:
        st.warning("Default events or risk metric history are missing after parsing uploads.")
        export_controls("default_cohorts")
        return

    chargeoff_like = events.rename(columns={"event_date": "chargeOffDate"})
    risk_for_metrics = risk_history.rename(columns={"pd_value": "annualizedCumulativePD", "obs_date": "reportingDate"})

    outputs = build_default_cohorts(risk_for_metrics, chargeoff_like)
    if not outputs:
        st.warning("Unable to build cohorts with the provided files.")
        export_controls("default_cohorts")
        return

    st.markdown("### Cohort cadence")
    if not outputs["cohort_summary"].empty:
        st.dataframe(outputs["cohort_summary"], use_container_width=True, hide_index=True)

    st.markdown("### PD path (average)")
    if not outputs["pd_path"].empty:
        fig = px.line(
            outputs["pd_path"],
            x="months_to_default",
            y="pd_value",
            labels={"months_to_default": "Months to default", "pd_value": "Average PD"},
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Latest PD before default")
    st.dataframe(outputs["latest_pd"], use_container_width=True, hide_index=True)

    export_controls(
        "default_cohorts",
        dataframes={
            "events": outputs["events"],
            "pd_path": outputs["pd_path"],
            "cohort_summary": outputs["cohort_summary"],
            "latest_pd": outputs["latest_pd"],
        },
    )

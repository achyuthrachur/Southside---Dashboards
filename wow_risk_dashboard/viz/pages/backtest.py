"""
Streamlit page for the Southside Bank expected vs realized loss backtest.
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

PAGE_KEY = "backtest"
START_2024 = datetime(2024, 1, 1)
END_2024 = datetime(2024, 12, 31)
SNAPSHOT_CUTOFF = datetime(2023, 12, 31)

INPUT_CONFIGS = [
    PageInputConfig(
        key="risk_metric_snapshot",
        title="Instrument Risk Metric – Q4 2023 Snapshot",
        dataset_key="instrument_risk_metric",
        required=True,
        description=(
            "Provides PD/LGD/EAD metrics as of the 2023-12-31 reporting cycle."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Snapshot date",
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
            HeaderExpectation(
                name="Exposure at default",
                candidates=["ead"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="result_snapshot",
        title="Instrument Result – Q4 2023 (optional)",
        dataset_key="instrument_result",
        required=False,
        description="Supplies IFRS EAD amounts when not available in risk metrics.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=False,
                match="all",
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="IFRS EAD Amount",
                candidates=["ifrsEADAmount"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="cashflow_2024",
        title="Instrument Cash Flow – 2024 (optional)",
        dataset_key="instrument_cashflow",
        required=False,
        description="Used to infer realized defaults when charge-off files are unavailable.",
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=False,
                match="all",
            ),
            HeaderExpectation(
                name="Cash flow date",
                candidates=["cashFlowDate"],
                required=False,
            ),
            HeaderExpectation(
                name="Realized defaults",
                candidates=["defaultAmount"],
                required=False,
            ),
            HeaderExpectation(
                name="Exposure on grid",
                candidates=["eadAmount"],
                required=False,
            ),
            HeaderExpectation(
                name="Principal recoveries",
                candidates=["principalRecoveryAmount"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="chargeoff_2024",
        title="Charge-off Events – 2024 (preferred)",
        dataset_key="chargeoff",
        required=False,
        description="Primary source for realized defaults and charge-off timing in 2024.",
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
        "Southside Bank backtest inputs are incomplete.\n\n" + "\n".join(lines)
    )
    return False


def _parse_date_series(df: pd.DataFrame, column: Optional[str]) -> pd.Series:
    if not column or column not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(df[column], errors="coerce")


def _validate_snapshots(panel_state) -> List[str]:
    errors: List[str] = []

    risk_status = panel_state.statuses.get("risk_metric_snapshot")
    if risk_status and risk_status.is_loaded:
        date_column = (
            risk_status.selected_columns.get("reportingDate")
            or risk_status.selected_columns.get("asOfDate")
        )
        if date_column and risk_status.file_path:
            df = load_input_dataframe(risk_status.file_path, (date_column,))
            dates = _parse_date_series(df, date_column)
        else:
            dates = pd.Series(dtype="datetime64[ns]")
        if dates.dropna().empty:
            errors.append(
                "Risk metric snapshot is missing valid reporting/as-of dates for Q4 2023."
            )
        elif dates.max() > SNAPSHOT_CUTOFF:
            errors.append(
                f"Risk metric snapshot includes dates beyond 2023-12-31 ({dates.max().date()}). "
                "Please supply a Q4 2023 snapshot."
            )

    chargeoff_status = panel_state.statuses.get("chargeoff_2024")
    if chargeoff_status and chargeoff_status.is_loaded:
        date_column = (
            chargeoff_status.selected_columns.get("chargeOffDate")
            or chargeoff_status.selected_columns.get("reportingDate")
            or chargeoff_status.selected_columns.get("asOfDate")
        )
        if date_column and chargeoff_status.file_path:
            df = load_input_dataframe(chargeoff_status.file_path, (date_column,))
            dates = _parse_date_series(df, date_column)
        else:
            dates = pd.Series(dtype="datetime64[ns]")
        if dates.dropna().empty:
            errors.append(
                "Charge-off file is missing recognizable charge-off dates for 2024."
            )
        else:
            min_date = dates.min()
            max_date = dates.max()
            if min_date < START_2024 or max_date > END_2024:
                errors.append(
                    f"Charge-off dates span {min_date.date()} to {max_date.date()}. "
                    "Limit the file to events occurring in the 2024 calendar year."
                )
    return errors


def render_backtest_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    chargeoff_loaded = panel_state.statuses["chargeoff_2024"].is_loaded
    cashflow_loaded = panel_state.statuses["cashflow_2024"].is_loaded
    if not (chargeoff_loaded or cashflow_loaded):
        st.warning(
            "Provide either the 2024 charge-off file or the 2024 instrument cash flow "
            "file so realized defaults can be evaluated."
        )
        return

    validation_errors = _validate_snapshots(panel_state)
    if validation_errors:
        for error in validation_errors:
            st.error(error)
        st.stop()

    st.info(
        "Expected vs realized loss analytics for Southside Bank will appear here once "
        "the calibration pipeline is connected to processed data."
    )
    export_controls("backtest_2024")

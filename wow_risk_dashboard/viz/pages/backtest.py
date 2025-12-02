"""
Streamlit page for the Southside Bank expected vs realized loss backtest.
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
from wow_risk_dashboard.io.schemas import PD_PRIORITY, EAD_PRIORITY, LGD_FIELDS, CHARGEOFF_AMOUNT_PRIORITY, DATE_FIELDS

PAGE_KEY = "backtest"
START_2024 = datetime(2024, 1, 1)
END_2024 = datetime(2024, 12, 31)
SNAPSHOT_CUTOFF = datetime(2023, 12, 31)

INPUT_CONFIGS = [
    PageInputConfig(
        key="risk_metric_snapshot",
        title="Instrument Risk Metric - Q4 2023 Snapshot",
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
        title="Instrument Result - Q4 2023 (optional)",
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
        title="Instrument Cash Flow - 2024 (optional)",
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
        title="Charge-off Events - 2024 (preferred)",
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
            df = load_input_dataframe(
                risk_status.file_path,
                (date_column,),
                encoding=risk_status.encoding,
            )
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
            df = load_input_dataframe(
                chargeoff_status.file_path,
                (date_column,),
                encoding=chargeoff_status.encoding,
            )
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


def _prepare_expected_losses(risk_df: pd.DataFrame, result_df: pd.DataFrame) -> pd.DataFrame:
    if risk_df.empty:
        return pd.DataFrame()
    expected = risk_df.copy()
    pd_col = _pick_column(expected, PD_PRIORITY)
    if not pd_col:
        return pd.DataFrame()
    expected["pd_value"] = pd.to_numeric(expected[pd_col], errors="coerce").fillna(0.0)

    lgd_col = _pick_column(expected, LGD_FIELDS)
    expected["lgd_value"] = pd.to_numeric(expected[lgd_col], errors="coerce").fillna(0.45) if lgd_col else 0.45

    ead_col = _pick_column(expected, EAD_PRIORITY)
    if not ead_col and not result_df.empty:
        alt = _pick_column(result_df, EAD_PRIORITY)
        if alt:
            expected = expected.merge(
                result_df[["instrumentIdentifier", alt]],
                on="instrumentIdentifier",
                how="left",
                suffixes=("", "_alt"),
            )
            ead_col = alt
    expected["ead_value"] = pd.to_numeric(expected.get(ead_col, 0), errors="coerce").fillna(0.0)
    expected["expected_loss"] = expected["pd_value"] * expected["lgd_value"] * expected["ead_value"]
    columns = ["instrumentIdentifier"]
    if "portfolioIdentifier" in expected.columns:
        columns.append("portfolioIdentifier")
    columns.extend(["pd_value", "lgd_value", "ead_value", "expected_loss"])
    return expected[columns]


def _prepare_realized_losses(chargeoff_df: pd.DataFrame, cashflow_df: pd.DataFrame) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []

    if not chargeoff_df.empty:
        amount_col = _pick_column(chargeoff_df, CHARGEOFF_AMOUNT_PRIORITY)
        date_col = _pick_column(chargeoff_df, DATE_FIELDS)
        if amount_col and date_col:
            df = chargeoff_df[["instrumentIdentifier", amount_col, date_col]].copy()
            df = df.rename(columns={amount_col: "realized_amount", date_col: "event_date"})
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
            frames.append(df)

    if not cashflow_df.empty:
        amount_col = _pick_column(cashflow_df, ["defaultAmount"])
        recovery_col = _pick_column(cashflow_df, ["principalRecoveryAmount"])
        date_col = _pick_column(cashflow_df, DATE_FIELDS)
        if amount_col and date_col:
            df = cashflow_df[["instrumentIdentifier", amount_col, date_col]].copy()
            df["realized_amount"] = pd.to_numeric(df[amount_col], errors="coerce")
            if recovery_col and recovery_col in cashflow_df.columns:
                df["realized_amount"] = df["realized_amount"] - pd.to_numeric(
                    cashflow_df[recovery_col], errors="coerce"
                ).fillna(0.0)
            df = df.rename(columns={date_col: "event_date"})
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
            frames.append(df[["instrumentIdentifier", "realized_amount", "event_date"]])

    if not frames:
        return pd.DataFrame()

    realized = pd.concat(frames, ignore_index=True)
    realized = realized.dropna(subset=["event_date"])
    realized = realized[
        (realized["event_date"] >= START_2024) & (realized["event_date"] <= END_2024)
    ]
    return realized


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

    risk_df = _load_status(panel_state.statuses["risk_metric_snapshot"])
    result_df = _load_status(panel_state.statuses["result_snapshot"])
    chargeoff_df = _load_status(panel_state.statuses["chargeoff_2024"])
    cashflow_df = _load_status(panel_state.statuses["cashflow_2024"])

    expected = _prepare_expected_losses(risk_df, result_df)
    realized = _prepare_realized_losses(chargeoff_df, cashflow_df)

    if expected.empty and realized.empty:
        st.warning("No expected or realized loss data could be derived from the uploads.")
        export_controls("backtest_2024")
        return

    expected_total = expected["expected_loss"].sum() if not expected.empty else 0.0
    realized_total = realized["realized_amount"].sum() if not realized.empty else 0.0
    coverage = (realized_total / expected_total) if expected_total else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Expected loss (2024 horizon)", f"${expected_total:,.0f}")
    c2.metric("Realized loss (2024)", f"${realized_total:,.0f}")
    c3.metric("Realized / Expected", f"{coverage:.1%}" if coverage is not None else "N/A")

    if not realized.empty:
        timeline = (
            realized.assign(month=lambda df: df["event_date"].dt.to_period("M"))
            .groupby("month")["realized_amount"]
            .sum()
            .reset_index()
        )
        timeline["expected_loss"] = expected_total
        fig = px.bar(
            timeline,
            x="month",
            y="realized_amount",
            labels={"realized_amount": "Realized loss", "month": "Month"},
            title="Realized defaults by month (2024)",
        )
        fig.add_scatter(x=timeline["month"].astype(str), y=timeline["expected_loss"], mode="lines", name="Expected")
        fig.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Instrument detail")
    if expected.empty:
        detail = realized
    elif realized.empty:
        detail = expected
    else:
        detail = expected.merge(realized, on="instrumentIdentifier", how="left")
    st.dataframe(detail, use_container_width=True, hide_index=True)

    export_controls(
        "backtest_2024",
        dataframes={
            "expected": expected,
            "realized": realized,
            "detail": detail,
        },
    )

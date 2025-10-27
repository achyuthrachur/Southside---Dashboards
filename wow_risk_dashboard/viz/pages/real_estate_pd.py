"""
Streamlit page for the Southside Bank real-estate PD heatmap.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st

from wow_risk_dashboard.components import (
    HeaderExpectation,
    PageInputConfig,
    export_controls,
    render_inputs_panel,
)

PAGE_KEY = "real_estate_pd"

INPUT_CONFIGS = [
    PageInputConfig(
        key="reference_current",
        title="Instrument Reference (Current Quarter)",
        dataset_key="instrument_reference",
        required=True,
        description=(
            "Identifies instruments, portfolios, geography, occupancy, and property "
            "attributes for the selected quarter."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifiers",
                candidates=["instrumentIdentifier", "portfolioIdentifier"],
                required=True,
                match="all",
                note="Both identifiers must be present.",
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=True,
                match="any",
                note="reportingDate preferred; falls back to asOfDate.",
            ),
            HeaderExpectation(
                name="Geography (CBSA/ZIP priority)",
                candidates=["geographyCode", "borrowerZipCode", "collateralZipCode"],
                required=True,
                match="any",
                note="Used to map exposures to CBSA; ZIP fallback allowed.",
            ),
            HeaderExpectation(
                name="State fallback",
                candidates=["borrowerState", "collateralState"],
                required=True,
                match="any",
                note="Used when CBSA mapping is unavailable.",
            ),
            HeaderExpectation(
                name="Occupancy status",
                candidates=["occupancyStatus"],
                required=True,
            ),
            HeaderExpectation(
                name="Property grouping",
                candidates=["propertyStatus", "loanPropertyGroupIdentifier", "assetClass"],
                required=True,
                match="any",
                note="At least one property proxy required for segmentation.",
            ),
        ],
    ),
    PageInputConfig(
        key="risk_metric_current",
        title="Instrument Risk Metric (Current Quarter)",
        dataset_key="instrument_risk_metric",
        required=True,
        description=(
            "Provides probability of default, and optionally LGD, for the same quarter "
            "as the reference file."
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
                note="Selected according to Southside Bank PD precedence.",
            ),
            HeaderExpectation(
                name="Loss given default",
                candidates=["lgd"],
                required=False,
            ),
        ],
    ),
    PageInputConfig(
        key="result_current",
        title="Instrument Result (Current Quarter)",
        dataset_key="instrument_result",
        required=False,
        description=(
            "Optional classification file used for overlays such as risk ratings or "
            "exposure metrics."
        ),
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
                name="Risk rating",
                candidates=[
                    "riskClassification",
                    "longTermRatingFromStageAllocation",
                    "longTermRatingFromStageAllocationScenarioBased",
                ],
                required=False,
                match="any",
            ),
        ],
    ),
]


def _render_readiness(panel_state) -> bool:
    """
    Show guidance when required inputs are missing. Returns True when ready.
    """
    missing_files = panel_state.missing_required_files
    missing_headers = panel_state.missing_required_headers

    if not missing_files and not missing_headers:
        return True

    message_lines = []
    if missing_files:
        message_lines.append(
            "Missing required file(s): " + ", ".join(f"`{name}`" for name in missing_files)
        )
    if missing_headers:
        header_lines = [
            f"- **{title}**: {', '.join(headers)}"
            for title, headers in missing_headers.items()
        ]
        message_lines.append(
            "Missing required column(s):\n" + "\n".join(header_lines)
        )

    st.warning(
        "Southside Bank heatmap inputs are incomplete.\n\n" + "\n".join(message_lines)
    )
    return False


def render_real_estate_pd_page(filters: Dict[str, str]) -> None:
    """
    Render the Real Estate PD heatmap page.
    """
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    st.info(
        "Visualizations for the Southside Bank real-estate PD heatmap will appear here "
        "after the analytics pipeline is connected to processed data."
    )
    export_controls("real_estate_pd")

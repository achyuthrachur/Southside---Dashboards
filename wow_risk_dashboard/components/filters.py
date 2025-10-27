"""
Global filter controls shared across Streamlit pages.
"""

from __future__ import annotations

from typing import Dict, List

import streamlit as st


def render_global_filters() -> Dict[str, object]:
    """Render sidebar filters and return current selections."""
    st.sidebar.header("Southside Bank Filters")

    quarter = st.sidebar.selectbox(
        "Quarter",
        options=[
            "Auto-detect",
            "Q1 2023",
            "Q2 2023",
            "Q3 2023",
            "Q4 2023",
            "Q1 2024",
            "Q2 2024",
            "Q3 2024",
            "Q4 2024",
            "Q1 2025",
            "Q2 2025",
        ],
        index=0,
        help="Select the focus quarter once data is loaded.",
    )

    available_portfolios: List[str] = st.session_state.get("southside_portfolios", [])
    if available_portfolios:
        default_selection = st.session_state.get("southside_selected_portfolios", available_portfolios)
        portfolio_selection = st.sidebar.multiselect(
            "Portfolios",
            options=available_portfolios,
            default=default_selection,
            help="Choose one or more portfolios to focus analysis. Leave all selected to view the full book.",
        )
        st.session_state["southside_selected_portfolios"] = portfolio_selection
    else:
        portfolio_selection = []

    geography = st.sidebar.selectbox(
        "Geography level",
        options=["State", "CBSA"],
        help="Controls the geographic aggregation used in the visuals.",
    )
    occupancy = st.sidebar.selectbox(
        "Occupancy",
        options=["All", "Owner-occupied", "Non-owner-occupied", "Unknown"],
        help="Filter instruments by occupancy classification.",
    )
    property_group = st.sidebar.text_input(
        "Property grouping",
        value="All property groups",
        help="Enter property group identifiers to focus analyses (optional).",
    )
    only_real_estate = st.sidebar.checkbox(
        "Only real estate exposures",
        value=True,
        help="Restrict analytics to real estate portfolios when enabled.",
    )

    if available_portfolios and portfolio_selection:
        portfolio_label = ",".join(portfolio_selection)
    else:
        portfolio_label = "All portfolios"

    return {
        "quarter": quarter,
        "portfolio": portfolio_label,
        "portfolio_list": portfolio_selection,
        "geography": geography,
        "occupancy": occupancy,
        "property_group": property_group,
        "only_real_estate": only_real_estate,
    }

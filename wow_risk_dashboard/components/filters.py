"""
Global filter controls shared across Streamlit pages.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st


def render_global_filters() -> Dict[str, str]:
    """
    Render sidebar filters and return current selections.
    """
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
    portfolio = st.sidebar.text_input(
        "Portfolio filter",
        value="All portfolios",
        help="Enter comma-separated portfolio identifiers to focus the visuals.",
    )
    geography = st.sidebar.selectbox(
        "Geography level",
        options=["CBSA", "State"],
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
    st.sidebar.checkbox(
        "Only real estate exposures",
        value=True,
        help="Restrict analytics to real estate portfolios when enabled.",
    )

    return {
        "quarter": quarter,
        "portfolio": portfolio,
        "geography": geography,
        "occupancy": occupancy,
        "property_group": property_group,
    }

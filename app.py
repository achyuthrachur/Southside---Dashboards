"""
Entry point for the WOW Risk Dashboard Streamlit application.

This scaffold wires together file ingestion, harmonization, and the five
analytic pages described in the specification. Implementation details will
be fleshed out in subsequent commits.
"""

from __future__ import annotations

import streamlit as st

from wow_risk_dashboard import viz
from wow_risk_dashboard.components import render_global_filters, render_explain_modal


def main() -> None:
    st.set_page_config(
        page_title="WOW Risk Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("WOW Risk Dashboard")
    st.info("Core functionality will be implemented in upcoming iterations.")

    filters = render_global_filters()
    render_explain_modal({})

    tab_labels = [
        "Real Estate PD Heatmap",
        "Risk Rating Migration",
        "Backtest 2024",
        "Macro Linkage",
        "Defaulted Cohorts",
    ]
    pages = [
        viz.render_real_estate_pd_page,
        viz.render_rating_migration_page,
        viz.render_backtest_page,
        viz.render_macro_linkage_page,
        viz.render_default_cohorts_page,
    ]

    tabs = st.tabs(tab_labels)
    for tab, label, page_func in zip(tabs, tab_labels, pages):
        with tab:
            st.subheader(label)
            page_func(None, filters)  # placeholders for forthcoming data objects


if __name__ == "__main__":
    main()

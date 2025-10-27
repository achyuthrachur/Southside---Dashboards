"""
Entry point for the Southside Bank Risk Dashboard Streamlit application.

The application hosts five analytical pages. Each page manages its own file
ingestion requirements, validation logic, and visualization placeholders.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import streamlit as st

from wow_risk_dashboard import viz
from wow_risk_dashboard.components import render_explain_modal, render_global_filters

PAGE_DEFINITIONS: List[Tuple[str, str, callable]] = [
    ("real_estate_pd", "Real Estate PD Heatmap", viz.render_real_estate_pd_page),
    ("rating_migration", "Risk Rating Migration", viz.render_rating_migration_page),
    ("backtest", "Backtest 2024", viz.render_backtest_page),
    ("macro_linkage", "Macro Linkage", viz.render_macro_linkage_page),
    ("default_cohorts", "Defaulted Cohorts", viz.render_default_cohorts_page),
]

PAGE_TITLE_MAP: Dict[str, str] = {key: title for key, title, _ in PAGE_DEFINITIONS}


def main() -> None:
    st.set_page_config(
        page_title="Southside Bank Risk Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Southside Bank Risk Dashboard")
    st.caption(
        "Upload the requested files on each page to unlock Southside Bank's risk "
        "analytics. The Explain Data panel summarizes which columns are used."
    )

    filters = render_global_filters()
    render_explain_modal(PAGE_TITLE_MAP)

    tab_labels = [title for _, title, _ in PAGE_DEFINITIONS]
    tabs = st.tabs(tab_labels)
    for (page_key, title, render_fn), tab in zip(PAGE_DEFINITIONS, tabs):
        with tab:
            st.subheader(title)
            try:
                render_fn(filters)
            except Exception as exc:  # pragma: no cover - diagnostic surfacing
                st.error(
                    f"An error occurred while rendering **{title}**: {exc}"
                )
                st.exception(exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

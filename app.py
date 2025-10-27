"""
Entry point for the WOW Risk Dashboard Streamlit application.

This scaffold wires together file ingestion, harmonization, and the five
analytic pages described in the specification. Implementation details will
be fleshed out in subsequent commits.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import streamlit as st

from wow_risk_dashboard import viz
from wow_risk_dashboard.components import render_explain_modal, render_global_filters
from wow_risk_dashboard.io import DATASET_SPECS, LoadedFile, load_uploaded_files

logger = logging.getLogger(__name__)


def _handle_file_uploads() -> Dict[str, List[LoadedFile]]:
    """Render the uploader control and return detected datasets."""
    uploaded_files = st.sidebar.file_uploader(
        "Upload quarterly WOW CSV files",
        type=["csv"],
        accept_multiple_files=True,
        help="Drag and drop the instrument and charge-off CSV extracts.",
    )

    if not uploaded_files:
        return {}

    payload = {uploaded_file.name: uploaded_file.getvalue() for uploaded_file in uploaded_files}

    try:
        loaded = load_uploaded_files(payload)
    except ValueError as exc:
        st.error(str(exc))
        logger.exception("Failed to ingest uploaded files")
        return {}

    total_files = sum(len(items) for items in loaded.values())
    st.sidebar.success(f"Detected {total_files} file(s) across {len(loaded)} dataset types.")

    for dataset_key, records in loaded.items():
        spec_name = DATASET_SPECS[dataset_key].display_name
        with st.expander(f"{spec_name} ({len(records)} file{'s' if len(records) != 1 else ''})", expanded=False):
            for record in records:
                diagnostics = record.diagnostics
                st.markdown(f"**{record.file_name}** - {diagnostics.get('row_count', 0)} rows")
                if diagnostics.get("matched_required"):
                    st.write("Matched required headers:", diagnostics["matched_required"])
                if diagnostics.get("matched_optional"):
                    st.write("Matched optional headers:", diagnostics["matched_optional"])
                header_sample = diagnostics.get("header_sample", [])
                if header_sample:
                    st.write("Header sample:", ", ".join(header_sample))
    return loaded


def main() -> None:
    st.set_page_config(
        page_title="WOW Risk Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("WOW Risk Dashboard")

    loaded = _handle_file_uploads()
    filters = render_global_filters()
    render_explain_modal({})

    if not loaded:
        st.info("Upload quarterly CSV files to begin exploring WOW risk analytics.")

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
            page_func(loaded, filters)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

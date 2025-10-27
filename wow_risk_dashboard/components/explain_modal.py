"""
Explain Data modal describing column usage and selection logic.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st


def render_explain_modal(page_titles: Dict[str, str]) -> None:
    """
    Render the Explain Data modal content using session-state provenance.
    """
    explain_state: Dict[str, Dict[str, Dict[str, str]]] = st.session_state.get(
        "southside_explain", {}
    )
    with st.expander("Explain Data", expanded=False):
        if not explain_state:
            st.write(
                "Upload files for any Southside Bank page to see the exact columns and "
                "field priorities used in the calculations."
            )
            return

        for page_key, datasets in explain_state.items():
            title = page_titles.get(page_key, page_key.replace("_", " ").title())
            st.markdown(f"**{title}**")
            if not datasets:
                st.caption("No files loaded yet.")
                continue

            for input_key, info in datasets.items():
                file_name = info.get("file_name")
                dataset_key = info.get("dataset_key")
                selected = info.get("selected_columns", {})
                missing = info.get("missing_headers", [])
                row_count = info.get("row_count")

                st.markdown(
                    f"- `{dataset_key}` → **{file_name or 'unavailable'}** "
                    f"({row_count or 0:,} rows)"
                )
                if selected:
                    st.write(
                        "  - Columns selected:",
                        ", ".join(f"{canonical} ⇢ {actual}" for canonical, actual in selected.items()),
                    )
                if missing:
                    st.write(
                        "  - Missing headers:",
                        ", ".join(missing),
                    )

"""
Explain Data modal describing column usage and selection logic.
"""

from __future__ import annotations

from typing import Dict

import streamlit as st


def render_explain_modal(column_map: Dict[str, Dict[str, str]]) -> None:
    """
    Render the Explain Data modal content.
    """
    with st.expander("Explain data (coming soon)", expanded=False):
        st.write(
            "Column provenance and PD selection priority will appear here "
            "once implemented."
        )

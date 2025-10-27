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
    st.sidebar.warning("Global filters will be implemented soon.")
    return {}

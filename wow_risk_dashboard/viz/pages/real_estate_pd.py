"""
Streamlit page for the real-estate PD heatmap.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_real_estate_pd_page(
    harmonized_data: pd.DataFrame,
    filters: dict,
) -> None:
    """
    Render the Real Estate PD US Heatmap page.
    """
    st.warning("Real Estate PD page is under construction.")

"""
Streamlit page for expected vs realized loss backtesting.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_backtest_page(
    backtest_data: dict,
    filters: dict,
) -> None:
    """
    Render the Backtest (Realizations in 2024) page.
    """
    st.warning("Backtest page is under construction.")

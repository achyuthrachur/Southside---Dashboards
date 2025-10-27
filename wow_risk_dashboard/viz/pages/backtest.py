"""
Streamlit page for expected vs realized loss backtesting.
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_backtest_page(
    backtest_data: Any,
    filters: dict,
) -> None:
    """
    Render the Backtest (Realizations in 2024) page.
    """
    st.warning("Backtest page is under construction.")

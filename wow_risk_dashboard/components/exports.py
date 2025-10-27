"""
Export controls for downloading visual outputs and data.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import streamlit as st


def export_controls(
    export_key: str,
    dataframes: Optional[Dict[str, pd.DataFrame]] = None,
) -> None:
    """
    Render export buttons for CSV/PNG downloads.
    """
    with st.expander("Exports", expanded=False):
        st.write(
            "Download-ready CSV and PNG outputs will appear here once the "
            "Southside Bank analytics are connected to processed data."
        )

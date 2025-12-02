"""
Export controls for downloading visual outputs and data.
"""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import streamlit as st
from wow_risk_dashboard.io.paths import ensure_processed_dirs, get_processed_path


def export_controls(
    export_key: str,
    dataframes: Optional[Dict[str, pd.DataFrame]] = None,
    persist: bool = True,
) -> None:
    """
    Render export buttons for CSV/PNG downloads.
    """
    with st.expander("Exports", expanded=False):
        if not dataframes:
            st.write(
                "Download-ready CSV outputs will appear here once the Southside Bank analytics produce data."
            )
            return

        ensure_processed_dirs()

        for name, df in dataframes.items():
            if df is None or df.empty:
                st.caption(f"{name}: no data available to export yet.")
                continue

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            label = f"Download {name} (CSV)"
            st.download_button(
                label=label,
                data=csv_bytes,
                file_name=f"{export_key}__{name}.csv",
                mime="text/csv",
                key=f"{export_key}_{name}_download",
            )

            if persist:
                path = get_processed_path(f"{export_key}__{name}")
                try:
                    df.to_parquet(path, index=False)
                    st.caption(f"Saved to {path}")
                except Exception as exc:  # pragma: no cover - filesystem guard
                    st.warning(f"Could not persist {name}: {exc}")

"""
Utilities for normalizing headers, detecting file profiles, and loading
uploaded CSV data into typed pandas DataFrames.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple, Any

import pandas as pd


def normalize_headers(columns: Iterable[str]) -> List[str]:
    """
    Normalize column headers by trimming whitespace and standardizing case.

    Returns a list of normalized column names while keeping the original
    order. This helper will underpin header alias management.
    """
    raise NotImplementedError


def detect_file_profile(
    file_name: str,
    sample_headers: Iterable[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Determine the dataset type based on filename patterns and header analysis.

    Returns the detected dataset key alongside diagnostics (e.g., matched
    headers) for logging and UI display.
    """
    raise NotImplementedError


def load_uploaded_files(files: Dict[str, bytes]) -> Dict[str, pd.DataFrame]:
    """
    Load uploaded CSV files into pandas DataFrames keyed by dataset type.

    Parameters
    ----------
    files:
        Mapping of filename to raw bytes from Streamlit's uploader.
    """
    raise NotImplementedError

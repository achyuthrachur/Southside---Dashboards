"""
Data ingestion and persistence utilities for the WOW Risk Dashboard.
"""

from .loader import (
    detect_file_profile,
    load_uploaded_files,
    normalize_headers,
)
from .paths import ensure_processed_dirs, get_processed_path
from .storage import PersistedDataset, DatasetRegistry

__all__ = [
    "detect_file_profile",
    "load_uploaded_files",
    "normalize_headers",
    "ensure_processed_dirs",
    "get_processed_path",
    "PersistedDataset",
    "DatasetRegistry",
]

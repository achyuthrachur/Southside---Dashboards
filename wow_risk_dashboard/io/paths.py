"""
Filesystem helpers for managing processed datasets and cache locations.
"""

from __future__ import annotations

from pathlib import Path

BASE_PROCESSED_DIR = Path("processed")


def ensure_processed_dirs() -> None:
    """Ensure that the processed data directory exists."""
    BASE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def get_processed_path(dataset_name: str) -> Path:
    """
    Return the canonical path for a processed dataset.

    Parameters
    ----------
    dataset_name:
        Logical name of the dataset (e.g., 'instrument_reference').
    """
    return BASE_PROCESSED_DIR / f"{dataset_name}.parquet"

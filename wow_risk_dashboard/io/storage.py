"""
Persistence helpers for managing cached datasets and their metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, List

import pandas as pd


@dataclass
class PersistedDataset:
    """Container capturing dataset metadata and storage location."""

    name: str
    path: Path
    sources: List[str] = field(default_factory=list)
    used_columns: Dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None

    def load(self) -> pd.DataFrame:
        """Load the dataset from disk."""
        return pd.read_parquet(self.path)


class DatasetRegistry:
    """
    Registry tracking datasets that have been processed and persisted.
    """

    def __init__(self) -> None:
        self._datasets: Dict[str, PersistedDataset] = {}

    def add(self, dataset: PersistedDataset) -> None:
        self._datasets[dataset.name] = dataset

    def get(self, name: str) -> Optional[PersistedDataset]:
        return self._datasets.get(name)

    def all(self) -> Dict[str, PersistedDataset]:
        return dict(self._datasets)

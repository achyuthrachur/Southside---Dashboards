"""
Harmonization routines to align disparate instrument datasets onto a canonical
schema for downstream analytics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class HarmonizedDataset:
    """Represents a consolidated snapshot of instrument attributes."""

    reference: pd.DataFrame
    risk_metric: pd.DataFrame
    result: pd.DataFrame
    cashflow: pd.DataFrame
    chargeoff: pd.DataFrame


def select_canonical_fields(df: pd.DataFrame, field_aliases: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Identify available canonical fields according to a prioritized alias map.

    Returns a mapping of canonical field name to the actual column selected
    within the DataFrame.
    """
    raise NotImplementedError


def harmonize_datasets(
    datasets: Dict[str, pd.DataFrame],
) -> Tuple[HarmonizedDataset, Dict[str, Dict[str, str]]]:
    """
    Harmonize the uploaded datasets into canonical tables and track which
    columns were used for each canonical field.
    """
    raise NotImplementedError

"""
Harmonization routines to align disparate instrument datasets onto a canonical
schema for downstream analytics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
from wow_risk_dashboard.io.loader import normalize_headers, normalize_token


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
    selected: Dict[str, str] = {}
    header_map = normalize_headers(df.columns)

    for canonical, aliases in field_aliases.items():
        for alias in aliases:
            token = normalize_token(alias)
            if token in header_map:
                selected[canonical] = header_map[token][0]
                break
    return selected


def harmonize_datasets(
    datasets: Dict[str, pd.DataFrame],
) -> Tuple[HarmonizedDataset, Dict[str, Dict[str, str]]]:
    """
    Harmonize the uploaded datasets into canonical tables and track which
    columns were used for each canonical field.
    """
    from wow_risk_dashboard.io.schemas import DATASET_SPECS

    used_columns: Dict[str, Dict[str, str]] = {}
    aligned: Dict[str, pd.DataFrame] = {}

    for dataset_key, spec in DATASET_SPECS.items():
        frame = datasets.get(dataset_key)
        if frame is None:
            used_columns[dataset_key] = {}
            aligned[dataset_key] = pd.DataFrame()
            continue

        mapping = select_canonical_fields(frame, spec.field_aliases)
        renamed = frame.rename(columns={actual: canonical for canonical, actual in mapping.items()})
        aligned[dataset_key] = renamed
        used_columns[dataset_key] = mapping

    harmonized = HarmonizedDataset(
        reference=aligned.get("instrument_reference", pd.DataFrame()),
        risk_metric=aligned.get("instrument_risk_metric", pd.DataFrame()),
        result=aligned.get("instrument_result", pd.DataFrame()),
        cashflow=aligned.get("instrument_cashflow", pd.DataFrame()),
        chargeoff=aligned.get("chargeoff", pd.DataFrame()),
    )

    return harmonized, used_columns

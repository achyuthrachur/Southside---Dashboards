"""
Utilities for normalizing headers, detecting file profiles, and loading
uploaded CSV data into typed pandas DataFrames.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
import logging
import re
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .schemas import DATASET_SPECS, AliasMap, DatasetSpec

logger = logging.getLogger(__name__)

_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]")


def _normalize_token(value: str) -> str:
    """Return a lowercase token stripped of whitespace and punctuation."""
    return _NORMALIZE_PATTERN.sub("", value.lower())


def normalize_headers(columns: Iterable[str]) -> Dict[str, List[str]]:
    """
    Normalize column headers by trimming whitespace and standardizing case.

    Returns a mapping of normalized token -> list of original column names
    (preserving the first occurrence order).
    """
    normalized: DefaultDict[str, List[str]] = defaultdict(list)
    for column in columns:
        if column is None:
            continue
        trimmed = column.strip()
        if not trimmed:
            continue
        normalized[_normalize_token(trimmed)].append(trimmed)
    return dict(normalized)


def _match_alias(alias_list: Iterable[str], header_map: Dict[str, List[str]]) -> Optional[str]:
    """Return the first header that matches any alias candidate."""
    for alias in alias_list:
        token = _normalize_token(alias)
        if token in header_map:
            return header_map[token][0]
    return None


@dataclass
class LoadedFile:
    dataset_key: str
    file_name: str
    dataframe: pd.DataFrame
    diagnostics: Dict[str, Any]


def _evaluate_dataset(
    spec: DatasetSpec,
    file_name: str,
    header_map: Dict[str, List[str]],
) -> Dict[str, Any]:
    matched_required: Dict[str, str] = {}
    matched_optional: Dict[str, str] = {}
    missing_required: Dict[str, List[str]] = {}

    for field in spec.required_fields:
        match = _match_alias(spec.alias_for(field), header_map)
        if match:
            matched_required[field] = match
        else:
            missing_required[field] = spec.alias_for(field)

    for field in spec.identifying_fields:
        match = _match_alias(spec.alias_for(field), header_map)
        if match:
            matched_optional[field] = match

    filename_bonus = 0
    lowercase_name = file_name.lower()
    if any(lowercase_name.startswith(prefix) for prefix in spec.filename_prefixes):
        filename_bonus = 2
    elif any(prefix in lowercase_name for prefix in spec.filename_prefixes):
        filename_bonus = 1

    score_required = len(matched_required) * 5
    score_optional = len(matched_optional)
    total_score = score_required + score_optional + filename_bonus

    return {
        "spec": spec,
        "matched_required": matched_required,
        "matched_optional": matched_optional,
        "missing_required": missing_required,
        "score_required": score_required,
        "score_optional": score_optional,
        "filename_bonus": filename_bonus,
        "total_score": total_score,
    }


def detect_file_profile(
    file_name: str,
    sample_headers: Iterable[str],
) -> Tuple[str, Dict[str, Any]]:
    """
    Determine the dataset type based on filename patterns and header analysis.

    Returns the detected dataset key alongside diagnostics describing matches.
    """
    header_map = normalize_headers(sample_headers)
    evaluations = [_evaluate_dataset(spec, file_name, header_map) for spec in DATASET_SPECS.values()]

    viable = [
        evaluation
        for evaluation in evaluations
        if len(evaluation["matched_required"]) == len(evaluation["spec"].required_fields)
    ]

    if not viable:
        best_guess = max(evaluations, key=lambda item: item["total_score"])
        spec = best_guess["spec"]
        missing_parts = ", ".join(
            f"{field} (candidates: {', '.join(aliases)})"
            for field, aliases in best_guess["missing_required"].items()
        ) or "required headers"
        raise ValueError(
            f"File '{file_name}' resembles '{spec.display_name}' but is missing required headers: {missing_parts}."
        )

    viable.sort(
        key=lambda item: (
            item["total_score"],
            item["score_required"],
            item["score_optional"],
        ),
        reverse=True,
    )

    best = viable[0]
    diagnostics = {
        "dataset_key": best["spec"].key,
        "display_name": best["spec"].display_name,
        "matched_required": best["matched_required"],
        "matched_optional": best["matched_optional"],
        "filename_bonus": best["filename_bonus"],
        "score": best["total_score"],
        "header_sample": list(sample_headers)[:10],
    }

    identifying_headers = list(best["matched_required"].values()) + list(best["matched_optional"].values())
    logger.info(
        "Detected dataset=%s for file=%s; identifying headers=%s",
        best["spec"].key,
        file_name,
        identifying_headers[:10],
    )

    return best["spec"].key, diagnostics


READ_CSV_KWARGS: Dict[str, Any] = {
    "dtype": str,
    "keep_default_na": False,
    "na_filter": False,
}


def load_uploaded_files(files: Dict[str, bytes]) -> Dict[str, List[LoadedFile]]:
    """
    Load uploaded CSV files into pandas DataFrames keyed by dataset type.

    Parameters
    ----------
    files:
        Mapping of filename to raw bytes from Streamlit's uploader.
    """
    loaded: Dict[str, List[LoadedFile]] = {}

    for file_name, content in files.items():
        if not content:
            logger.warning("File %s is empty; skipping.", file_name)
            continue

        preview_buffer = BytesIO(content)
        try:
            header_frame = pd.read_csv(preview_buffer, nrows=0)
        except Exception as exc:  # pragma: no cover - propagating context
            raise ValueError(f"Unable to read CSV headers for file '{file_name}': {exc}") from exc

        dataset_key, diagnostics = detect_file_profile(file_name, header_frame.columns)

        preview_buffer.seek(0)
        try:
            df = pd.read_csv(preview_buffer, **READ_CSV_KWARGS)
        except Exception as exc:  # pragma: no cover - propagating context
            raise ValueError(f"Unable to load CSV for file '{file_name}': {exc}") from exc

        df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
        diagnostics.update(
            {
                "row_count": len(df),
                "columns": list(df.columns),
            }
        )

        record = LoadedFile(
            dataset_key=dataset_key,
            file_name=file_name,
            dataframe=df,
            diagnostics=diagnostics,
        )
        loaded.setdefault(dataset_key, []).append(record)

    return loaded

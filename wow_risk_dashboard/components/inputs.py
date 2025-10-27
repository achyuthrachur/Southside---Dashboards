"""
Reusable components for rendering Southside Bank page input panels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from wow_risk_dashboard.io import (
    DATASET_SPECS,
    DatasetSpec,
    load_uploaded_files,
    normalize_headers,
    normalize_token,
)


@st.cache_data(show_spinner=False, ttl=None)
def _load_uploaded_bytes(
    cache_key: Tuple[str, str, str, int],
    file_name: str,
    content: bytes,
) -> Dict[str, Dict[str, object]]:
    """
    Read raw CSV bytes and return DataFrames plus diagnostics keyed by dataset type.

    The cache key combines page key, input key, file name, and file size so that
    replacing a file with different contents invalidates the cache automatically.
    """
    loaded = load_uploaded_files({file_name: content})
    result: Dict[str, Dict[str, object]] = {}
    for dataset_key, records in loaded.items():
        if not records:
            continue
        record = records[0]
        result[dataset_key] = {
            "dataframe": record.dataframe,
            "diagnostics": record.diagnostics,
        }
    return result


@dataclass
class HeaderExpectation:
    name: str
    candidates: List[str]
    required: bool = True
    match: str = "all"  # "all" => every candidate must be present, "any" => first match wins
    note: Optional[str] = None


@dataclass
class PageInputConfig:
    key: str
    title: str
    dataset_key: str
    required: bool
    description: str
    expectations: List[HeaderExpectation] = field(default_factory=list)


@dataclass
class InputStatus:
    config: PageInputConfig
    uploaded_file: Optional[str] = None
    dataframe: Optional[pd.DataFrame] = None
    encoding: Optional[str] = None
    row_count: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    missing_headers: List[str] = field(default_factory=list)
    selected_columns: Dict[str, str] = field(default_factory=dict)

    @property
    def is_loaded(self) -> bool:
        return self.dataframe is not None and not self.errors

    @property
    def is_ready(self) -> bool:
        return self.is_loaded and not self.missing_headers


@dataclass
class InputPanelState:
    page_key: str
    statuses: Dict[str, InputStatus]

    @property
    def missing_required_files(self) -> List[str]:
        return [
            status.config.title
            for status in self.statuses.values()
            if status.config.required and not status.is_loaded
        ]

    @property
    def missing_required_headers(self) -> Dict[str, List[str]]:
        return {
            status.config.title: status.missing_headers
            for status in self.statuses.values()
            if status.config.required and status.missing_headers
        }

    @property
    def ready(self) -> bool:
        return not self.missing_required_files and not self.missing_required_headers


def _match_columns(
    spec: DatasetSpec,
    dataframe: pd.DataFrame,
    expectation: HeaderExpectation,
) -> Tuple[Dict[str, str], List[str]]:
    header_map = normalize_headers(dataframe.columns)

    def find_column(canonical: str) -> Optional[str]:
        for alias in spec.alias_for(canonical):
            token = normalize_token(alias)
            if token in header_map:
                return header_map[token][0]
        return None

    selected: Dict[str, str] = {}
    missing: List[str] = []

    if expectation.match == "all":
        for canonical in expectation.candidates:
            column = find_column(canonical)
            if column:
                selected[canonical] = column
            else:
                missing.append(canonical)
    else:  # expectation.match == "any"
        for canonical in expectation.candidates:
            column = find_column(canonical)
            if column:
                selected[canonical] = column
                break
        else:
            if expectation.required:
                missing.append(" / ".join(expectation.candidates))

    return selected, missing


def render_inputs_panel(
    page_key: str,
    configs: List[PageInputConfig],
) -> InputPanelState:
    st.markdown("### Inputs")
    statuses: Dict[str, InputStatus] = {}

    for config in configs:
        spec = DATASET_SPECS[config.dataset_key]
        status = InputStatus(config=config)

        with st.container():
            label = "Required" if config.required else "Optional"
            st.markdown(f"**{config.title}** · _{label}_")
            if config.description:
                st.caption(config.description)

            uploader_key = f"{page_key}_{config.key}_uploader"
            uploaded = st.file_uploader(
                "Drag and drop or browse",
                type=["csv"],
                key=uploader_key,
                help=f"Upload the {config.title.lower()} file.",
            )

            if uploaded is not None:
                status.uploaded_file = uploaded.name
                content = uploaded.getvalue()
                cache_key = (page_key, config.key, uploaded.name, len(content))
                try:
                    cached = _load_uploaded_bytes(cache_key, uploaded.name, content)
                except ValueError as exc:
                    status.errors.append(str(exc))
                else:
                    if config.dataset_key not in cached:
                        detected = ", ".join(cached.keys()) or "none"
                        status.errors.append(
                            f"Detected dataset type(s): {detected}. Expected '{config.dataset_key}'."
                        )
                    else:
                        payload = cached[config.dataset_key]
                        dataframe = payload["dataframe"]
                        diagnostics = payload["diagnostics"]
                        status.dataframe = dataframe
                        status.row_count = len(dataframe)
                        status.encoding = diagnostics.get("encoding")

                        for expectation in config.expectations:
                            selected, missing = _match_columns(spec, dataframe, expectation)
                            status.selected_columns.update(selected)
                            if missing and expectation.required:
                                status.missing_headers.extend(
                                    f"{expectation.name}: {item}" for item in missing
                                )

            statuses[config.key] = status

            if status.errors:
                for error in status.errors:
                    st.error(error)
            elif status.is_loaded:
                details = [f"✅ Loaded — {status.row_count:,} rows"]
                if status.encoding:
                    details.append(f"encoding: {status.encoding}")
                st.success("; ".join(details))
            else:
                icon = "⛔" if config.required else "ℹ️"
                descriptor = "Missing (required)" if config.required else "Missing (optional)"
                st.info(f"{icon} {descriptor}")

            if status.missing_headers:
                st.warning("Missing headers detected: " + "; ".join(status.missing_headers))

            if config.expectations:
                summary_lines = []
                for expectation in config.expectations:
                    requirement = "Required" if expectation.required else "Optional"
                    priority = " → ".join(expectation.candidates)
                    note = f" — {expectation.note}" if expectation.note else ""
                    summary_lines.append(f"- `{expectation.name}` ({requirement}): {priority}{note}")
                st.caption("\n".join(summary_lines))

    state = InputPanelState(page_key=page_key, statuses=statuses)

    explain_state = st.session_state.setdefault("southside_explain", {})
    explain_state[page_key] = {
        key: {
            "file_name": status.uploaded_file,
            "dataset_key": status.config.dataset_key,
            "selected_columns": status.selected_columns,
            "missing_headers": status.missing_headers,
            "row_count": status.row_count,
        }
        for key, status in statuses.items()
        if status.is_loaded
    }

    return state

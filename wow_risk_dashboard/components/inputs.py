"""
Reusable components for rendering per-page input panels with validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from wow_risk_dashboard.io import (
    DATASET_SPECS,
    DatasetSpec,
    LoadedFile,
    load_uploaded_files,
    normalize_headers,
    normalize_token,
)


@dataclass
class HeaderExpectation:
    """
    Represents a set of canonical fields that satisfy a logical requirement.
    """

    name: str
    candidates: List[str]
    required: bool = True
    match: str = "all"  # "all" => every candidate, "any" => at least one candidate
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
    loaded_file: Optional[LoadedFile] = None
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
        missing: List[str] = []
        for status in self.statuses.values():
            if not status.config.required:
                continue
            if not status.is_loaded:
                missing.append(status.config.title)
        return missing

    @property
    def missing_required_headers(self) -> Dict[str, List[str]]:
        report: Dict[str, List[str]] = {}
        for key, status in self.statuses.items():
            if status.config.required and status.missing_headers:
                report[status.config.title] = status.missing_headers
        return report

    @property
    def ready(self) -> bool:
        return not self.missing_required_files and not self.missing_required_headers


def _match_columns(
    spec: DatasetSpec,
    df_columns: List[str],
    expectation: HeaderExpectation,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Return a mapping of canonical field -> actual column for the expectation
    and a list describing missing headers.
    """
    header_map = normalize_headers(df_columns)

    def find_alias(canonical: str) -> Optional[str]:
        for alias in spec.alias_for(canonical):
            token = normalize_token(alias)
            if token in header_map:
                return header_map[token][0]
        return None

    selected: Dict[str, str] = {}
    missing: List[str] = []

    if expectation.match == "all":
        for canonical in expectation.candidates:
            column_name = find_alias(canonical)
            if column_name:
                selected[canonical] = column_name
            else:
                missing.append(canonical)
    else:  # expectation.match == "any"
        for canonical in expectation.candidates:
            column_name = find_alias(canonical)
            if column_name:
                selected[canonical] = column_name
                break
        else:
            if expectation.required:
                missing.append(" / ".join(expectation.candidates))

    return selected, missing


def render_inputs_panel(
    page_key: str,
    configs: List[PageInputConfig],
) -> InputPanelState:
    """
    Render page-specific input controls and return their validation state.
    """
    st.markdown("### Inputs")
    statuses: Dict[str, InputStatus] = {}

    for config in configs:
        spec = DATASET_SPECS[config.dataset_key]
        container = st.container()
        with container:
            requirement_label = "Required" if config.required else "Optional"
            st.markdown(f"**{config.title}** · _{requirement_label}_")
            if config.description:
                st.caption(config.description)

            uploader_key = f"{page_key}_{config.key}_uploader"
            uploaded = st.file_uploader(
                "Drag and drop or browse",
                type=["csv"],
                key=uploader_key,
                help=f"Upload a file matching the {config.title.lower()} specification.",
            )

            status = InputStatus(config=config)

            if uploaded is not None:
                status.uploaded_file = uploaded.name
                content = uploaded.getvalue()
                try:
                    loaded_map = load_uploaded_files({uploaded.name: content})
                except ValueError as exc:
                    status.errors.append(str(exc))
                else:
                    if config.dataset_key not in loaded_map:
                        # If multiple files were detected, choose the first for feedback.
                        detected_keys = ", ".join(loaded_map.keys()) or "none"
                        status.errors.append(
                            f"Detected dataset type(s): {detected_keys}. Expected '{config.dataset_key}'."
                        )
                    else:
                        record = loaded_map[config.dataset_key][0]
                        status.loaded_file = record
                        status.dataframe = record.dataframe
                        status.row_count = len(record.dataframe)
                        status.encoding = record.diagnostics.get("encoding")

                        for expectation in config.expectations:
                            selected, missing = _match_columns(
                                spec,
                                record.dataframe.columns.tolist(),
                                expectation,
                            )
                            status.selected_columns.update(selected)
                            if missing and expectation.required:
                                status.missing_headers.extend(
                                    f"{expectation.name}: {item}" for item in missing
                                )

            statuses[config.key] = status

            # Status messaging
            if status.errors:
                for error in status.errors:
                    st.error(error)
            elif status.is_loaded:
                info_parts = [f"✅ Loaded — {status.row_count:,} rows"]
                if status.encoding:
                    info_parts.append(f"encoding: {status.encoding}")
                st.success("; ".join(info_parts))
            else:
                icon = "⛔" if config.required else "ℹ️"
                label = "Missing (required)" if config.required else "Missing (optional)"
                st.info(f"{icon} {label}")

            if status.missing_headers:
                st.warning(
                    "Missing headers detected: "
                    + "; ".join(status.missing_headers)
                )

            # Header expectations summary
            if config.expectations:
                lines = []
                for expectation in config.expectations:
                    requirement = "Required" if expectation.required else "Optional"
                    priority = " → ".join(expectation.candidates)
                    note = f" — {expectation.note}" if expectation.note else ""
                    lines.append(f"- `{expectation.name}` ({requirement}): {priority}{note}")
                st.caption("\n".join(lines))

    state = InputPanelState(page_key=page_key, statuses=statuses)

    # Persist diagnostic information for explain modal reference.
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

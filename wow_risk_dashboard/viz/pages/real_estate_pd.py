"""
Interactive Real Estate risk heatmap for Southside Bank.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PACKAGE_ROOT.parent
CBSA_GEOJSON_PATH = PROJECT_ROOT / "data" / "cbsa.geojson"
CBSA_METADATA_PATH = PROJECT_ROOT / "data" / "cbsa_metadata.csv"
CBSA_FEATURE_FOLDER = PROJECT_ROOT / "cbsa_json_per_cbsa"
CBSA_SHAPEFILE_PATH = PROJECT_ROOT / "tl_2023_us_cbsa" / "tl_2023_us_cbsa.shp"

from wow_risk_dashboard.components import (
    HeaderExpectation,
    PageInputConfig,
    export_controls,
    load_input_dataframe,
    render_inputs_panel,
)

STATE_ABBREVIATIONS = {
    "ALABAMA": "AL",
    "ALASKA": "AK",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC",
    "WASHINGTON DC": "DC",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "HAWAII": "HI",
    "IDAHO": "ID",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "MONTANA": "MT",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM",
    "NEW YORK": "NY",
    "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VERMONT": "VT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI",
    "WYOMING": "WY",
    "PUERTO RICO": "PR",
    "GUAM": "GU",
    "NORTHERN MARIANA ISLANDS": "MP",
    "AMERICAN SAMOA": "AS",
    "US VIRGIN ISLANDS": "VI",
}
STATE_ABBREVIATION_SET: Set[str] = set(STATE_ABBREVIATIONS.values())
PLOTLY_STATE_EXCLUSIONS: Set[str] = {"AS", "GU", "MP", "PR", "VI"}
PLOTLY_STATE_CODES: Tuple[str, ...] = tuple(
    sorted(code for code in STATE_ABBREVIATION_SET if code not in PLOTLY_STATE_EXCLUSIONS)
)
CBSA_COLUMN_CANDIDATES: Tuple[str, ...] = (
    "geographyCode",
    "cbsaIdentifier",
    "cbsaCode",
    "cbsa",
    "msaCode",
    "msa",
)
ESSENTIAL_COLUMNS: Set[str] = {
    "instrumentIdentifier",
    "portfolioIdentifier",
    "scenarioIdentifier",
    "geographyCode",
    "borrowerState",
    "collateralState",
    "occupancyStatus",
    "propertyStatus",
    "loanPropertyGroupIdentifier",
    "assetClass",
    "annualizedPDOneYear",
    "lgdLifetime",
    "amortizedCost",
}

PAGE_KEY = "real_estate_pd"

INPUT_CONFIGS = [
    PageInputConfig(
        key="reference_current",
        title="Instrument Reference",
        dataset_key="instrument_reference",
        required=True,
        description=(
            "Instrument characteristics, geography, and segmentation attributes "
            "for the selected quarter."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifier",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Portfolio identifier",
                candidates=["portfolioIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="Geography",
                candidates=["geographyCode", "borrowerZipCode", "collateralZipCode"],
                required=False,
                match="any",
                note="CBSA when available, ZIP fallback otherwise.",
            ),
            HeaderExpectation(
                name="State",
                candidates=["borrowerState", "collateralState"],
                required=True,
                match="any",
            ),
            HeaderExpectation(
                name="Occupancy",
                candidates=["occupancyStatus"],
                required=False,
            ),
            HeaderExpectation(
                name="Property grouping",
                candidates=["propertyStatus", "loanPropertyGroupIdentifier", "assetClass"],
                required=False,
                match="any",
            ),
        ],
    ),
    PageInputConfig(
        key="result_current",
        title="Instrument Result",
        dataset_key="instrument_result",
        required=True,
        description=(
            "Credit quality metrics (PD, LGD) and balances for the same quarter."
        ),
        expectations=[
            HeaderExpectation(
                name="Instrument identifier",
                candidates=["instrumentIdentifier"],
                required=True,
            ),
            HeaderExpectation(
                name="Portfolio identifier",
                candidates=["portfolioIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="Snapshot date",
                candidates=["reportingDate", "asOfDate"],
                required=False,
                match="any",
            ),
            HeaderExpectation(
                name="Scenario identifier",
                candidates=["scenarioIdentifier"],
                required=False,
            ),
            HeaderExpectation(
                name="One-year PD",
                candidates=["annualizedPDOneYear"],
                required=True,
            ),
            HeaderExpectation(
                name="Lifetime LGD",
                candidates=["lgdLifetime"],
                required=True,
            ),
            HeaderExpectation(
                name="Amortized cost",
                candidates=["amortizedCost"],
                required=True,
            ),
        ],
    ),
]


@dataclass
class HeatmapData:
    frame: pd.DataFrame
    state_summary: pd.DataFrame
    cbsa_summary: pd.DataFrame
    metric_columns: Dict[str, str]
    tooltip_fields: List[str]


def _render_readiness(panel_state) -> bool:
    missing_files = panel_state.missing_required_files
    missing_headers = panel_state.missing_required_headers
    if not missing_files and not missing_headers:
        return True

    messages: List[str] = []
    if missing_files:
        messages.append(
            "Missing required file(s): " + ", ".join(f"{title}" for title in missing_files)
        )
    if missing_headers:
        details = [
            f"- **{title}**: {', '.join(headers)}"
            for title, headers in missing_headers.items()
        ]
        messages.append("Missing required column(s):\n" + "\n".join(details))
    st.warning("Southside Bank heatmap inputs are incomplete.\n\n" + "\n".join(messages))
    return False


def _get_selected_column(status, canonical: str) -> Optional[str]:
    return status.selected_columns.get(canonical)


def _load_reference_dataframe(status) -> pd.DataFrame:
    columns = set(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    return df


def _load_result_dataframe(status) -> pd.DataFrame:
    columns = set(status.selected_columns.values())
    df = load_input_dataframe(status.file_path, tuple(columns), encoding=status.encoding)
    rename_map = {actual: canonical for canonical, actual in status.selected_columns.items()}
    df = df.rename(columns=rename_map)
    return df


def _normalize_state(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.upper().str.strip()

    def normalize(value: str) -> Optional[str]:
        if not value or value in {"NAN", "NONE"}:
            return None
        if len(value) == 2 and value in STATE_ABBREVIATION_SET:
            return value

        # Try to detect "(TX)" style suffixes.
        match = re.search(r"\b([A-Z]{2})\b", value)
        if match:
            candidate = match.group(1)
            if candidate in STATE_ABBREVIATION_SET:
                return candidate

        # Fall back to full-name mapping.
        if value in STATE_ABBREVIATIONS:
            return STATE_ABBREVIATIONS[value]
        return None

    normalized = cleaned.map(normalize)
    return normalized


def _map_occupancy(raw: pd.Series) -> pd.Series:
    mapping = {
        "owner": "Owner-occupied",
        "owner occupied": "Owner-occupied",
        "owner-occupied": "Owner-occupied",
        "owner occupied property": "Owner-occupied",
        "non-owner": "Non-owner-occupied",
        "non owner": "Non-owner-occupied",
        "non-owner-occupied": "Non-owner-occupied",
        "tenant": "Non-owner-occupied",
    }
    normalized = raw.fillna("").str.lower().str.strip()
    return normalized.map(mapping).fillna("Unknown")


def _choose_property_group(row: pd.Series) -> str:
    for field in ["propertyStatus", "loanPropertyGroupIdentifier", "assetClass"]:
        value = row.get(field)
        if pd.notna(value) and str(value).strip():
            return str(value)
    return "Unclassified"


def _derive_quarter(df: pd.DataFrame) -> pd.Series:
    """
    Determine the reporting quarter using any reporting/as-of date columns present.
    """
    quarter = pd.Series(pd.Period("1970Q1"), index=df.index, dtype="object")
    quarter[:] = pd.NaT
    candidate_columns = [
        column
        for column in df.columns
        if column.startswith("reportingDate") or column.startswith("asOfDate")
    ]
    for column in candidate_columns:
        dates = pd.to_datetime(df[column], errors="coerce")
        mask = quarter.isna() & dates.notna()
        quarter.loc[mask] = dates.loc[mask].dt.to_period("Q")
    return quarter


def _extract_cbsa_codes(df: pd.DataFrame) -> pd.Series:
    """
    Derive CBSA codes from any available geography-related columns.
    """
    cbsa_series = pd.Series(pd.NA, index=df.index, dtype="object")
    candidate_columns: List[str] = []
    for field in CBSA_COLUMN_CANDIDATES:
        for column in df.columns:
            if column == field or column.startswith(f"{field}_"):
                candidate_columns.append(column)
    for column in candidate_columns:
        raw = df[column].astype(str)
        extracted = raw.str.extract(r"(\d{5})", expand=False)
        cbsa_series = cbsa_series.where(cbsa_series.notna(), extracted)
        if cbsa_series.notna().all():
            break

    def _normalize(value: object) -> Optional[str]:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        token = str(value).strip()
        if not token:
            return None
        return token.zfill(5)

    return cbsa_series.map(_normalize)


def _prune_columns(df: pd.DataFrame) -> pd.DataFrame:
    keep: List[str] = []
    for column in df.columns:
        if column.startswith("portfolioIdentifier") and column != "portfolioIdentifier":
            continue
        if (
            column in ESSENTIAL_COLUMNS
            or column.startswith("reportingDate")
            or column.startswith("asOfDate")
            or column in CBSA_COLUMN_CANDIDATES
            or any(column.startswith(f"{field}_") for field in CBSA_COLUMN_CANDIDATES)
        ):
            keep.append(column)
    return df.loc[:, keep]


def _summarize_by_state(frame: pd.DataFrame) -> pd.DataFrame:
    summary = (
        frame.groupby("state", dropna=True)
        .agg(
            avg_pd=("annualizedPDOneYear", "mean"),
            avg_lgd=("lgdLifetime", "mean"),
            exposure=("amortizedCost", "sum"),
            instrument_count=("instrumentIdentifier", "nunique"),
        )
        .reset_index()
    )
    total_exposure = summary["exposure"].sum()
    if total_exposure > 0:
        summary["exposure_share"] = summary["exposure"] / total_exposure
    else:
        summary["exposure_share"] = np.nan
    return summary


def _summarize_by_cbsa(frame: pd.DataFrame) -> pd.DataFrame:
    if "cbsa_code" not in frame.columns:
        return pd.DataFrame(
            columns=[
                "cbsa_code",
                "avg_pd",
                "avg_lgd",
                "exposure",
                "instrument_count",
                "exposure_share",
                "cbsa_name",
            ]
        )
    filtered = frame.dropna(subset=["cbsa_code"])
    if filtered.empty:
        return pd.DataFrame(
            columns=[
                "cbsa_code",
                "avg_pd",
                "avg_lgd",
                "exposure",
                "instrument_count",
                "exposure_share",
                "cbsa_name",
            ]
        )
    summary = (
        filtered.groupby("cbsa_code", dropna=True)
        .agg(
            avg_pd=("annualizedPDOneYear", "mean"),
            avg_lgd=("lgdLifetime", "mean"),
            exposure=("amortizedCost", "sum"),
            instrument_count=("instrumentIdentifier", "nunique"),
        )
        .reset_index()
    )
    summary["cbsa_code"] = summary["cbsa_code"].apply(lambda value: str(value).zfill(5))
    metadata = load_cbsa_geojson()["metadata"]
    if not metadata.empty:
        summary = summary.merge(metadata, how="left", on="cbsa_code")
    else:
        summary["cbsa_name"] = summary["cbsa_code"]
    total_exposure = summary["exposure"].sum()
    if total_exposure > 0:
        summary["exposure_share"] = summary["exposure"] / total_exposure
    else:
        summary["exposure_share"] = np.nan
    return summary


def _prepare_state_map_data(summary: pd.DataFrame) -> pd.DataFrame:
    if "state" in summary.columns:
        base = summary.set_index("state")
    else:
        base = pd.DataFrame(
            columns=["avg_pd", "avg_lgd", "exposure", "instrument_count", "exposure_share"],
            index=pd.Index([], name="state"),
        )
    map_df = base.reindex(PLOTLY_STATE_CODES).reset_index()
    for column in ["exposure", "instrument_count"]:
        if column in map_df.columns:
            map_df[column] = map_df[column].fillna(0)
    if "exposure_share" in map_df.columns:
        map_df["exposure_share"] = map_df["exposure_share"].fillna(0)
    return map_df


def _prepare_heatmap_data(panel_state) -> HeatmapData:
    reference_status = panel_state.statuses["reference_current"]
    result_status = panel_state.statuses["result_current"]

    ref_df = _load_reference_dataframe(reference_status)
    res_df = _load_result_dataframe(result_status)

    merged = pd.merge(ref_df, res_df, on="instrumentIdentifier", how="inner", suffixes=("_ref", "_res"))

    portfolio_columns = [col for col in merged.columns if col.startswith("portfolioIdentifier")]
    if portfolio_columns:
        combined_series = merged[portfolio_columns[0]].copy()
        for column in portfolio_columns[1:]:
            combined_series = combined_series.fillna(merged[column])
        merged["portfolioIdentifier"] = combined_series

        available = {
            str(value).strip()
            for value in merged["portfolioIdentifier"].dropna()
            if str(value).strip()
        }
        existing = set(st.session_state.get("southside_portfolios", []))
        combined = sorted(existing.union(available))
        st.session_state["southside_portfolios"] = combined
    merged = _prune_columns(merged).copy()

    if "scenarioIdentifier" in merged.columns:
        scenario_values = sorted(
            {
                str(value).strip()
                for value in merged["scenarioIdentifier"].dropna()
                if str(value).strip()
            }
        )
        if scenario_values:
            st.session_state["southside_scenarios"] = scenario_values
        else:
            st.session_state.pop("southside_scenarios", None)
    else:
        st.session_state.pop("southside_scenarios", None)

    merged["state"] = _normalize_state(
        merged["borrowerState"].where(merged["borrowerState"].notna(), merged.get("collateralState"))
    )
    merged = merged[merged["state"].notna()]

    merged["occupancy"] = _map_occupancy(merged.get("occupancyStatus"))
    merged["propertyGroup"] = merged.apply(_choose_property_group, axis=1)

    merged["quarter"] = _derive_quarter(merged)
    merged["cbsa_code"] = _extract_cbsa_codes(merged)

    for column in ["annualizedPDOneYear", "lgdLifetime", "amortizedCost"]:
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce")

    merged = merged.dropna(subset=["annualizedPDOneYear", "lgdLifetime", "amortizedCost"], how="all")

    state_summary = _summarize_by_state(merged)
    cbsa_summary = _summarize_by_cbsa(merged)

    metric_columns = {
        "Average PD (1Y)": "avg_pd",
        "Average LGD (Lifetime)": "avg_lgd",
        "Exposure Share": "exposure_share",
    }
    tooltip_fields = [
        "avg_pd",
        "avg_lgd",
        "exposure",
        "exposure_share",
        "instrument_count",
    ]

    return HeatmapData(merged, state_summary, cbsa_summary, metric_columns, tooltip_fields)


def _apply_filters(data: HeatmapData, filters: Dict[str, str]) -> HeatmapData:
    frame = data.frame.copy()

    quarter_filter = filters.get("quarter", "Auto-detect")
    if quarter_filter and quarter_filter != "Auto-detect" and "quarter" in frame.columns:
        cleaned = quarter_filter.replace(" ", "").upper()
        normalized_quarter = cleaned
        if cleaned.startswith("Q") and len(cleaned) >= 5:
            normalized_quarter = f"{cleaned[-4:]}Q{cleaned[1]}"
        mask = frame["quarter"].astype(str) == normalized_quarter
        frame = frame[mask]

    scenario_filter = filters.get("scenario", "All scenarios")
    if scenario_filter and scenario_filter != "All scenarios" and "scenarioIdentifier" in frame.columns:
        normalized = frame["scenarioIdentifier"].fillna("").astype(str).str.strip()
        frame = frame[normalized == scenario_filter]

    occupancy_filter = filters.get("occupancy", "All")
    if occupancy_filter and occupancy_filter != "All":
        frame = frame[frame["occupancy"] == occupancy_filter]

    portfolio_list = filters.get("portfolio_list") or []
    if portfolio_list and "portfolioIdentifier" in frame.columns:
        frame = frame[
            frame["portfolioIdentifier"]
            .fillna("")
            .str.strip()
            .isin(portfolio_list)
        ]

    property_filter = filters.get("property_group", "All property groups")
    if property_filter and property_filter != "All property groups":
        requested = {p.strip().lower() for p in property_filter.split(",") if p.strip()}
        if requested:
            frame = frame[
                frame["propertyGroup"]
                .fillna("")
                .str.lower()
                .isin(requested)
            ]

    state_summary = _summarize_by_state(frame)
    cbsa_summary = _summarize_by_cbsa(frame)

    return HeatmapData(frame, state_summary, cbsa_summary, data.metric_columns, data.tooltip_fields)


def _render_kpis(summary: pd.DataFrame, geography_label: str) -> None:
    total_instruments = int(summary["instrument_count"].sum())
    avg_pd = summary["avg_pd"].mean()
    avg_lgd = summary["avg_lgd"].mean()
    total_exposure = summary["exposure"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Instruments ({geography_label})", f"{total_instruments:,}")
    col2.metric("Average PD (1Y)", f"{avg_pd:.2%}" if pd.notna(avg_pd) else "N/A")
    col3.metric("Average LGD", f"{avg_lgd:.2%}" if pd.notna(avg_lgd) else "N/A")
    col4.metric("Total Amortized Cost", f"${total_exposure:,.0f}")


def _render_state_heatmap(summary: pd.DataFrame, metric_label: str, metric_column: str) -> None:
    if summary.empty:
        st.warning("No data available after applying filters.")
        return

    color_scale = {
        "avg_pd": "PuBu",
        "avg_lgd": "Reds",
        "exposure_share": "Viridis",
    }[metric_column]

    map_data = _prepare_state_map_data(summary)
    fig = px.choropleth(
        map_data,
        locations="state",
        locationmode="USA-states",
        color=metric_column,
        scope="usa",
        color_continuous_scale=color_scale,
        labels={
            "avg_pd": "Avg PD (1Y)",
            "avg_lgd": "Avg LGD",
            "exposure_share": "Exposure Share",
        },
        hover_data={
            "avg_pd": ":.2%",
            "avg_lgd": ":.2%",
            "exposure_share": ":.1%",
            "exposure": ":,.0f",
            "instrument_count": ":,",
        },
    )
    fig.update_geos(
        visible=False,
        showcountries=False,
        showcoastlines=True,
        coastlinecolor="#2E2E2E",
        showlakes=True,
        lakecolor="#ffffff",
        projection_type="albers usa",
    )
    fig.update_traces(marker_line_color="#1c1c1c", marker_line_width=1.0)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(title=metric_label))
    st.plotly_chart(fig, use_container_width=True)


@st.cache_resource(show_spinner=False)
def load_cbsa_geojson() -> Dict[str, Optional[object]]:
    """
    Retrieve CBSA boundaries and metadata. Prefer local resources to avoid network
    calls, but fall back to remote retrieval when available.
    """
    if CBSA_GEOJSON_PATH.exists():
        geojson_data = json.load(CBSA_GEOJSON_PATH.open())
        if CBSA_METADATA_PATH.exists():
            metadata = pd.read_csv(CBSA_METADATA_PATH, dtype=str)
        else:
            metadata = pd.DataFrame(
                [
                    {
                        "cbsa_code": feature["properties"]["GEOID"],
                        "cbsa_name": feature["properties"]["NAME"],
                    }
                    for feature in geojson_data.get("features", [])
                ]
            )
        return {"geojson": geojson_data, "metadata": metadata}

    if CBSA_FEATURE_FOLDER.exists():
        features: List[Dict[str, object]] = []
        rows: List[Dict[str, str]] = []
        for path in sorted(CBSA_FEATURE_FOLDER.glob("*.json")):
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            geometry = data.get("geometry")
            if not geometry:
                continue
            properties = {
                key: value
                for key, value in data.items()
                if key not in {"geometry", "bbox"}
            }
            cbsa_code = properties.get("cbsa_code") or properties.get("cbsa")
            if not cbsa_code:
                continue
            cbsa_name = (
                properties.get("cbsa_name")
                or properties.get("cbsa_title")
                or cbsa_code
            )
            properties.setdefault("cbsa_code", cbsa_code)
            properties.setdefault("cbsa_name", cbsa_name)
            properties.setdefault("GEOID", cbsa_code)
            properties.setdefault("NAME", cbsa_name)
            rows.append(
                {
                    "cbsa_code": cbsa_code,
                    "cbsa_name": cbsa_name,
                }
            )
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties,
                }
            )

        if features:
            metadata = (
                pd.DataFrame(rows)
                .dropna(subset=["cbsa_code"])
                .drop_duplicates(subset=["cbsa_code"])
            )
            metadata["cbsa_name"] = metadata["cbsa_name"].fillna(
                metadata["cbsa_code"]
            )
            return {
                "geojson": {"type": "FeatureCollection", "features": features},
                "metadata": metadata,
            }

    if CBSA_SHAPEFILE_PATH.exists():
        try:
            import geopandas as gpd  # type: ignore import-not-found

            geodf = gpd.read_file(CBSA_SHAPEFILE_PATH)[["GEOID", "NAME", "geometry"]]
        except Exception as exc:  # pragma: no cover - optional dependency path
            st.warning(
                "Unable to read local CBSA shapefile; falling back to state view. "
                f"Details: {exc}"
            )
        else:
            metadata = (
                geodf[["GEOID", "NAME"]]
                .rename(columns={"GEOID": "cbsa_code", "NAME": "cbsa_name"})
                .dropna(subset=["cbsa_code"])
                .drop_duplicates(subset=["cbsa_code"])
            )
            geojson_data = json.loads(geodf.to_json())
            return {"geojson": geojson_data, "metadata": metadata}

    url = (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Presidential_Results_12-16/"
        "master/geojson/cb_2018_us_cbsa_5m.geojson"
    )
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        st.warning(
            "Unable to download CBSA boundaries; displaying state view only. "
            "Provide `data/cbsa.geojson` (and optional `data/cbsa_metadata.csv`) "
            "to enable CBSA heatmaps."
        )
        return {"geojson": None, "metadata": pd.DataFrame()}

    geojson = response.json()
    metadata = pd.DataFrame(
        [
            {"cbsa_code": feature["properties"]["GEOID"], "cbsa_name": feature["properties"]["NAME"]}
            for feature in geojson.get("features", [])
        ]
    )
    return {"geojson": geojson, "metadata": metadata}


def _render_cbsa_heatmap(summary: pd.DataFrame, metric_label: str, metric_column: str) -> None:
    if summary.empty:
        st.warning(
            "No CBSA-level data available after applying filters. Ensure the uploaded files include CBSA or "
            "geography codes so the dashboard can map each instrument."
        )
        return

    data = load_cbsa_geojson()
    geojson = data["geojson"]
    metadata = data["metadata"]

    if geojson is None:
        st.warning(
            "CBSA map unavailable because boundary files could not be loaded. "
            "Upload `data/cbsa.geojson` locally to enable the CBSA view."
        )
        _render_state_heatmap(summary, metric_label, metric_column)
        return

    if not metadata.empty:
        summary = summary.merge(metadata, how="left", on="cbsa_code")
    else:
        summary["cbsa_name"] = summary["cbsa_code"]

    fig = px.choropleth_mapbox(
        summary,
        geojson=geojson,
        locations="cbsa_code",
        featureidkey="properties.GEOID",
        color=metric_column,
        color_continuous_scale={
            "avg_pd": "PuBu",
            "avg_lgd": "Reds",
            "exposure_share": "Viridis",
        }[metric_column],
        hover_name="cbsa_name",
        hover_data={
            "avg_pd": ":.2%",
            "avg_lgd": ":.2%",
            "exposure_share": ":.1%",
            "exposure": ":,.0f",
            "instrument_count": ":,",
        },
        mapbox_style="carto-positron",
        zoom=3.35,
        center={"lat": 38.5, "lon": -96.5},
        opacity=0.8,
        labels={
            "avg_pd": "Avg PD (1Y)",
            "avg_lgd": "Avg LGD",
            "exposure_share": "Exposure Share",
        },
    )
    fig.update_traces(marker_line_color="#1c1c1c", marker_line_width=0.2)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_detail_table(summary: pd.DataFrame, geography: str) -> None:
    display = summary.copy()
    display = display.sort_values("exposure", ascending=False)
    display["avg_pd"] = display["avg_pd"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    display["avg_lgd"] = display["avg_lgd"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    display["exposure_share"] = display["exposure_share"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    if geography == "State":
        display = display.rename(
            columns={
                "state": "State",
                "avg_pd": "Avg PD (1Y)",
                "avg_lgd": "Avg LGD",
                "exposure": "Amortized Cost",
                "exposure_share": "Exposure Share",
                "instrument_count": "Instruments",
            }
        )
    else:
        display = display.rename(
            columns={
                "cbsa_name": "CBSA",
                "cbsa_code": "CBSA Code",
                "avg_pd": "Avg PD (1Y)",
                "avg_lgd": "Avg LGD",
                "exposure": "Amortized Cost",
                "exposure_share": "Exposure Share",
                "instrument_count": "Instruments",
            }
        )
    st.dataframe(display, use_container_width=True, hide_index=True)


def _select_metric_label(metric_columns: Dict[str, str]) -> str:
    options = list(metric_columns.keys())
    default = options[0] if options else ""
    segmented = getattr(st, "segmented_control", None)
    if segmented:
        try:
            return segmented(
                "View",
                options=options,
                default=default,
                key=f"{PAGE_KEY}_metric_selector_segmented",
            )
        except TypeError:
            st.warning(
                "Segmented control unavailable in this Streamlit environment. "
                "Falling back to radio buttons."
            )
        except Exception:
            st.warning(
                "Segmented control encountered an error. Using radio buttons instead."
            )

    return st.radio(
        "View",
        options=options,
        index=0,
        horizontal=True,
        key=f"{PAGE_KEY}_metric_selector_radio",
    )


def render_real_estate_pd_page(filters: Dict[str, str]) -> None:
    panel_state = render_inputs_panel(PAGE_KEY, INPUT_CONFIGS)
    if not _render_readiness(panel_state):
        return

    base_data = _prepare_heatmap_data(panel_state)
    filtered_data = _apply_filters(base_data, filters)

    geography_level = filters.get("geography", "State")
    if geography_level == "CBSA":
        summary = filtered_data.cbsa_summary
        geography_label = "CBSA"
    else:
        summary = filtered_data.state_summary
        geography_label = "State"

    _render_kpis(summary, geography_label)

    metric_label = _select_metric_label(filtered_data.metric_columns)
    metric_column = filtered_data.metric_columns[metric_label]
    st.caption(
        "Exposure share reflects each geography's share of amortized cost after the current filters "
        "are applied (geography amortized cost / total amortized cost)."
    )

    if geography_level == "CBSA":
        _render_cbsa_heatmap(summary, metric_label, metric_column)
        st.markdown("### CBSA Detail")
        _render_detail_table(summary, "CBSA")
    else:
        _render_state_heatmap(summary, metric_label, metric_column)
        st.markdown("### State Detail")
        _render_detail_table(summary, "State")

    export_controls(
        "real_estate_pd",
        dataframes={
            "state_summary": filtered_data.state_summary,
            "cbsa_summary": filtered_data.cbsa_summary,
            "filtered_instruments": filtered_data.frame,
        },
    )

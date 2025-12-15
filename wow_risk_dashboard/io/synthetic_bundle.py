"""
Synthetic Southside demo bundle for the new dashboard experience.

This module builds a compact, visually interesting dataset that mirrors the
shapes of the original uploads (reference, results, risk metrics, charge-offs)
so the revamped UI can run without user-provided CSVs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Cbsa:
    code: str
    name: str
    state: str
    weight: float
    latitude: float
    longitude: float


CBSA_CATALOG: List[Cbsa] = [
    Cbsa("19100", "Dallas-Fort Worth-Arlington, TX", "TX", 0.14, 32.7767, -96.7970),
    Cbsa("26420", "Houston-The Woodlands-Sugar Land, TX", "TX", 0.10, 29.7604, -95.3698),
    Cbsa("35620", "New York-Newark-Jersey City, NY-NJ", "NY", 0.14, 40.7128, -74.0060),
    Cbsa("38060", "Phoenix-Mesa-Chandler, AZ", "AZ", 0.06, 33.4484, -112.0740),
    Cbsa("16980", "Chicago-Naperville-Elgin, IL", "IL", 0.08, 41.8781, -87.6298),
    Cbsa("42660", "Seattle-Tacoma-Bellevue, WA", "WA", 0.07, 47.6062, -122.3321),
    Cbsa("47900", "Washington-Arlington-Alexandria, DC-VA", "VA", 0.07, 38.9072, -77.0369),
    Cbsa("33100", "Miami-Fort Lauderdale-Pompano Beach, FL", "FL", 0.08, 25.7617, -80.1918),
    Cbsa("41860", "San Francisco-Oakland-Berkeley, CA", "CA", 0.09, 37.7749, -122.4194),
    Cbsa("41700", "San Diego-Chula Vista-Carlsbad, CA", "CA", 0.07, 32.7157, -117.1611),
    Cbsa("16740", "Charlotte-Concord-Gastonia, NC-SC", "NC", 0.05, 35.2271, -80.8431),
    Cbsa("19740", "Denver-Aurora-Lakewood, CO", "CO", 0.05, 39.7392, -104.9903),
]


def _pd_to_rating(value: float) -> str:
    """Map PD to a stylized rating bucket."""
    if value <= 0.003:
        return "AAA"
    if value <= 0.006:
        return "AA"
    if value <= 0.010:
        return "A"
    if value <= 0.018:
        return "BBB"
    if value <= 0.030:
        return "BB"
    if value <= 0.060:
        return "B"
    if value <= 0.120:
        return "CCC"
    if value <= 0.180:
        return "CC"
    return "C"


def _cbsa_probs(catalog: List[Cbsa]) -> np.ndarray:
    weights = np.array([cbsa.weight for cbsa in catalog], dtype=float)
    return weights / weights.sum()


def build_synthetic_bundle(
    *,
    instruments: int = 360,
    seed: int = 13,
) -> Dict[str, pd.DataFrame]:
    """
    Create a cohesive synthetic dataset spanning 2023-2025.
    """
    rng = np.random.default_rng(seed)
    cbsa_probs = _cbsa_probs(CBSA_CATALOG)

    portfolios = ["CRE", "C&I", "Energy", "Healthcare", "Consumer"]
    property_groups = ["Multifamily", "Industrial", "Office", "Retail", "Hospitality", "Land"]
    occupancy_classes = ["Owner-occupied", "Non-owner-occupied"]
    scenarios = ["Baseline", "Adverse"]

    ref_records: List[Dict[str, object]] = []
    result_records: List[Dict[str, object]] = []
    risk_records: List[Dict[str, object]] = []
    chargeoff_records: List[Dict[str, object]] = []

    # Track end-of-horizon PD to decide which names default.
    end_pd_by_instrument: Dict[str, float] = {}
    ead_by_instrument: Dict[str, float] = {}
    lgd_by_instrument: Dict[str, float] = {}

    timeline = pd.date_range("2023-01-31", periods=30, freq="ME")

    for idx in range(instruments):
        instrument = f"LN-{idx:05d}"
        cbsa = CBSA_CATALOG[rng.choice(len(CBSA_CATALOG), p=cbsa_probs)]

        portfolio = rng.choice(portfolios, p=[0.30, 0.24, 0.12, 0.18, 0.16])
        property_group = rng.choice(property_groups, p=[0.24, 0.18, 0.16, 0.18, 0.14, 0.10])
        occupancy = rng.choice(occupancy_classes, p=[0.58, 0.42])
        scenario = rng.choice(scenarios, p=[0.65, 0.35])

        # Capital stack sizing and PD/LGD anchors.
        ead = float(np.clip(rng.lognormal(mean=13.7, sigma=0.35), 250_000, 4_000_000))
        lgd_base = {"Multifamily": 0.38, "Industrial": 0.36, "Office": 0.46, "Retail": 0.44, "Hospitality": 0.50, "Land": 0.55}.get(property_group, 0.42)
        lgd = float(np.clip(lgd_base + rng.normal(0, 0.02), 0.32, 0.62))

        risk_anchor = 0.0075 + rng.normal(0, 0.0035)
        property_lift = {
            "Multifamily": -0.002,
            "Industrial": -0.001,
            "Office": 0.003,
            "Retail": 0.0015,
            "Hospitality": 0.004,
            "Land": 0.006,
        }.get(property_group, 0.0)
        scenario_lift = 0.006 if scenario == "Adverse" else -0.001
        start_pd = float(np.clip(risk_anchor + property_lift + scenario_lift + rng.normal(0, 0.0025), 0.001, 0.18))
        drift = rng.normal(loc=0.002 if scenario == "Adverse" else -0.0006, scale=0.003)
        end_pd = float(np.clip(start_pd + drift, 0.001, 0.22))

        ead_by_instrument[instrument] = ead
        end_pd_by_instrument[instrument] = end_pd
        lgd_by_instrument[instrument] = lgd

        rating_start = _pd_to_rating(start_pd)
        rating_end = _pd_to_rating(end_pd)

        ref_records.append(
            {
                "instrumentIdentifier": instrument,
                "portfolioIdentifier": portfolio,
                "geographyCode": cbsa.code,
                "cbsaName": cbsa.name,
                "borrowerState": cbsa.state,
                "collateralState": cbsa.state,
                "occupancyStatus": occupancy,
                "propertyStatus": property_group,
                "loanPropertyGroupIdentifier": property_group,
                "assetClass": property_group,
                "amortizedCost": round(ead, 2),
                "reportingDate": "2024-06-30",
                "scenarioIdentifier": scenario,
                "latitude": cbsa.latitude,
                "longitude": cbsa.longitude,
            }
        )

        result_records.extend(
            [
                {
                    "instrumentIdentifier": instrument,
                    "portfolioIdentifier": portfolio,
                    "reportingDate": "2023-06-30",
                    "riskClassification": rating_start,
                    "ifrsEADAmount": round(ead, 2),
                    "scenarioIdentifier": scenario,
                },
                {
                    "instrumentIdentifier": instrument,
                    "portfolioIdentifier": portfolio,
                    "reportingDate": "2025-06-30",
                    "riskClassification": rating_end,
                    "ifrsEADAmount": round(ead * (1 + rng.normal(0, 0.03)), 2),
                    "scenarioIdentifier": scenario,
                },
            ]
        )

        for position, date in enumerate(timeline):
            weight = position / (len(timeline) - 1)
            pd_value = float(
                np.clip(start_pd + (end_pd - start_pd) * weight + rng.normal(0, 0.0012), 0.0008, 0.24)
            )
            ead_value = float(np.clip(ead * (1 + rng.normal(0, 0.04)), 200_000, 4_200_000))
            risk_records.append(
                {
                    "instrumentIdentifier": instrument,
                    "portfolioIdentifier": portfolio,
                    "reportingDate": date.strftime("%Y-%m-%d"),
                    "asOfDate": date.strftime("%Y-%m-%d"),
                    "annualizedCumulativePD": pd_value,
                    "lgd": lgd,
                    "ead": ead_value,
                    "geographyCode": cbsa.code,
                    "borrowerState": cbsa.state,
                    "scenarioIdentifier": scenario,
                    "propertyStatus": property_group,
                    "occupancyStatus": occupancy,
                    "latitude": cbsa.latitude,
                    "longitude": cbsa.longitude,
                }
            )

    # Select a default cohort from the riskiest names.
    default_candidates = sorted(end_pd_by_instrument.items(), key=lambda item: item[1], reverse=True)
    cohort_size = max(12, int(len(default_candidates) * 0.14))
    cohort = default_candidates[:cohort_size]
    event_dates = pd.date_range("2024-02-01", "2024-11-15", freq="2W")

    for (instrument, pd_end), event_date in zip(cohort, rng.choice(event_dates, size=cohort_size, replace=True)):
        chargeoff_records.append(
            {
                "instrumentIdentifier": instrument,
                "chargeOffDate": pd.to_datetime(event_date).strftime("%Y-%m-%d"),
                "netChargeOffAmount": round(
                    float(ead_by_instrument[instrument] * lgd_by_instrument[instrument] * rng.uniform(0.3, 0.65)),
                    2,
                ),
                "pdAtDefault": pd_end,
            }
        )

    bundle = {
        "instrument_reference": pd.DataFrame(ref_records),
        "instrument_result": pd.DataFrame(result_records),
        "instrument_risk_metric": pd.DataFrame(risk_records),
        "chargeoff": pd.DataFrame(chargeoff_records),
    }
    return bundle


def bundle_to_json(bundle: Dict[str, pd.DataFrame], path: Path) -> None:
    """Persist the bundle as a pretty JSON file."""
    serialized = {key: df.to_dict(orient="records") for key, df in bundle.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialized, indent=2))


def generate_default_json(path: Path | None = None) -> Path:
    """
    Generate the default synthetic JSON and return its path.
    """
    target = path or Path(__file__).resolve().parents[2] / "data" / "southside_demo.json"
    bundle = build_synthetic_bundle()
    bundle_to_json(bundle, target)
    return target


if __name__ == "__main__":
    output_path = generate_default_json()
    print(f"Synthetic demo JSON written to {output_path}")

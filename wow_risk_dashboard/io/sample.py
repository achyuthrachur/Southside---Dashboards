"""
Helpers for generating lightweight synthetic datasets used in demos and tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Tuple
import numpy as np
import pandas as pd


def _dates(start: datetime, periods: int, step_days: int = 30) -> list[str]:
    return [(start + timedelta(days=idx * step_days)).strftime("%Y-%m-%d") for idx in range(periods)]


def generate_sample_reference(count: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    states = ["TX", "CA", "NY", "WA", "FL"]
    cbsa_codes = ["19100", "26420", "35620", "42660", "47900"]
    data = {
        "instrumentIdentifier": [f"LN-{i:05d}" for i in range(count)],
        "portfolioIdentifier": rng.choice(["CRE", "C&I", "Consumer"], size=count),
        "geographyCode": rng.choice(cbsa_codes, size=count),
        "borrowerState": rng.choice(states, size=count),
        "collateralState": rng.choice(states, size=count),
        "occupancyStatus": rng.choice(["Owner", "Non-owner"], size=count),
        "propertyStatus": rng.choice(["Multifamily", "Office", "Retail"], size=count),
    }
    return pd.DataFrame(data)


def generate_sample_results(period_label: str, count: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(hash(period_label) % (2**32))
    ratings = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
    year = int(period_label[:4])
    quarter = int(period_label[-1]) if period_label[-1].isdigit() else 1
    start_month = (quarter - 1) * 3 + 1
    start_date = datetime(year, start_month, 1)
    data = {
        "instrumentIdentifier": [f"LN-{i:05d}" for i in range(count)],
        "portfolioIdentifier": rng.choice(["CRE", "C&I", "Consumer"], size=count),
        "reportingDate": [start_date.strftime("%Y-%m-%d")] * count,
        "riskClassification": rng.choice(ratings, size=count),
        "ifrsEADAmount": rng.normal(loc=1_000_000, scale=100_000, size=count).clip(min=25_000),
    }
    return pd.DataFrame(data)


def generate_sample_risk_metrics(periods: int = 8, count: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    base_date = datetime(2023, 1, 1)
    rows = []
    for period_idx in range(periods):
        date = base_date + timedelta(days=period_idx * 90)
        for i in range(count):
            pd_value = abs(rng.normal(0.02, 0.01))
            rows.append(
                {
                    "instrumentIdentifier": f"LN-{i:05d}",
                    "reportingDate": date.strftime("%Y-%m-%d"),
                    "annualizedCumulativePD": pd_value,
                    "lgd": 0.45,
                    "ead": 1_000_000 + rng.normal(0, 50_000),
                }
            )
    return pd.DataFrame(rows)


def generate_sample_chargeoffs(count: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(9)
    base_date = datetime(2024, 1, 15)
    data = []
    for idx in range(count):
        data.append(
            {
                "instrumentIdentifier": f"LN-{idx:05d}",
                "chargeOffDate": (base_date + timedelta(days=int(idx * 7))).strftime("%Y-%m-%d"),
                "netChargeOffAmount": float(abs(rng.normal(250_000, 50_000))),
            }
        )
    return pd.DataFrame(data)


def generate_sample_cashflows(count: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    base_date = datetime(2024, 1, 1)
    data = []
    for idx in range(count):
        data.append(
            {
                "instrumentIdentifier": f"LN-{idx:05d}",
                "cashFlowDate": (base_date + timedelta(days=int(idx * 5))).strftime("%Y-%m-%d"),
                "defaultAmount": float(abs(rng.normal(120_000, 20_000))),
                "principalRecoveryAmount": float(abs(rng.normal(20_000, 10_000))),
                "eadAmount": float(abs(rng.normal(900_000, 40_000))),
            }
        )
    return pd.DataFrame(data)


def sample_inputs_for_page(page_key: str) -> Dict[str, pd.DataFrame]:
    """
    Provide synthetic datasets keyed by dataset type to enable local demos
    without user uploads. Intended for tests and quick manual runs.
    """
    if page_key == "real_estate_pd":
        ref = generate_sample_reference()
        res = generate_sample_results("2024Q2")
        return {"instrument_reference": ref, "instrument_result": res}
    if page_key == "rating_migration":
        return {
            "instrument_result": pd.concat(
                [generate_sample_results("2023Q2"), generate_sample_results("2025Q2")]
            ),
            "instrument_risk_metric": generate_sample_risk_metrics(periods=2),
        }
    if page_key == "backtest":
        return {
            "instrument_risk_metric": generate_sample_risk_metrics(periods=1),
            "instrument_cashflow": generate_sample_cashflows(),
            "chargeoff": generate_sample_chargeoffs(),
        }
    if page_key == "macro_linkage":
        return {
            "instrument_risk_metric": generate_sample_risk_metrics(periods=10),
            "instrument_reference": generate_sample_reference(),
        }
    if page_key == "default_cohorts":
        return {
            "instrument_risk_metric": generate_sample_risk_metrics(periods=10),
            "chargeoff": generate_sample_chargeoffs(),
        }
    return {}

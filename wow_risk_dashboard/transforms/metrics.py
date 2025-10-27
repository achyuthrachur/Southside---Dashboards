"""
Quantitative transformations for expected losses, migrations, and cohorts.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd


def compute_expected_losses(
    harmonized: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Compute expected loss metrics needed for the backtest page.
    """
    raise NotImplementedError


def build_rating_migration(
    results: pd.DataFrame,
    risk_metrics: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Construct rating migration analytics outputs:
      * Sankey edge list
      * Transition matrix
      * Top movers summary
    """
    raise NotImplementedError


def build_default_cohorts(
    risk_metrics: pd.DataFrame,
    chargeoffs: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Build defaulted cohorts and matched control analytics.
    """
    raise NotImplementedError

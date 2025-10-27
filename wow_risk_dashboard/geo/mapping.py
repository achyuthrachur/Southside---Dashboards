"""
Geographic enrichment utilities for mapping instruments to CBSA/MSA regions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


@dataclass
class GeoResolver:
    """
    Provides lookup utilities for translating ZIP codes and geography codes
    into CBSA/MSA labels required for visualizations.
    """

    cbsa_lookup: pd.DataFrame

    @classmethod
    def from_file(cls, path: Path) -> "GeoResolver":
        raise NotImplementedError

    def resolve(
        self,
        borrower_zip: Optional[str],
        collateral_zip: Optional[str],
        state: Optional[str],
        geography_code: Optional[str],
    ) -> Dict[str, Optional[str]]:
        """
        Resolve CBSA information using precedence rules.
        """
        raise NotImplementedError


def load_cbsa_reference_data() -> pd.DataFrame:
    """
    Load CBSA reference data from local cache or remote source.
    """
    raise NotImplementedError


def resolve_cbsa_for_instrument(
    resolver: GeoResolver,
    record: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """
    Convenience helper for mapping a single instrument record.
    """
    raise NotImplementedError

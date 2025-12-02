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
        df = pd.read_csv(path, dtype=str)
        expected = {"cbsa_code", "cbsa_name"}
        missing = expected - set(df.columns)
        if missing:
            raise ValueError(f"CBSA reference file is missing columns: {', '.join(sorted(missing))}")
        df["cbsa_code"] = df["cbsa_code"].astype(str).str.zfill(5)
        return cls(cbsa_lookup=df)

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
        cbsa_code = None
        if geography_code:
            token = str(geography_code).strip()
            if token:
                cbsa_code = token.zfill(5) if token.isdigit() else token

        if cbsa_code and not cbsa_code.isdigit():
            cbsa_row = self.cbsa_lookup[self.cbsa_lookup["cbsa_name"].str.lower() == cbsa_code.lower()]
        elif cbsa_code:
            cbsa_row = self.cbsa_lookup[self.cbsa_lookup["cbsa_code"] == cbsa_code]
        else:
            cbsa_row = pd.DataFrame()

        cbsa_name = cbsa_row["cbsa_name"].iloc[0] if not cbsa_row.empty else None

        # Without a ZIP->CBSA map we cannot derive CBSA from ZIP; preserve state for downstream filters.
        return {
            "cbsa_code": cbsa_code,
            "cbsa_name": cbsa_name,
            "state": state,
        }


def load_cbsa_reference_data() -> pd.DataFrame:
    """
    Load CBSA reference data from local cache or remote source.
    """
    default_path = Path("data") / "cbsa_metadata.csv"
    if default_path.exists():
        return pd.read_csv(default_path, dtype=str)
    return pd.DataFrame(columns=["cbsa_code", "cbsa_name"])


def resolve_cbsa_for_instrument(
    resolver: GeoResolver,
    record: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """
    Convenience helper for mapping a single instrument record.
    """
    return resolver.resolve(
        borrower_zip=record.get("borrowerZipCode"),
        collateral_zip=record.get("collateralZipCode"),
        state=record.get("borrowerState") or record.get("collateralState"),
        geography_code=record.get("geographyCode"),
    )

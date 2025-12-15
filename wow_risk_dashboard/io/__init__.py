"""
Data ingestion and persistence utilities for the Southside Bank Risk Dashboard.
"""

from .loader import (
    LoadedFile,
    detect_file_profile,
    load_uploaded_files,
    normalize_headers,
    normalize_token,
)
from .paths import ensure_processed_dirs, get_processed_path
from .schemas import (
    AliasMap,
    DATASET_ORDER,
    DATASET_SPECS,
    FIELD_CANDIDATES,
    PD_PRIORITY,
    RATING_PRIORITY,
    EAD_PRIORITY,
    LGD_FIELDS,
    CHARGEOFF_AMOUNT_PRIORITY,
    DATE_FIELDS,
    IDENTIFIER_FIELDS,
    GEOGRAPHY_PRIORITY,
    PROPERTY_FIELDS,
    OCCUPANCY_FIELD,
    DatasetSpec,
)
from .storage import DatasetRegistry, PersistedDataset
from .sample import (
    generate_sample_reference,
    generate_sample_results,
    generate_sample_risk_metrics,
    generate_sample_chargeoffs,
    generate_sample_cashflows,
    sample_inputs_for_page,
)
from .synthetic_bundle import (
    build_synthetic_bundle,
    bundle_to_json,
    generate_default_json,
)

__all__ = [
    "AliasMap",
    "DatasetSpec",
    "LoadedFile",
    "detect_file_profile",
    "load_uploaded_files",
    "normalize_headers",
    "normalize_token",
    "ensure_processed_dirs",
    "get_processed_path",
    "DatasetRegistry",
    "PersistedDataset",
    "DATASET_ORDER",
    "DATASET_SPECS",
    "FIELD_CANDIDATES",
    "PD_PRIORITY",
    "RATING_PRIORITY",
    "EAD_PRIORITY",
    "LGD_FIELDS",
    "CHARGEOFF_AMOUNT_PRIORITY",
    "DATE_FIELDS",
    "IDENTIFIER_FIELDS",
    "GEOGRAPHY_PRIORITY",
    "PROPERTY_FIELDS",
    "OCCUPANCY_FIELD",
    "generate_sample_reference",
    "generate_sample_results",
    "generate_sample_risk_metrics",
    "generate_sample_chargeoffs",
    "generate_sample_cashflows",
    "sample_inputs_for_page",
    "build_synthetic_bundle",
    "bundle_to_json",
    "generate_default_json",
]

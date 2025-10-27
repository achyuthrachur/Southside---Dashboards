"""
Data ingestion and persistence utilities for the WOW Risk Dashboard.
"""

from .loader import (
    LoadedFile,
    detect_file_profile,
    load_uploaded_files,
    normalize_headers,
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

__all__ = [
    "AliasMap",
    "DatasetSpec",
    "LoadedFile",
    "detect_file_profile",
    "load_uploaded_files",
    "normalize_headers",
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
]

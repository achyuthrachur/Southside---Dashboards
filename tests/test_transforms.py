import pandas as pd

from wow_risk_dashboard.io.schemas import DATASET_SPECS
from wow_risk_dashboard.io.sample import (
    generate_sample_chargeoffs,
    generate_sample_risk_metrics,
    generate_sample_results,
)
from wow_risk_dashboard.transforms.harmonize import HarmonizedDataset, harmonize_datasets, select_canonical_fields
from wow_risk_dashboard.transforms.metrics import (
    build_default_cohorts,
    build_rating_migration,
    compute_expected_losses,
)


def test_select_canonical_fields_is_case_insensitive():
    spec = DATASET_SPECS["instrument_risk_metric"]
    df = pd.DataFrame(columns=["Instrument_ID", "reporting_date"])
    mapping = select_canonical_fields(df, spec.field_aliases)
    assert mapping["instrumentIdentifier"] == "Instrument_ID"
    assert mapping["reportingDate"] == "reporting_date"


def test_compute_expected_losses_generates_outputs():
    risk = generate_sample_risk_metrics(periods=1, count=10)
    harmonized = HarmonizedDataset(
        reference=pd.DataFrame(),
        risk_metric=risk,
        result=pd.DataFrame(),
        cashflow=pd.DataFrame(),
        chargeoff=pd.DataFrame(),
    )
    outputs = compute_expected_losses(harmonized)
    assert "instrument" in outputs and not outputs["instrument"].empty
    assert outputs["instrument"]["expected_loss"].ge(0).all()


def test_build_rating_migration_produces_edges():
    res_2023 = generate_sample_results("2023Q2", count=20).rename(columns={"riskClassification": "rating"})
    res_2023["period"] = "2023Q2"
    res_2025 = generate_sample_results("2025Q2", count=20).rename(columns={"riskClassification": "rating"})
    res_2025["period"] = "2025Q2"
    results = pd.concat([res_2023[["instrumentIdentifier", "rating", "period"]], res_2025[["instrumentIdentifier", "rating", "period"]]])
    edges, matrix, movers = build_rating_migration(results, pd.DataFrame())
    assert not edges.empty
    assert not matrix.empty
    assert "instrumentIdentifier" in movers.columns


def test_build_default_cohorts_uses_events_and_history():
    risk = generate_sample_risk_metrics(periods=6, count=10)
    chargeoffs = generate_sample_chargeoffs(count=5)
    outputs = build_default_cohorts(risk, chargeoffs)
    assert "pd_path" in outputs
    assert not outputs["pd_path"].empty

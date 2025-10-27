"""
Dataset schema definitions and alias registries for WOW Risk Dashboard ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Sequence

AliasMap = Dict[str, List[str]]


def alias_variants(name: str, extras: Optional[Sequence[str]] = None) -> List[str]:
    extras = extras or []
    variants: List[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if value and value not in variants:
            variants.append(value)

    add(name)
    add(name.replace(" ", ""))
    add(name.lower())
    add(name.replace(" ", "").lower())

    tokens = re.findall(r"[A-Z]+[a-z0-9]*|[a-z0-9]+", name)
    if tokens:
        snake = "_".join(token.lower() for token in tokens)
        add(snake)
        add(snake.replace("_", ""))
    for extra in extras:
        add(extra)
        add(extra.lower())
        add(extra.replace("_", ""))
    return variants


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    display_name: str
    filename_prefixes: Sequence[str]
    required_fields: Sequence[str]
    field_aliases: AliasMap
    identifying_fields: Sequence[str] = field(default_factory=list)

    def alias_for(self, field: str) -> List[str]:
        return self.field_aliases.get(field, [field])


INSTRUMENT_REFERENCE_ALIASES: AliasMap = {
    "instrumentIdentifier": alias_variants("instrumentIdentifier", ["instrument_id"]),
    "portfolioIdentifier": alias_variants("portfolioIdentifier", ["portfolio_id"]),
    "reportingDate": alias_variants("reportingDate", ["reporting_date"]),
    "asOfDate": alias_variants("asOfDate", ["as_of_date"]),
    "borrowerZipCode": alias_variants("borrowerZipCode", ["borrower_zip_code", "borrower_zip"]),
    "collateralZipCode": alias_variants("collateralZipCode", ["collateral_zip_code", "collateral_zip"]),
    "borrowerState": alias_variants("borrowerState", ["borrower_state"]),
    "collateralState": alias_variants("collateralState", ["collateral_state"]),
    "geographyCode": alias_variants("geographyCode", ["geography_code", "cbsa_code", "msa_code"]),
    "occupancyStatus": alias_variants("occupancyStatus", ["occupancy_status"]),
    "propertyStatus": alias_variants("propertyStatus", ["property_status"]),
    "loanPropertyGroupIdentifier": alias_variants(
        "loanPropertyGroupIdentifier",
        ["loan_property_group_identifier", "property_group_id"],
    ),
    "assetClass": alias_variants("assetClass", ["asset_class"]),
    "dealName": alias_variants("dealName", ["deal_name"]),
    "cusip": alias_variants("cusip", ["cusip_number"]),
    "obligorName": alias_variants("obligorName", ["obligor_name", "borrowerName"]),
}

INSTRUMENT_RISK_METRIC_ALIASES: AliasMap = {
    "instrumentIdentifier": alias_variants("instrumentIdentifier", ["instrument_id"]),
    "reportingDate": alias_variants("reportingDate", ["reporting_date"]),
    "asOfDate": alias_variants("asOfDate", ["as_of_date"]),
    "annualizedCumulativePD": alias_variants("annualizedCumulativePD", ["annualized_pd"]),
    "forwardPD": alias_variants("forwardPD", ["forward_pd"]),
    "cumulativePD": alias_variants("cumulativePD", ["cumulative_pd"]),
    "marginalPD": alias_variants("marginalPD", ["marginal_pd"]),
    "maturityRiskPD": alias_variants("maturityRiskPD", ["maturity_risk_pd"]),
    "lgd": alias_variants("lgd", ["lossGivenDefault"]),
    "lossRateAnnualized": alias_variants("lossRateAnnualized", ["loss_rate_annualized"]),
    "lossRateCumulative": alias_variants("lossRateCumulative", ["loss_rate_cumulative"]),
    "ead": alias_variants("ead", ["exposureAtDefault"]),
    "ccf": alias_variants("ccf"),
    "ugd": alias_variants("ugd"),
    "prepaymentRate": alias_variants("prepaymentRate", ["prepayment_rate"]),
    "forwardPrepaymentRate": alias_variants("forwardPrepaymentRate", ["forward_prepayment_rate"]),
    "cumulativePrepaymentRate": alias_variants("cumulativePrepaymentRate", ["cumulative_prepayment_rate"]),
    "expectedCreditLossAmount": alias_variants("expectedCreditLossAmount", ["expected_credit_loss_amount"]),
    "exposure": alias_variants("exposure"),
}

INSTRUMENT_RESULT_ALIASES: AliasMap = {
    "instrumentIdentifier": alias_variants("instrumentIdentifier", ["instrument_id"]),
    "portfolioIdentifier": alias_variants("portfolioIdentifier", ["portfolio_id"]),
    "reportingDate": alias_variants("reportingDate", ["reporting_date"]),
    "asOfDate": alias_variants("asOfDate", ["as_of_date"]),
    "riskClassification": alias_variants("riskClassification", ["risk_classification"]),
    "longTermRatingFromStageAllocation": alias_variants(
        "longTermRatingFromStageAllocation",
        ["long_term_rating_stage_allocation"],
    ),
    "longTermRatingFromStageAllocationScenarioBased": alias_variants(
        "longTermRatingFromStageAllocationScenarioBased",
        ["long_term_rating_stage_allocation_scenario", "long_term_rating_scenario"],
    ),
    "ifrsEADAmount": alias_variants("ifrsEADAmount", ["ifrs_ead_amount"]),
    "lossRateDelta": alias_variants("lossRateDelta", ["loss_rate_delta"]),
    "lossAllowanceDelta": alias_variants("lossAllowanceDelta", ["loss_allowance_delta"]),
    "ifrsLossRateUnadjusted": alias_variants("ifrsLossRateUnadjusted", ["ifrs_loss_rate_unadjusted"]),
    "lossAllowanceDeltaInInstrumentCurrency": alias_variants(
        "lossAllowanceDeltaInInstrumentCurrency",
        ["loss_allowance_delta_in_instrument_currency"],
    ),
}

INSTRUMENT_CASHFLOW_ALIASES: AliasMap = {
    "instrumentIdentifier": alias_variants("instrumentIdentifier", ["instrument_id"]),
    "portfolioIdentifier": alias_variants("portfolioIdentifier", ["portfolio_id"]),
    "cashFlowDate": alias_variants("cashFlowDate", ["cash_flow_date"]),
    "reportingDate": alias_variants("reportingDate", ["reporting_date"]),
    "asOfDate": alias_variants("asOfDate", ["as_of_date"]),
    "beginningUnpaidPrincipalBalance": alias_variants(
        "beginningUnpaidPrincipalBalance",
        ["beginning_principal_balance"],
    ),
    "grossCarryingAmount": alias_variants("grossCarryingAmount", ["gross_carrying_amount"]),
    "principalPayment": alias_variants("principalPayment", ["principal_payment"]),
    "interestPayment": alias_variants("interestPayment", ["interest_payment"]),
    "prepaymentAmount": alias_variants("prepaymentAmount", ["prepayment_amount"]),
    "defaultAmount": alias_variants("defaultAmount", ["default_amount"]),
    "principalRecoveryAmount": alias_variants("principalRecoveryAmount", ["principal_recovery_amount"]),
    "eadAmount": alias_variants("eadAmount", ["ead_amount"]),
    "forwardPD": alias_variants("forwardPD", ["forward_pd"]),
    "cumulativePD": alias_variants("cumulativePD", ["cumulative_pd"]),
    "lgd": alias_variants("lgd"),
    "discountFactorForAllowance": alias_variants(
        "discountFactorForAllowance",
        ["discount_factor_allowance"],
    ),
    "discountFactorForFairValue": alias_variants(
        "discountFactorForFairValue",
        ["discount_factor_fair_value"],
    ),
}

CHARGEOFF_ALIASES: AliasMap = {
    "instrumentIdentifier": alias_variants("instrumentIdentifier", ["instrument_id"]),
    "chargeOffDate": alias_variants(
        "chargeOffDate",
        ["charge_off_date", "chargeoff_date", "reportingDate", "asOfDate"],
    ),
    "reportingDate": alias_variants("reportingDate", ["reporting_date"]),
    "asOfDate": alias_variants("asOfDate", ["as_of_date"]),
    "netChargeOffAmount": alias_variants("netChargeOffAmount", ["net_charge_off_amount"]),
    "chargeOffAmount": alias_variants("chargeOffAmount", ["charge_off_amount"]),
}

INSTRUMENT_REFERENCE_SPEC = DatasetSpec(
    key="instrument_reference",
    display_name="Instrument Reference",
    filename_prefixes=("instrumentreference", "reference"),
    required_fields=("instrumentIdentifier", "portfolioIdentifier"),
    field_aliases=INSTRUMENT_REFERENCE_ALIASES,
    identifying_fields=(
        "reportingDate",
        "asOfDate",
        "borrowerZipCode",
        "collateralZipCode",
        "borrowerState",
        "collateralState",
        "geographyCode",
        "occupancyStatus",
        "propertyStatus",
        "loanPropertyGroupIdentifier",
        "assetClass",
    ),
)

INSTRUMENT_RISK_METRIC_SPEC = DatasetSpec(
    key="instrument_risk_metric",
    display_name="Instrument Risk Metric",
    filename_prefixes=("instrumentriskmetric", "riskmetric", "risk_metrics"),
    required_fields=("instrumentIdentifier", "reportingDate"),
    field_aliases=INSTRUMENT_RISK_METRIC_ALIASES,
    identifying_fields=(
        "annualizedCumulativePD",
        "forwardPD",
        "cumulativePD",
        "marginalPD",
        "maturityRiskPD",
        "lgd",
        "ead",
    ),
)

INSTRUMENT_RESULT_SPEC = DatasetSpec(
    key="instrument_result",
    display_name="Instrument Result",
    filename_prefixes=("instrumentresult", "result"),
    required_fields=("instrumentIdentifier", "portfolioIdentifier"),
    field_aliases=INSTRUMENT_RESULT_ALIASES,
    identifying_fields=(
        "reportingDate",
        "asOfDate",
        "riskClassification",
        "longTermRatingFromStageAllocation",
        "longTermRatingFromStageAllocationScenarioBased",
        "ifrsEADAmount",
        "lossAllowanceDelta",
    ),
)

INSTRUMENT_CASHFLOW_SPEC = DatasetSpec(
    key="instrument_cashflow",
    display_name="Instrument Cash Flow",
    filename_prefixes=("instrumentcashflow", "cashflow", "cash_flow"),
    required_fields=("instrumentIdentifier", "portfolioIdentifier", "cashFlowDate"),
    field_aliases=INSTRUMENT_CASHFLOW_ALIASES,
    identifying_fields=(
        "reportingDate",
        "asOfDate",
        "beginningUnpaidPrincipalBalance",
        "grossCarryingAmount",
        "principalPayment",
        "interestPayment",
        "prepaymentAmount",
        "defaultAmount",
        "principalRecoveryAmount",
        "eadAmount",
        "forwardPD",
        "cumulativePD",
        "lgd",
    ),
)

CHARGEOFF_SPEC = DatasetSpec(
    key="chargeoff",
    display_name="Charge-off",
    filename_prefixes=("chargeoff", "charge_off", "default"),
    required_fields=("instrumentIdentifier",),
    field_aliases=CHARGEOFF_ALIASES,
    identifying_fields=(
        "chargeOffDate",
        "netChargeOffAmount",
        "chargeOffAmount",
    ),
)

DATASET_SPECS: Dict[str, DatasetSpec] = {
    spec.key: spec
    for spec in (
        INSTRUMENT_REFERENCE_SPEC,
        INSTRUMENT_RISK_METRIC_SPEC,
        INSTRUMENT_RESULT_SPEC,
        INSTRUMENT_CASHFLOW_SPEC,
        CHARGEOFF_SPEC,
    )
}

DATASET_ORDER: Sequence[str] = tuple(DATASET_SPECS.keys())

FIELD_CANDIDATES: AliasMap = {}
for spec in DATASET_SPECS.values():
    for canonical, aliases in spec.field_aliases.items():
        target = FIELD_CANDIDATES.setdefault(canonical, [])
        for alias in aliases:
            if alias not in target:
                target.append(alias)

PD_PRIORITY: Sequence[str] = (
    "annualizedCumulativePD",
    "forwardPD",
    "cumulativePD",
    "marginalPD",
    "maturityRiskPD",
)

RATING_PRIORITY: Sequence[str] = (
    "riskClassification",
    "longTermRatingFromStageAllocation",
    "longTermRatingFromStageAllocationScenarioBased",
)

EAD_PRIORITY: Sequence[str] = (
    "ead",
    "eadAmount",
    "ifrsEADAmount",
)

LGD_FIELDS: Sequence[str] = ("lgd",)

CHARGEOFF_AMOUNT_PRIORITY: Sequence[str] = (
    "netChargeOffAmount",
    "chargeOffAmount",
)

DATE_FIELDS: Sequence[str] = (
    "reportingDate",
    "asOfDate",
    "cashFlowDate",
    "chargeOffDate",
)

IDENTIFIER_FIELDS: Sequence[str] = (
    "instrumentIdentifier",
    "portfolioIdentifier",
)

GEOGRAPHY_PRIORITY: Sequence[str] = (
    "geographyCode",
    "borrowerZipCode",
    "collateralZipCode",
    "borrowerState",
    "collateralState",
)

PROPERTY_FIELDS: Sequence[str] = (
    "propertyStatus",
    "loanPropertyGroupIdentifier",
    "assetClass",
)

OCCUPANCY_FIELD: str = "occupancyStatus"

__all__ = [
    "AliasMap",
    "DatasetSpec",
    "DATASET_SPECS",
    "DATASET_ORDER",
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
    "alias_variants",
]

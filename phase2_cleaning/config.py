"""
Cleaning rules configuration for the NGO data cleaning pipeline.

This module externalises every cleaning decision — column mappings,
valid value sets, imputation strategies, outlier bounds — so that the
cleaning logic in ``cleaners.py`` contains *zero* hard-coded magic
values.  An M&E officer can modify this file without touching Python
business logic.

Design rationale:
    - Frozen dataclasses enforce immutability at runtime.
    - Every threshold has a docstring-level comment explaining *why*
      that value was chosen (domain justification, not arbitrary).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DateCleaningConfig:
    """
    Rules for normalising inconsistent date formats.

    The synthetic generator injects formats like DD/MM/YYYY, DD-Mon-YY,
    MM-DD-YYYY, etc.  We attempt parsing with ``dayfirst=True`` because
    Indian data entry conventions are DD/MM/YYYY (not US MM/DD/YYYY).
    """

    target_format: str = "%Y-%m-%d"
    dayfirst: bool = True
    # Columns that are known date fields, per table
    date_columns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "beneficiaries": ["registration_date"],
            "service_delivery": ["delivery_date"],
            "assessments": ["assessment_date"],
            "funding": ["disbursement_date"],
            "interventions": ["scheduled_date", "actual_date"],
            "expenses": ["expense_date"],
            "staff": ["hire_date"],
            "donors": ["onboarded_date"],
            "outcome_tracking": [],
            "programs": ["start_date", "end_date"],
        }
    )


# ---------------------------------------------------------------------------
# Categorical standardisation
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CategoricalCleaningConfig:
    """
    Canonical value mappings for categorical columns.

    These maps resolve the casing / abbreviation chaos injected by the
    noise generator (e.g., 'male', 'MALE', 'M' → 'Male').

    The keys are *lowercased and stripped* versions of dirty values.
    """

    gender_map: dict[str, str] = field(
        default_factory=lambda: {
            "male": "Male",
            "m": "Male",
            "female": "Female",
            "f": "Female",
            "non-binary": "Non-Binary",
            "nb": "Non-Binary",
            "n": "Non-Binary",
            "prefer not to say": "Prefer Not to Say",
            "p": "Prefer Not to Say",
        }
    )

    service_status_map: dict[str, str] = field(
        default_factory=lambda: {
            "completed": "Completed",
            "c": "Completed",
            "partially completed": "Partially Completed",
            "scheduled": "Scheduled",
            "s": "Scheduled",
            "cancelled": "Cancelled",
            "canceled": "Cancelled",
            "no-show": "No-Show",
            "no show": "No-Show",
            "n": "No-Show",
        }
    )

    assessment_type_map: dict[str, str] = field(
        default_factory=lambda: {
            "pre-test": "Pre-Test",
            "pre test": "Pre-Test",
            "pretest": "Pre-Test",
            "post-test": "Post-Test",
            "post test": "Post-Test",
            "posttest": "Post-Test",
            "midline survey": "Midline Survey",
            "endline survey": "Endline Survey",
            "spot check": "Spot Check",
            "follow-up interview": "Follow-Up Interview",
            "follow up interview": "Follow-Up Interview",
        }
    )

    outcome_status_map: dict[str, str] = field(
        default_factory=lambda: {
            "on track": "On Track",
            "at risk": "At Risk",
            "off track": "Off Track",
            "achieved": "Achieved",
            "exceeded": "Exceeded",
        }
    )


# ---------------------------------------------------------------------------
# Outlier boundaries (domain-justified)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OutlierConfig:
    """
    Valid ranges for numeric fields, grounded in M&E domain knowledge.

    Each bound has a domain rationale:
        - age: NGOs serve children (5+) through elderly (max 100)
        - household_size: India avg ~4.4; max reasonable = 20
        - score: Cannot be negative; max bounded by max_score
        - dosage: Sessions per beneficiary; max 50 is generous
        - attendance: Cannot be negative; max 1000 for large events
        - amount_inr: ₹100 minimum transaction; ₹10Cr ceiling
    """

    age_min: int = 0
    age_max: int = 110
    household_min: int = 1
    household_max: int = 20
    score_min: float = 0.0
    dosage_min: int = 0
    dosage_max: int = 50
    attendance_min: int = 0
    attendance_max: int = 1000
    amount_min: float = 100.0
    amount_max: float = 100_000_000.0


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DeduplicationConfig:
    """
    Rules for identifying and removing near-duplicate records.

    Strategy: flag rows where the primary key contains '-DUP' (injected
    by the noise generator), then additionally check for near-matches
    on key demographic fields.
    """

    # Columns to use for fuzzy matching (per table)
    match_columns: dict[str, list[str]] = field(
        default_factory=lambda: {
            "beneficiaries": ["full_name", "phone", "region_id"],
            "service_delivery": ["beneficiary_id", "intervention_id", "delivery_date"],
            "assessments": ["beneficiary_id", "assessment_type", "assessment_date"],
            "staff": ["full_name", "phone"],
            "funding": ["donor_id", "program_id", "disbursement_date"],
        }
    )


# ---------------------------------------------------------------------------
# Imputation strategies
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ImputationConfig:
    """
    Column-level imputation strategies.

    Strategy options:
        - 'median': Numeric columns — robust to outliers
        - 'mode': Categorical columns — most frequent value
        - 'unknown': Fill with a sentinel string (e.g., 'Unknown')
        - 'drop': Drop rows where this column is NULL (last resort)
        - 'forward_fill': Time-series ordered fill
        - 'zero': Fill with 0 (e.g., dosage, attendance)
        - 'skip': Leave as NULL — intentional for BI tools to handle

    Design choice: We prefer 'unknown' over 'mode' for demographic fields
    because imputing a gender or income bracket introduces bias.  Better
    to be explicit that the data was missing.
    """

    strategies: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "beneficiaries": {
                "age": "median",
                "gender": "unknown",
                "phone": "skip",
                "education_level": "unknown",
                "income_bracket": "unknown",
                "household_size": "median",
                "is_disabled": "zero",
                "registration_date": "skip",
            },
            "service_delivery": {
                "dosage": "median",
                "notes": "skip",
                "delivery_date": "skip",
            },
            "assessments": {
                "score": "skip",  # Cannot fabricate test scores
                "remarks": "skip",
                "intervention_id": "skip",
                "max_score": "skip",
            },
            "funding": {
                "grant_type": "unknown",
                "disbursement_date": "skip",
            },
            "staff": {
                "phone": "skip",
                "email": "skip",
                "hire_date": "skip",
            },
        }
    )


# ---------------------------------------------------------------------------
# Master config aggregator
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CleaningConfig:
    """Top-level cleaning configuration aggregating all sub-configs."""

    dates: DateCleaningConfig = field(default_factory=DateCleaningConfig)
    categoricals: CategoricalCleaningConfig = field(
        default_factory=CategoricalCleaningConfig
    )
    outliers: OutlierConfig = field(default_factory=OutlierConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    imputation: ImputationConfig = field(default_factory=ImputationConfig)


# Singleton config instance
CLEANING_CONFIG: Final[CleaningConfig] = CleaningConfig()

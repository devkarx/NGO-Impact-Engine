"""
Fact table generators for transactional / event-level entities.

Generators:
    - BeneficiaryGenerator       → beneficiaries (~2,000 rows)
    - FundingGenerator           → funding (~80 rows)
    - InterventionGenerator      → interventions (~150 rows)
    - ServiceDeliveryGenerator   → service_delivery (~2,500 rows)
    - AssessmentGenerator        → assessments (~1,800 rows)
    - OutcomeTrackingGenerator   → outcome_tracking (~200 rows)
    - ExpenseGenerator           → expenses (~300 rows)

Each generator accepts pre-generated dimension DataFrames as constructor
arguments to guarantee valid foreign key references (before noise injection).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pandas as pd

from phase1_data_architecture.config import (
    AGE_RANGE,
    ASSESSMENT_TYPES,
    DATA_END_DATE,
    DATA_START_DATE,
    EDUCATION_LEVELS,
    EXPENSE_CATEGORIES,
    GENDER_VALUES,
    GENDER_WEIGHTS,
    INCOME_BRACKETS,
    INCOME_WEIGHTS,
    INTERVENTION_TYPES,
    ROW_COUNTS,
    SERVICE_STATUSES,
    SERVICE_STATUS_WEIGHTS,
)
from phase1_data_architecture.generators.base import BaseGenerator

logger = logging.getLogger(__name__)


# =========================================================================
# BENEFICIARIES
# =========================================================================
class BeneficiaryGenerator(BaseGenerator):
    """
    Generate the ``beneficiaries`` fact table.

    Produces realistic Indian beneficiary records with demographic data
    that mirrors the population served by development-sector NGOs —
    skewing toward BPL/LIG income brackets and lower education levels.
    """

    def __init__(
        self,
        region_ids: list[str],
        program_ids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._region_ids = region_ids
        self._program_ids = program_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.beneficiaries + 1):
            age = int(self.rng.integers(AGE_RANGE[0], AGE_RANGE[1] + 1))
            registration_date = self.random_date(DATA_START_DATE, DATA_END_DATE)

            rows.append(
                {
                    "beneficiary_id": self.make_id("BEN", i, width=5),
                    "full_name": self.fake.name(),
                    "age": age,
                    "gender": self.weighted_choice(GENDER_VALUES, GENDER_WEIGHTS),
                    "phone": self.indian_phone(),
                    "education_level": self.weighted_choice(
                        EDUCATION_LEVELS,
                        weights=[0.25, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05],
                    ),
                    "income_bracket": self.weighted_choice(
                        INCOME_BRACKETS, INCOME_WEIGHTS
                    ),
                    "region_id": self.rng.choice(self._region_ids),
                    "registration_date": registration_date,
                    "program_id": self.rng.choice(self._program_ids),
                    "household_size": int(self.rng.integers(1, 12)),
                    "is_disabled": int(self.rng.choice([0, 1], p=[0.88, 0.12])),
                }
            )

        return rows


# =========================================================================
# FUNDING
# =========================================================================
class FundingGenerator(BaseGenerator):
    """Generate the ``funding`` fact table linking donors to programs."""

    _GRANT_TYPES: list[str] = ["Restricted", "Unrestricted", "Project-Tied"]

    def __init__(
        self,
        donor_ids: list[str],
        program_ids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._donor_ids = donor_ids
        self._program_ids = program_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.funding + 1):
            disbursement = self.random_date(DATA_START_DATE, DATA_END_DATE)
            # Funding amounts: ₹50K – ₹50L (log-normal distribution)
            amount = round(float(self.rng.lognormal(mean=12.5, sigma=1.2)), 2)
            amount = max(50_000.0, min(amount, 5_000_000.0))

            rows.append(
                {
                    "funding_id": self.make_id("FND", i),
                    "donor_id": self.rng.choice(self._donor_ids),
                    "program_id": self.rng.choice(self._program_ids),
                    "amount_inr": amount,
                    "currency": "INR",
                    "disbursement_date": disbursement,
                    "fiscal_year": self.fiscal_year_label(disbursement),
                    "grant_type": self.rng.choice(self._GRANT_TYPES),
                }
            )

        return rows


# =========================================================================
# INTERVENTIONS
# =========================================================================
class InterventionGenerator(BaseGenerator):
    """Generate the ``interventions`` fact table."""

    def __init__(
        self,
        program_ids: list[str],
        staff_ids: list[str],
        region_ids: list[str],
        programs_df: pd.DataFrame,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._program_ids = program_ids
        self._staff_ids = staff_ids
        self._region_ids = region_ids
        self._programs_df = programs_df

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.interventions + 1):
            program_id = self.rng.choice(self._program_ids)
            prog_row = self._programs_df[
                self._programs_df["program_id"] == program_id
            ].iloc[0]

            # Schedule intervention within the program's active window
            prog_start = pd.Timestamp(prog_row["start_date"]).date()
            prog_end = (
                pd.Timestamp(prog_row["end_date"]).date()
                if pd.notna(prog_row["end_date"])
                else DATA_END_DATE
            )
            scheduled = self.random_date(prog_start, prog_end)

            # 80% chance the intervention actually happened
            actual = None
            if self.rng.random() < 0.80:
                offset = int(self.rng.integers(-3, 8))  # slight drift
                actual = scheduled + timedelta(days=offset)

            planned = int(self.rng.integers(10, 200))
            actual_att = (
                int(self.rng.integers(max(1, planned - 40), planned + 20))
                if actual is not None
                else None
            )

            intervention_type = self.rng.choice(INTERVENTION_TYPES)
            title = f"{intervention_type} — {prog_row['sector']} ({prog_row['program_name'][:30]})"

            rows.append(
                {
                    "intervention_id": self.make_id("INT", i),
                    "program_id": program_id,
                    "intervention_type": intervention_type,
                    "title": title,
                    "scheduled_date": scheduled,
                    "actual_date": actual,
                    "staff_id": self.rng.choice(self._staff_ids),
                    "region_id": self.rng.choice(self._region_ids),
                    "planned_attendance": planned,
                    "actual_attendance": actual_att,
                }
            )

        return rows

    @property
    def interventions(self) -> int:
        """Alias for documentation clarity."""
        return ROW_COUNTS.interventions


# =========================================================================
# SERVICE DELIVERY
# =========================================================================
class ServiceDeliveryGenerator(BaseGenerator):
    """
    Generate the ``service_delivery`` fact table.

    Each row records one beneficiary receiving one unit of service
    during a specific intervention.
    """

    def __init__(
        self,
        beneficiary_ids: list[str],
        intervention_ids: list[str],
        interventions_df: pd.DataFrame,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._beneficiary_ids = beneficiary_ids
        self._intervention_ids = intervention_ids
        self._interventions_df = interventions_df

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        notes_pool = [
            "Beneficiary engaged well.",
            "Partial attendance — left early.",
            "Required follow-up visit.",
            "Materials distributed successfully.",
            "Translator needed for local dialect.",
            "Beneficiary was not available.",
            "Completed all modules.",
            None,
        ]

        for i in range(1, ROW_COUNTS.service_delivery + 1):
            intervention_id = self.rng.choice(self._intervention_ids)
            intv_row = self._interventions_df[
                self._interventions_df["intervention_id"] == intervention_id
            ].iloc[0]

            # Delivery date = intervention's actual date (or scheduled if no actual)
            base_date = (
                pd.Timestamp(intv_row["actual_date"]).date()
                if pd.notna(intv_row["actual_date"])
                else pd.Timestamp(intv_row["scheduled_date"]).date()
            )

            rows.append(
                {
                    "delivery_id": self.make_id("DEL", i, width=5),
                    "beneficiary_id": self.rng.choice(self._beneficiary_ids),
                    "intervention_id": intervention_id,
                    "delivery_date": base_date,
                    "status": self.weighted_choice(
                        SERVICE_STATUSES, SERVICE_STATUS_WEIGHTS
                    ),
                    "dosage": int(self.rng.integers(1, 6)),
                    "notes": self.rng.choice(notes_pool),
                }
            )

        return rows


# =========================================================================
# ASSESSMENTS
# =========================================================================
class AssessmentGenerator(BaseGenerator):
    """
    Generate the ``assessments`` fact table.

    Models pre/post tests and surveys that measure beneficiary-level
    outcome changes — the core of any M&E outcome measurement system.
    """

    def __init__(
        self,
        beneficiary_ids: list[str],
        intervention_ids: list[str],
        staff_ids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._beneficiary_ids = beneficiary_ids
        self._intervention_ids = intervention_ids
        self._staff_ids = staff_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        remarks_pool = [
            "Significant improvement observed.",
            "No change from baseline.",
            "Beneficiary uncooperative during assessment.",
            "Assessment incomplete — will revisit.",
            "Strong progress in literacy skills.",
            "Health indicators within normal range.",
            None,
        ]

        for i in range(1, ROW_COUNTS.assessments + 1):
            assessment_type = self.rng.choice(ASSESSMENT_TYPES)
            max_score = float(self.rng.choice([10, 20, 50, 100]))

            # Score distribution: roughly normal centred at 60% of max
            raw_score = float(
                self.rng.normal(loc=max_score * 0.6, scale=max_score * 0.2)
            )
            score = round(max(0.0, min(raw_score, max_score)), 1)

            rows.append(
                {
                    "assessment_id": self.make_id("ASM", i, width=5),
                    "beneficiary_id": self.rng.choice(self._beneficiary_ids),
                    "intervention_id": (
                        self.rng.choice(self._intervention_ids)
                        if self.rng.random() > 0.1
                        else None
                    ),
                    "assessment_type": assessment_type,
                    "assessment_date": self.random_date(DATA_START_DATE, DATA_END_DATE),
                    "score": score,
                    "max_score": max_score,
                    "assessor_staff_id": self.rng.choice(self._staff_ids),
                    "remarks": self.rng.choice(remarks_pool),
                }
            )

        return rows


# =========================================================================
# OUTCOME TRACKING
# =========================================================================
class OutcomeTrackingGenerator(BaseGenerator):
    """
    Generate the ``outcome_tracking`` fact table.

    Links program-level quarterly results to IRIS+ indicators, enabling
    the Activity → Output → Outcome → Impact rollup in the dashboard.
    """

    def __init__(
        self,
        program_ids: list[str],
        indicator_ids: list[str],
        staff_ids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._program_ids = program_ids
        self._indicator_ids = indicator_ids
        self._staff_ids = staff_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        # Generate quarterly periods across the data window
        quarters = self._generate_quarters()
        data_sources = [
            "Field Survey",
            "MIS Database",
            "Government Records",
            "Community Feedback",
            "Third-Party Audit",
        ]

        idx = 1
        for program_id in self._program_ids:
            # Each program tracks 3-5 indicators across quarters
            n_indicators = int(self.rng.integers(3, 6))
            selected_indicators = self.rng.choice(
                self._indicator_ids,
                size=min(n_indicators, len(self._indicator_ids)),
                replace=False,
            ).tolist()

            for indicator_id in selected_indicators:
                for quarter in quarters:
                    if idx > ROW_COUNTS.outcome_tracking:
                        break

                    target = round(float(self.rng.uniform(50, 500)), 1)
                    # Actual is 60-120% of target (some over-achieve, some under)
                    actual = round(target * float(self.rng.uniform(0.6, 1.2)), 1)
                    ratio = actual / target if target > 0 else 0

                    if ratio >= 1.0:
                        status = "Achieved" if ratio < 1.1 else "Exceeded"
                    elif ratio >= 0.8:
                        status = "On Track"
                    elif ratio >= 0.5:
                        status = "At Risk"
                    else:
                        status = "Off Track"

                    rows.append(
                        {
                            "outcome_id": self.make_id("OUT", idx),
                            "program_id": program_id,
                            "indicator_id": indicator_id,
                            "reporting_period": quarter,
                            "target_value": target,
                            "actual_value": actual,
                            "status": status,
                            "data_source": self.rng.choice(data_sources),
                            "verified_by": (
                                self.rng.choice(self._staff_ids)
                                if self.rng.random() > 0.2
                                else None
                            ),
                        }
                    )
                    idx += 1

                if idx > ROW_COUNTS.outcome_tracking:
                    break
            if idx > ROW_COUNTS.outcome_tracking:
                break

        return rows

    @staticmethod
    def _generate_quarters() -> list[str]:
        """Generate Indian FY quarter labels from FY2021-22 to FY2024-25."""
        quarters = []
        for fy_start in range(2021, 2025):
            fy_label = f"FY{fy_start}-{str(fy_start + 1)[-2:]}"
            for q in range(1, 5):
                quarters.append(f"Q{q}-{fy_label}")
        return quarters


# =========================================================================
# EXPENSES
# =========================================================================
class ExpenseGenerator(BaseGenerator):
    """Generate the ``expenses`` fact table."""

    def __init__(
        self,
        program_ids: list[str],
        staff_ids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._program_ids = program_ids
        self._staff_ids = staff_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.expenses + 1):
            expense_date = self.random_date(DATA_START_DATE, DATA_END_DATE)
            # Expense amounts: ₹500 – ₹5L (log-normal)
            amount = round(float(self.rng.lognormal(mean=10.0, sigma=1.0)), 2)
            amount = max(500.0, min(amount, 500_000.0))

            rows.append(
                {
                    "expense_id": self.make_id("EXP", i),
                    "program_id": self.rng.choice(self._program_ids),
                    "category": self.rng.choice(EXPENSE_CATEGORIES),
                    "amount_inr": amount,
                    "expense_date": expense_date,
                    "fiscal_year": self.fiscal_year_label(expense_date),
                    "approved_by": (
                        self.rng.choice(self._staff_ids)
                        if self.rng.random() > 0.15
                        else None
                    ),
                    "receipt_available": int(self.rng.choice([0, 1], p=[0.20, 0.80])),
                }
            )

        return rows

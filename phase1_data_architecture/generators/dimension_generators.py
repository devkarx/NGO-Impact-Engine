"""
Dimension table generators for reference/lookup entities.

Generators:
    - RegionGenerator        → regions (25 rows)
    - DonorGenerator         → donors (30 rows)
    - ProgramGenerator       → programs (12 rows)
    - StaffGenerator         → staff (60 rows)
    - ImpactIndicatorGenerator → impact_indicators (20 rows)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from phase1_data_architecture.config import (
    DATA_END_DATE,
    DATA_START_DATE,
    DONOR_TYPES,
    IRIS_INDICATORS,
    PROGRAM_SECTORS,
    REGION_TYPES,
    ROW_COUNTS,
    STATES_AND_DISTRICTS,
)
from phase1_data_architecture.generators.base import BaseGenerator

logger = logging.getLogger(__name__)


# =========================================================================
# REGIONS
# =========================================================================
class RegionGenerator(BaseGenerator):
    """Generate the ``regions`` dimension table."""

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        idx = 1

        for state, districts in STATES_AND_DISTRICTS.items():
            for district in districts:
                if idx > ROW_COUNTS.regions:
                    break
                rows.append(
                    {
                        "region_id": self.make_id("REG", idx),
                        "state": state,
                        "district": district,
                        "block": (
                            self.fake.city_suffix() if self.rng.random() > 0.3 else None
                        ),
                        "region_type": self.weighted_choice(
                            REGION_TYPES, weights=[0.20, 0.25, 0.40, 0.15]
                        ),
                        "latitude": round(float(self.rng.uniform(8.0, 37.0)), 6),
                        "longitude": round(float(self.rng.uniform(68.0, 97.0)), 6),
                    }
                )
                idx += 1
            if idx > ROW_COUNTS.regions:
                break

        logger.debug("RegionGenerator produced %d rows", len(rows))
        return rows


# =========================================================================
# DONORS
# =========================================================================
class DonorGenerator(BaseGenerator):
    """Generate the ``donors`` dimension table."""

    # Realistic donor name templates
    _DONOR_TEMPLATES: list[str] = [
        "{company} Foundation",
        "{company} CSR Trust",
        "The {last_name} Family Trust",
        "{company} Philanthropies",
        "Ministry of {sector}",
        "{last_name} & Associates Giving Circle",
    ]

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.donors + 1):
            donor_type = self.weighted_choice(
                DONOR_TYPES,
                weights=[0.10, 0.05, 0.30, 0.20, 0.15, 0.10, 0.10],
            )
            donor_name = self._make_donor_name(donor_type)
            country = (
                "India"
                if donor_type
                in ("Corporate CSR", "Government Scheme", "Individual (HNI)")
                else self.fake.country()
            )

            rows.append(
                {
                    "donor_id": self.make_id("DON", i),
                    "donor_name": donor_name,
                    "donor_type": donor_type,
                    "country": country,
                    "contact_email": (
                        self.fake.company_email() if self.rng.random() > 0.2 else None
                    ),
                    "onboarded_date": self.random_date(
                        date(2018, 1, 1), DATA_START_DATE
                    ),
                }
            )

        return rows

    def _make_donor_name(self, donor_type: str) -> str:
        """Generate a contextual donor name based on type."""
        if donor_type == "Corporate CSR":
            return f"{self.fake.company()} CSR"
        if donor_type == "Government Scheme":
            sector = self.rng.choice(
                [
                    "Rural Development",
                    "Education",
                    "Health & Family Welfare",
                    "Women & Child Development",
                ]
            )
            return f"Ministry of {sector}"
        if donor_type == "Individual (HNI)":
            return f"{self.fake.name()} (Individual)"
        if donor_type == "Crowdfunding":
            return f"{self.fake.company()} Crowdfund Campaign"
        return self.rng.choice(self._DONOR_TEMPLATES).format(
            company=self.fake.company(),
            last_name=self.fake.last_name(),
            sector=self.rng.choice(PROGRAM_SECTORS),
        )


# =========================================================================
# PROGRAMS
# =========================================================================
class ProgramGenerator(BaseGenerator):
    """Generate the ``programs`` dimension table."""

    _PROGRAM_NAME_TEMPLATES: list[str] = [
        "Project {name} — {sector} Initiative",
        "{sector} Empowerment Program",
        "Mission {name}: {sector}",
        "{district} {sector} Outreach",
        "Pragati {sector} Programme",
        "Unnati {sector} Scheme",
    ]

    def __init__(self, region_ids: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._region_ids = region_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.programs + 1):
            sector = PROGRAM_SECTORS[(i - 1) % len(PROGRAM_SECTORS)]
            start = self.random_date(DATA_START_DATE, date(2023, 3, 31))
            end_date = (
                self.random_date(date(2024, 4, 1), DATA_END_DATE)
                if self.rng.random() > 0.3
                else None
            )
            status = (
                "Active"
                if end_date is None or end_date > date(2025, 1, 1)
                else "Completed"
            )

            name_template = self.rng.choice(self._PROGRAM_NAME_TEMPLATES)
            program_name = name_template.format(
                name=self.fake.first_name(),
                sector=sector,
                district=self.fake.city(),
            )

            rows.append(
                {
                    "program_id": self.make_id("PRG", i),
                    "program_name": program_name,
                    "sector": sector,
                    "start_date": start,
                    "end_date": end_date,
                    "target_beneficiaries": int(self.rng.integers(50, 500)),
                    "region_id": self.rng.choice(self._region_ids),
                    "status": status,
                }
            )

        return rows


# =========================================================================
# STAFF
# =========================================================================
class StaffGenerator(BaseGenerator):
    """Generate the ``staff`` dimension table."""

    _ROLES: list[str] = [
        "Field Coordinator",
        "Program Manager",
        "M&E Officer",
        "Community Health Worker",
        "Data Entry Operator",
        "District Lead",
        "Finance Officer",
        "Training Facilitator",
        "Social Worker",
        "Outreach Volunteer",
    ]

    def __init__(self, region_ids: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._region_ids = region_ids

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i in range(1, ROW_COUNTS.staff + 1):
            hire_date = self.random_date(date(2018, 1, 1), DATA_END_DATE)
            is_active = 1 if self.rng.random() > 0.15 else 0

            rows.append(
                {
                    "staff_id": self.make_id("STF", i),
                    "full_name": self.fake.name(),
                    "role": self.rng.choice(self._ROLES),
                    "region_id": self.rng.choice(self._region_ids),
                    "hire_date": hire_date,
                    "phone": self.indian_phone() if self.rng.random() > 0.1 else None,
                    "email": (
                        self.fake.company_email() if self.rng.random() > 0.05 else None
                    ),
                    "is_active": is_active,
                }
            )

        return rows


# =========================================================================
# IMPACT INDICATORS
# =========================================================================
class ImpactIndicatorGenerator(BaseGenerator):
    """Generate the ``impact_indicators`` table from IRIS+ catalog entries."""

    def _generate_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for i, indicator in enumerate(IRIS_INDICATORS, start=1):
            rows.append(
                {
                    "indicator_id": self.make_id("IND", i),
                    "iris_id": indicator.iris_id,
                    "indicator_name": indicator.name,
                    "category": indicator.category,
                    "unit": indicator.unit,
                    "sector": indicator.sector,
                }
            )

        return rows

"""
Configuration constants for the NGO Impact Dashboard synthetic data generator.

This module centralises all tunable parameters — seed values, distribution
weights, domain-specific enumerations, and noise injection rates — so that
every generator draws from a single source of truth.

Design decisions:
    - India-specific context (states, districts, INR currency).
    - Indian fiscal year: April → March.
    - Date range: FY 2021-22 to FY 2024-25 (4 fiscal years of data).
    - IRIS+ indicator IDs sourced from the GIIN catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED: Final[int] = 42

# ---------------------------------------------------------------------------
# Date boundaries (Indian Fiscal Year: April – March)
# ---------------------------------------------------------------------------
DATA_START_DATE: Final[date] = date(2021, 4, 1)  # FY 2021-22 start
DATA_END_DATE: Final[date] = date(2025, 3, 31)  # FY 2024-25 end


# ---------------------------------------------------------------------------
# Row-count targets
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RowCounts:
    """Target row counts for each generated table."""

    donors: int = 30
    programs: int = 12
    regions: int = 25
    staff: int = 60
    impact_indicators: int = 20
    interventions: int = 150
    funding: int = 80
    beneficiaries: int = 2000
    service_delivery: int = 2500
    assessments: int = 1800
    outcome_tracking: int = 200
    expenses: int = 300
    data_quality_log: int = 100


ROW_COUNTS: Final[RowCounts] = RowCounts()

# ---------------------------------------------------------------------------
# Indian geographic context
# ---------------------------------------------------------------------------
STATES_AND_DISTRICTS: Final[dict[str, list[str]]] = {
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Ajmer", "Kota"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane"],
    "Uttar Pradesh": ["Lucknow", "Varanasi", "Agra", "Kanpur", "Prayagraj"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Puri", "Rourkela"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubli", "Mangaluru"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "West Bengal": ["Kolkata", "Howrah", "Siliguri", "Durgapur"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro"],
}

REGION_TYPES: Final[list[str]] = ["Urban", "Semi-Urban", "Rural", "Tribal"]

# ---------------------------------------------------------------------------
# Program / intervention domain
# ---------------------------------------------------------------------------
PROGRAM_SECTORS: Final[list[str]] = [
    "Education",
    "Healthcare",
    "Livelihoods",
    "WASH",
    "Women Empowerment",
    "Agriculture",
    "Financial Inclusion",
    "Child Protection",
    "Nutrition",
    "Governance & Advocacy",
]

INTERVENTION_TYPES: Final[list[str]] = [
    "Workshop",
    "Training Program",
    "Community Meeting",
    "Home Visit",
    "Health Camp",
    "Distribution Drive",
    "Awareness Campaign",
    "Counselling Session",
    "Skill Development",
    "Microfinance Disbursement",
    "Monitoring Visit",
    "Vaccination Drive",
]

# ---------------------------------------------------------------------------
# Beneficiary demographics
# ---------------------------------------------------------------------------
GENDER_VALUES: Final[list[str]] = ["Male", "Female", "Non-Binary", "Prefer Not to Say"]
GENDER_WEIGHTS: Final[list[float]] = [0.40, 0.50, 0.02, 0.08]

EDUCATION_LEVELS: Final[list[str]] = [
    "No Formal Education",
    "Primary (1-5)",
    "Upper Primary (6-8)",
    "Secondary (9-10)",
    "Higher Secondary (11-12)",
    "Graduate",
    "Post-Graduate",
]

INCOME_BRACKETS: Final[list[str]] = [
    "BPL (Below ₹1 lakh)",
    "LIG (₹1-3 lakh)",
    "MIG (₹3-6 lakh)",
    "HIG (Above ₹6 lakh)",
]
INCOME_WEIGHTS: Final[list[float]] = [0.45, 0.35, 0.15, 0.05]

AGE_RANGE: Final[tuple[int, int]] = (5, 85)

# ---------------------------------------------------------------------------
# Donor archetypes
# ---------------------------------------------------------------------------
DONOR_TYPES: Final[list[str]] = [
    "Bilateral Agency",
    "Multilateral Agency",
    "Corporate CSR",
    "Private Foundation",
    "Individual (HNI)",
    "Government Scheme",
    "Crowdfunding",
]


# ---------------------------------------------------------------------------
# IRIS+ indicators (legitimate IDs from GIIN catalog)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class IRISIndicator:
    """Represents a single IRIS+ metric from the GIIN catalog."""

    iris_id: str
    name: str
    category: str
    unit: str
    sector: str


IRIS_INDICATORS: Final[list[IRISIndicator]] = [
    IRISIndicator(
        "PI4060", "Client Individuals: Total", "Output", "Count", "Cross-sector"
    ),
    IRISIndicator(
        "PI2345", "Educational Attainment", "Outcome", "Score (0-100)", "Education"
    ),
    IRISIndicator(
        "PI1479", "Earnings/Wage Improvement", "Outcome", "INR", "Livelihoods"
    ),
    IRISIndicator(
        "OI8869", "Units/Volume of Products Sold", "Output", "Count", "Agriculture"
    ),
    IRISIndicator(
        "PI9468", "Health Improvements: Beneficiaries", "Outcome", "Count", "Healthcare"
    ),
    IRISIndicator(
        "OI1120",
        "Operational Self-Sufficiency",
        "Outcome",
        "Percentage",
        "Financial Inclusion",
    ),
    IRISIndicator("PI3468", "Access to Clean Water", "Outcome", "Count", "WASH"),
    IRISIndicator("PI6298", "Women Empowered", "Outcome", "Count", "Women Empowerment"),
    IRISIndicator(
        "OI5765", "Savings Facilitated", "Output", "INR", "Financial Inclusion"
    ),
    IRISIndicator(
        "PI7098", "Civic Engagement", "Outcome", "Count", "Governance & Advocacy"
    ),
    IRISIndicator("PI1015", "Individuals Trained", "Output", "Count", "Education"),
    IRISIndicator("OI3160", "Jobs Created", "Outcome", "Count", "Livelihoods"),
    IRISIndicator("PI8590", "Immunisations Provided", "Output", "Count", "Healthcare"),
    IRISIndicator(
        "OI4721",
        "Agricultural Yield Improvement",
        "Outcome",
        "Percentage",
        "Agriculture",
    ),
    IRISIndicator(
        "PI5532", "Children Enrolled in School", "Outcome", "Count", "Education"
    ),
    IRISIndicator("OI6643", "Loans Disbursed", "Output", "INR", "Financial Inclusion"),
    IRISIndicator(
        "PI2201", "Malnutrition Cases Reduced", "Outcome", "Count", "Nutrition"
    ),
    IRISIndicator(
        "OI3378", "Community Groups Formed", "Output", "Count", "Governance & Advocacy"
    ),
    IRISIndicator(
        "PI9912",
        "Child Protection Cases Resolved",
        "Outcome",
        "Count",
        "Child Protection",
    ),
    IRISIndicator("OI4489", "Sanitation Facilities Built", "Output", "Count", "WASH"),
]


# ---------------------------------------------------------------------------
# Noise injection rates  (percentage of rows affected)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NoiseConfig:
    """Controls the degree of intentional data quality degradation."""

    null_rate: float = 0.12  # 12% NULLs in optional columns
    inconsistent_date_rate: float = 0.20  # 20% non-standard date formats
    duplicate_rate: float = 0.03  # 3% near-duplicate rows
    encoding_fuzz_rate: float = 0.05  # 5% name transliteration variants
    outlier_rate: float = 0.02  # 2% unrealistic values
    orphan_ref_rate: float = 0.01  # 1% broken FK references
    inconsistent_case_rate: float = 0.10  # 10% casing inconsistencies


NOISE_CONFIG: Final[NoiseConfig] = NoiseConfig()

# ---------------------------------------------------------------------------
# Assessment / outcome metrics
# ---------------------------------------------------------------------------
ASSESSMENT_TYPES: Final[list[str]] = [
    "Pre-Test",
    "Post-Test",
    "Midline Survey",
    "Endline Survey",
    "Spot Check",
    "Follow-Up Interview",
]

OUTCOME_STATUSES: Final[list[str]] = [
    "On Track",
    "At Risk",
    "Off Track",
    "Achieved",
    "Exceeded",
]

# ---------------------------------------------------------------------------
# Expense categories
# ---------------------------------------------------------------------------
EXPENSE_CATEGORIES: Final[list[str]] = [
    "Personnel",
    "Travel & Field",
    "Materials & Supplies",
    "Training & Capacity Building",
    "Infrastructure",
    "Monitoring & Evaluation",
    "Administrative Overhead",
    "Communication & Outreach",
]

# ---------------------------------------------------------------------------
# Service delivery statuses
# ---------------------------------------------------------------------------
SERVICE_STATUSES: Final[list[str]] = [
    "Completed",
    "Partially Completed",
    "Scheduled",
    "Cancelled",
    "No-Show",
]
SERVICE_STATUS_WEIGHTS: Final[list[float]] = [0.55, 0.15, 0.10, 0.10, 0.10]

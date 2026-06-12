"""
Relational schema definitions for the NGO Impact Dashboard.

This module defines the database schema using SQLAlchemy Core metadata,
supporting both ORM-style inspection and raw DDL export. The schema maps
directly to the Theory of Change results chain:

    Inputs (donors, funding, expenses)
    → Activities (programs, interventions, staff)
    → Outputs (beneficiaries, service_delivery)
    → Outcomes (assessments, outcome_tracking)
    → Impact (impact_indicators)

Target database: PostgreSQL 14+, with SQLite compatibility for local dev.
"""

from __future__ import annotations

import io
from typing import Final

from sqlalchemy import (
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.schema import CreateTable

# ---------------------------------------------------------------------------
# Shared metadata container
# ---------------------------------------------------------------------------
metadata: Final[MetaData] = MetaData()

# ---------------------------------------------------------------------------
# 1. REGIONS (cross-cutting dimension)
# ---------------------------------------------------------------------------
regions = Table(
    "regions",
    metadata,
    Column(
        "region_id",
        String(16),
        primary_key=True,
        comment="Unique region identifier (e.g., REG-001)",
    ),
    Column("state", String(64), nullable=False, comment="Indian state name"),
    Column("district", String(64), nullable=False, comment="District within the state"),
    Column(
        "block", String(64), nullable=True, comment="Administrative block (optional)"
    ),
    Column(
        "region_type",
        String(32),
        nullable=False,
        comment="Urban / Semi-Urban / Rural / Tribal",
    ),
    Column("latitude", Float, nullable=True, comment="GPS latitude for mapping"),
    Column("longitude", Float, nullable=True, comment="GPS longitude for mapping"),
    comment="Geographic regions where the NGO operates.",
)

# ---------------------------------------------------------------------------
# 2. DONORS (input)
# ---------------------------------------------------------------------------
donors = Table(
    "donors",
    metadata,
    Column(
        "donor_id",
        String(16),
        primary_key=True,
        comment="Unique donor identifier (e.g., DON-001)",
    ),
    Column(
        "donor_name",
        String(128),
        nullable=False,
        comment="Full name of the donor entity",
    ),
    Column(
        "donor_type",
        String(64),
        nullable=False,
        comment="Bilateral / Corporate CSR / Foundation / etc.",
    ),
    Column("country", String(64), nullable=False, comment="Country of origin"),
    Column(
        "contact_email", String(128), nullable=True, comment="Primary contact email"
    ),
    Column(
        "onboarded_date",
        Date,
        nullable=True,
        comment="Date the donor was first registered",
    ),
    comment="Funding sources for the NGO's programs.",
)

# ---------------------------------------------------------------------------
# 3. PROGRAMS (activity)
# ---------------------------------------------------------------------------
programs = Table(
    "programs",
    metadata,
    Column(
        "program_id",
        String(16),
        primary_key=True,
        comment="Unique program identifier (e.g., PRG-001)",
    ),
    Column(
        "program_name",
        String(128),
        nullable=False,
        comment="Descriptive name of the program",
    ),
    Column(
        "sector",
        String(64),
        nullable=False,
        comment="Thematic sector (Education, WASH, etc.)",
    ),
    Column("start_date", Date, nullable=False, comment="Program launch date"),
    Column(
        "end_date", Date, nullable=True, comment="Planned end date (NULL if ongoing)"
    ),
    Column(
        "target_beneficiaries",
        Integer,
        nullable=True,
        comment="Planned number of beneficiaries",
    ),
    Column(
        "region_id",
        String(16),
        ForeignKey("regions.region_id"),
        nullable=True,
        comment="Primary operating region",
    ),
    Column(
        "status", String(32), nullable=False, comment="Active / Completed / Suspended"
    ),
    comment="High-level programs aligned to the NGO's mission.",
)

# ---------------------------------------------------------------------------
# 4. STAFF (activity)
# ---------------------------------------------------------------------------
staff = Table(
    "staff",
    metadata,
    Column(
        "staff_id",
        String(16),
        primary_key=True,
        comment="Unique staff identifier (e.g., STF-001)",
    ),
    Column(
        "full_name", String(128), nullable=False, comment="Staff member's full name"
    ),
    Column("role", String(64), nullable=False, comment="Job title / role"),
    Column(
        "region_id",
        String(16),
        ForeignKey("regions.region_id"),
        nullable=True,
        comment="Assigned operating region",
    ),
    Column("hire_date", Date, nullable=True, comment="Date of joining"),
    Column("phone", String(20), nullable=True, comment="Contact phone number"),
    Column("email", String(128), nullable=True, comment="Work email address"),
    Column("is_active", Integer, nullable=False, comment="1 = active, 0 = inactive"),
    comment="Field workers, coordinators, and support staff.",
)

# ---------------------------------------------------------------------------
# 5. IMPACT_INDICATORS (impact — IRIS+)
# ---------------------------------------------------------------------------
impact_indicators = Table(
    "impact_indicators",
    metadata,
    Column(
        "indicator_id",
        String(16),
        primary_key=True,
        comment="Internal indicator ID (e.g., IND-001)",
    ),
    Column(
        "iris_id",
        String(16),
        nullable=False,
        comment="IRIS+ catalog metric ID (e.g., PI4060)",
    ),
    Column(
        "indicator_name",
        String(128),
        nullable=False,
        comment="Human-readable indicator name",
    ),
    Column("category", String(32), nullable=False, comment="Output / Outcome"),
    Column("unit", String(32), nullable=False, comment="Unit of measurement"),
    Column(
        "sector",
        String(64),
        nullable=False,
        comment="Thematic sector this indicator covers",
    ),
    comment="IRIS+ standardised impact metrics from the GIIN catalog.",
)

# ---------------------------------------------------------------------------
# 6. FUNDING (input)
# ---------------------------------------------------------------------------
funding = Table(
    "funding",
    metadata,
    Column(
        "funding_id", String(16), primary_key=True, comment="Unique funding record ID"
    ),
    Column(
        "donor_id",
        String(16),
        ForeignKey("donors.donor_id"),
        nullable=False,
        comment="Source donor",
    ),
    Column(
        "program_id",
        String(16),
        ForeignKey("programs.program_id"),
        nullable=False,
        comment="Receiving program",
    ),
    Column(
        "amount_inr",
        Numeric(15, 2),
        nullable=False,
        comment="Grant amount in Indian Rupees",
    ),
    Column(
        "currency",
        String(8),
        nullable=False,
        comment="Original currency code (INR, USD, etc.)",
    ),
    Column(
        "disbursement_date", Date, nullable=True, comment="Date funds were disbursed"
    ),
    Column(
        "fiscal_year",
        String(12),
        nullable=False,
        comment="Indian FY label (e.g., FY2023-24)",
    ),
    Column(
        "grant_type",
        String(32),
        nullable=True,
        comment="Restricted / Unrestricted / Project-Tied",
    ),
    comment="Financial inflows from donors to programs.",
)

# ---------------------------------------------------------------------------
# 7. INTERVENTIONS (activity)
# ---------------------------------------------------------------------------
interventions = Table(
    "interventions",
    metadata,
    Column(
        "intervention_id",
        String(16),
        primary_key=True,
        comment="Unique intervention ID",
    ),
    Column(
        "program_id",
        String(16),
        ForeignKey("programs.program_id"),
        nullable=False,
        comment="Parent program",
    ),
    Column(
        "intervention_type",
        String(64),
        nullable=False,
        comment="Workshop / Health Camp / etc.",
    ),
    Column(
        "title",
        String(256),
        nullable=False,
        comment="Descriptive title of the intervention",
    ),
    Column("scheduled_date", Date, nullable=False, comment="Planned date of delivery"),
    Column(
        "actual_date",
        Date,
        nullable=True,
        comment="Actual date delivered (NULL if not yet)",
    ),
    Column(
        "staff_id",
        String(16),
        ForeignKey("staff.staff_id"),
        nullable=True,
        comment="Lead facilitator",
    ),
    Column(
        "region_id",
        String(16),
        ForeignKey("regions.region_id"),
        nullable=True,
        comment="Delivery location",
    ),
    Column(
        "planned_attendance",
        Integer,
        nullable=True,
        comment="Expected number of attendees",
    ),
    Column(
        "actual_attendance",
        Integer,
        nullable=True,
        comment="Recorded number of attendees",
    ),
    comment="Specific activities delivered under a program.",
)

# ---------------------------------------------------------------------------
# 8. BENEFICIARIES (output)
# ---------------------------------------------------------------------------
beneficiaries = Table(
    "beneficiaries",
    metadata,
    Column(
        "beneficiary_id", String(16), primary_key=True, comment="Unique beneficiary ID"
    ),
    Column("full_name", String(128), nullable=False, comment="Beneficiary's full name"),
    Column("age", Integer, nullable=True, comment="Age in years at registration"),
    Column(
        "gender", String(32), nullable=True, comment="Male / Female / Non-Binary / etc."
    ),
    Column("phone", String(20), nullable=True, comment="Contact phone number"),
    Column(
        "education_level",
        String(64),
        nullable=True,
        comment="Highest education attained",
    ),
    Column(
        "income_bracket",
        String(64),
        nullable=True,
        comment="Annual household income bracket",
    ),
    Column(
        "region_id",
        String(16),
        ForeignKey("regions.region_id"),
        nullable=True,
        comment="Beneficiary's home region",
    ),
    Column(
        "registration_date",
        Date,
        nullable=True,
        comment="Date registered in the system",
    ),
    Column(
        "program_id",
        String(16),
        ForeignKey("programs.program_id"),
        nullable=True,
        comment="Primary program enrolled in",
    ),
    Column(
        "household_size", Integer, nullable=True, comment="Number of household members"
    ),
    Column(
        "is_disabled",
        Integer,
        nullable=True,
        comment="1 = yes, 0 = no, NULL = not recorded",
    ),
    comment="Individuals receiving services from the NGO.",
)

# ---------------------------------------------------------------------------
# 9. SERVICE_DELIVERY (output)
# ---------------------------------------------------------------------------
service_delivery = Table(
    "service_delivery",
    metadata,
    Column(
        "delivery_id", String(16), primary_key=True, comment="Unique delivery record ID"
    ),
    Column(
        "beneficiary_id",
        String(16),
        ForeignKey("beneficiaries.beneficiary_id"),
        nullable=False,
        comment="Beneficiary who received the service",
    ),
    Column(
        "intervention_id",
        String(16),
        ForeignKey("interventions.intervention_id"),
        nullable=False,
        comment="Intervention under which service was delivered",
    ),
    Column(
        "delivery_date", Date, nullable=False, comment="Date the service was provided"
    ),
    Column(
        "status",
        String(32),
        nullable=False,
        comment="Completed / Partially Completed / No-Show",
    ),
    Column(
        "dosage", Integer, nullable=True, comment="Number of sessions / units received"
    ),
    Column("notes", Text, nullable=True, comment="Field worker's free-text notes"),
    comment="Records of individual services delivered to beneficiaries.",
)

# ---------------------------------------------------------------------------
# 10. ASSESSMENTS (outcome)
# ---------------------------------------------------------------------------
assessments = Table(
    "assessments",
    metadata,
    Column(
        "assessment_id",
        String(16),
        primary_key=True,
        comment="Unique assessment record ID",
    ),
    Column(
        "beneficiary_id",
        String(16),
        ForeignKey("beneficiaries.beneficiary_id"),
        nullable=False,
        comment="Assessed beneficiary",
    ),
    Column(
        "intervention_id",
        String(16),
        ForeignKey("interventions.intervention_id"),
        nullable=True,
        comment="Related intervention (if applicable)",
    ),
    Column(
        "assessment_type",
        String(64),
        nullable=False,
        comment="Pre-Test / Post-Test / Survey / etc.",
    ),
    Column(
        "assessment_date",
        Date,
        nullable=False,
        comment="Date the assessment was conducted",
    ),
    Column(
        "score", Float, nullable=True, comment="Numeric score (scale depends on type)"
    ),
    Column("max_score", Float, nullable=True, comment="Maximum possible score"),
    Column(
        "assessor_staff_id",
        String(16),
        ForeignKey("staff.staff_id"),
        nullable=True,
        comment="Staff member who conducted the assessment",
    ),
    Column(
        "remarks", Text, nullable=True, comment="Qualitative notes from the assessor"
    ),
    comment="Pre/post assessments and surveys measuring beneficiary outcomes.",
)

# ---------------------------------------------------------------------------
# 11. OUTCOME_TRACKING (outcome)
# ---------------------------------------------------------------------------
outcome_tracking = Table(
    "outcome_tracking",
    metadata,
    Column(
        "outcome_id", String(16), primary_key=True, comment="Unique outcome tracking ID"
    ),
    Column(
        "program_id",
        String(16),
        ForeignKey("programs.program_id"),
        nullable=False,
        comment="Program being tracked",
    ),
    Column(
        "indicator_id",
        String(16),
        ForeignKey("impact_indicators.indicator_id"),
        nullable=False,
        comment="IRIS+ indicator being measured",
    ),
    Column(
        "reporting_period",
        String(16),
        nullable=False,
        comment="Quarter label (e.g., Q1-FY2023-24)",
    ),
    Column(
        "target_value", Float, nullable=True, comment="Planned target for this period"
    ),
    Column(
        "actual_value", Float, nullable=True, comment="Achieved value for this period"
    ),
    Column(
        "status",
        String(32),
        nullable=False,
        comment="On Track / At Risk / Achieved / etc.",
    ),
    Column(
        "data_source",
        String(128),
        nullable=True,
        comment="Where the data was collected from",
    ),
    Column(
        "verified_by",
        String(16),
        ForeignKey("staff.staff_id"),
        nullable=True,
        comment="Staff member who verified the data",
    ),
    comment="Periodic tracking of program outcomes against IRIS+ indicators.",
)

# ---------------------------------------------------------------------------
# 12. EXPENSES (input — financial)
# ---------------------------------------------------------------------------
expenses = Table(
    "expenses",
    metadata,
    Column(
        "expense_id", String(16), primary_key=True, comment="Unique expense record ID"
    ),
    Column(
        "program_id",
        String(16),
        ForeignKey("programs.program_id"),
        nullable=False,
        comment="Program the expense is charged to",
    ),
    Column("category", String(64), nullable=False, comment="Expense category"),
    Column(
        "amount_inr", Numeric(15, 2), nullable=False, comment="Amount in Indian Rupees"
    ),
    Column(
        "expense_date", Date, nullable=False, comment="Date the expense was incurred"
    ),
    Column("fiscal_year", String(12), nullable=False, comment="Indian FY label"),
    Column(
        "approved_by",
        String(16),
        ForeignKey("staff.staff_id"),
        nullable=True,
        comment="Staff member who approved the expense",
    ),
    Column("receipt_available", Integer, nullable=True, comment="1 = yes, 0 = no"),
    comment="Financial outflows / expenditures against programs.",
)

# ---------------------------------------------------------------------------
# 13. DATA_QUALITY_LOG (meta)
# ---------------------------------------------------------------------------
data_quality_log = Table(
    "data_quality_log",
    metadata,
    Column("log_id", String(16), primary_key=True, comment="Unique log entry ID"),
    Column(
        "table_name",
        String(64),
        nullable=False,
        comment="Table where the issue was found",
    ),
    Column(
        "column_name", String(64), nullable=True, comment="Specific column affected"
    ),
    Column("record_id", String(16), nullable=True, comment="ID of the affected record"),
    Column(
        "issue_type", String(64), nullable=False, comment="Type of data quality issue"
    ),
    Column(
        "description",
        Text,
        nullable=True,
        comment="Human-readable description of the issue",
    ),
    Column("detected_date", Date, nullable=False, comment="Date the issue was logged"),
    Column("resolved", Integer, nullable=False, comment="1 = resolved, 0 = open"),
    comment="Audit trail of data quality issues detected during cleaning.",
)


# ---------------------------------------------------------------------------
# DDL export utilities
# ---------------------------------------------------------------------------
def generate_ddl(dialect: str = "postgresql") -> str:
    """
    Generate CREATE TABLE DDL statements for the entire schema.

    Args:
        dialect: Target SQL dialect. Supports 'postgresql' and 'sqlite'.

    Returns:
        A single string containing all DDL statements.

    Raises:
        ValueError: If an unsupported dialect is provided.
    """
    supported_dialects = {"postgresql", "sqlite"}
    if dialect not in supported_dialects:
        raise ValueError(
            f"Unsupported dialect '{dialect}'. Choose from: {supported_dialects}"
        )

    engine = create_engine(f"{dialect}://", strategy="mock", executor=_ddl_collector)
    buffer = io.StringIO()

    for table in metadata.sorted_tables:
        ddl_statement = CreateTable(table).compile(engine)
        buffer.write(str(ddl_statement).strip())
        buffer.write(";\n\n")

    return buffer.getvalue()


def _ddl_collector(sql: str, *args, **kwargs) -> None:
    """No-op executor used by the mock engine for DDL generation."""
    pass


def export_ddl_to_file(filepath: str, dialect: str = "postgresql") -> None:
    """
    Write DDL statements to a SQL file.

    Args:
        filepath: Output file path.
        dialect: Target SQL dialect.
    """
    ddl = generate_ddl(dialect=dialect)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(f"-- NGO Impact Dashboard — DDL ({dialect})\n")
        fh.write("-- Auto-generated schema definition\n")
        fh.write(f"-- Tables: {len(metadata.sorted_tables)}\n\n")
        fh.write(ddl)

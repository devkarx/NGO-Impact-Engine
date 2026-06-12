"""
Cleaning pipeline orchestrator.

Composes the individual cleaners from ``cleaners.py`` into a complete
table-by-table pipeline, respecting dependency order (parent tables
must be cleaned before child tables for FK validation).

Produces a full audit report summarising every cleaning step across
every table — designed to be exported as a cleaning manifest that
an M&E officer can review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from phase2_cleaning.cleaners import (
    CleaningReport,
    cast_types,
    check_referential_integrity,
    deduplicate,
    impute_missing,
    normalise_dates,
    standardise_categoricals,
    treat_outliers,
)
from phase2_cleaning.config import CLEANING_CONFIG, CleaningConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline report
# ---------------------------------------------------------------------------
@dataclass
class PipelineReport:
    """
    Aggregate report for the entire cleaning pipeline run.

    Attributes:
        table_reports: Per-table, per-step cleaning reports.
        summary: High-level summary statistics.
    """

    table_reports: dict[str, list[CleaningReport]] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def add_report(self, report: CleaningReport) -> None:
        """Add a single step report to the appropriate table bucket."""
        if report.table_name not in self.table_reports:
            self.table_reports[report.table_name] = []
        self.table_reports[report.table_name].append(report)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all reports to a flat DataFrame for export."""
        rows: list[dict[str, Any]] = []
        for table_name, reports in self.table_reports.items():
            for report in reports:
                rows.append(
                    {
                        "table_name": table_name,
                        "step": report.step,
                        "rows_before": report.rows_before,
                        "rows_after": report.rows_after,
                        "rows_affected": report.rows_affected,
                        "details": " | ".join(report.details),
                    }
                )
        return pd.DataFrame(rows)

    def print_summary(self) -> None:
        """Log a human-readable summary of the cleaning run."""
        logger.info("═══ Cleaning Pipeline Summary ═══")
        for table_name, reports in self.table_reports.items():
            total_affected = sum(r.rows_affected for r in reports)
            initial_rows = reports[0].rows_before if reports else 0
            final_rows = reports[-1].rows_after if reports else 0
            logger.info(
                "  %-22s: %d → %d rows (%d modifications across %d steps)",
                table_name,
                initial_rows,
                final_rows,
                total_affected,
                len(reports),
            )


# ---------------------------------------------------------------------------
# FK relationship registry
# ---------------------------------------------------------------------------
# Maps: child_table → list of (fk_column, parent_table, parent_pk)
FK_RELATIONSHIPS: dict[str, list[tuple[str, str, str]]] = {
    "programs": [("region_id", "regions", "region_id")],
    "staff": [("region_id", "regions", "region_id")],
    "funding": [
        ("donor_id", "donors", "donor_id"),
        ("program_id", "programs", "program_id"),
    ],
    "interventions": [
        ("program_id", "programs", "program_id"),
        ("staff_id", "staff", "staff_id"),
        ("region_id", "regions", "region_id"),
    ],
    "beneficiaries": [
        ("region_id", "regions", "region_id"),
        ("program_id", "programs", "program_id"),
    ],
    "service_delivery": [
        ("beneficiary_id", "beneficiaries", "beneficiary_id"),
        ("intervention_id", "interventions", "intervention_id"),
    ],
    "assessments": [
        ("beneficiary_id", "beneficiaries", "beneficiary_id"),
        ("intervention_id", "interventions", "intervention_id"),
        ("assessor_staff_id", "staff", "staff_id"),
    ],
    "outcome_tracking": [
        ("program_id", "programs", "program_id"),
        ("indicator_id", "impact_indicators", "indicator_id"),
        ("verified_by", "staff", "staff_id"),
    ],
    "expenses": [
        ("program_id", "programs", "program_id"),
        ("approved_by", "staff", "staff_id"),
    ],
}

# Table-level primary key mapping
TABLE_PK: dict[str, str] = {
    "regions": "region_id",
    "donors": "donor_id",
    "programs": "program_id",
    "staff": "staff_id",
    "impact_indicators": "indicator_id",
    "funding": "funding_id",
    "interventions": "intervention_id",
    "beneficiaries": "beneficiary_id",
    "service_delivery": "delivery_id",
    "assessments": "assessment_id",
    "outcome_tracking": "outcome_id",
    "expenses": "expense_id",
    "data_quality_log": "log_id",
}

# Cleaning order: parents before children
CLEANING_ORDER: list[str] = [
    "regions",
    "donors",
    "impact_indicators",
    "programs",
    "staff",
    "funding",
    "interventions",
    "beneficiaries",
    "service_delivery",
    "assessments",
    "outcome_tracking",
    "expenses",
]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(
    tables: dict[str, pd.DataFrame],
    config: CleaningConfig | None = None,
) -> tuple[dict[str, pd.DataFrame], PipelineReport]:
    """
    Execute the full cleaning pipeline across all tables.

    Processing order is topologically sorted so that parent tables
    are cleaned before child tables, enabling FK validation.

    Steps per table:
        1. Deduplication
        2. Date normalisation
        3. Categorical standardisation
        4. Outlier treatment
        5. Imputation
        6. FK integrity check (against already-cleaned parents)
        7. Type casting

    Args:
        tables: Dictionary of table_name → dirty DataFrame.
        config: Optional cleaning config (defaults to CLEANING_CONFIG).

    Returns:
        Tuple of (cleaned tables dict, PipelineReport).
    """
    if config is None:
        config = CLEANING_CONFIG

    report = PipelineReport()
    cleaned: dict[str, pd.DataFrame] = {}

    logger.info("═══ Starting Cleaning Pipeline ═══")
    logger.info("Tables to process: %d", len(CLEANING_ORDER))

    for table_name in CLEANING_ORDER:
        if table_name not in tables:
            logger.warning("Table '%s' not found in input, skipping", table_name)
            continue

        df = tables[table_name].copy()
        pk = TABLE_PK.get(table_name, "")

        logger.info("─── Cleaning: %s (%d rows) ───", table_name, len(df))

        # 1. Deduplication
        if pk:
            df, r = deduplicate(df, table_name, pk, config)
            report.add_report(r)

        # 2. Date normalisation
        df, r = normalise_dates(df, table_name, config)
        report.add_report(r)

        # 3. Categorical standardisation
        df, r = standardise_categoricals(df, table_name, config)
        report.add_report(r)

        # 4. Outlier treatment
        df, r = treat_outliers(df, table_name, config)
        report.add_report(r)

        # 5. Imputation
        df, r = impute_missing(df, table_name, config)
        report.add_report(r)

        # 6. FK integrity (check against already-cleaned parent tables)
        fk_rels = FK_RELATIONSHIPS.get(table_name, [])
        for fk_col, parent_table, parent_pk in fk_rels:
            if parent_table in cleaned:
                df, r = check_referential_integrity(
                    df, table_name, fk_col, cleaned[parent_table], parent_pk
                )
                report.add_report(r)

        # 7. Type casting
        df, r = cast_types(df, table_name)
        report.add_report(r)

        cleaned[table_name] = df
        logger.info("─── Done: %s → %d rows ───", table_name, len(df))

    # Copy over data_quality_log as-is (meta table, not cleaned)
    if "data_quality_log" in tables:
        cleaned["data_quality_log"] = tables["data_quality_log"].copy()

    report.print_summary()
    return cleaned, report

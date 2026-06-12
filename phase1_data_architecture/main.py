"""
Phase 1 orchestrator — generates all synthetic tables and exports to CSV + SQLite.

Usage::

    # Default: generate with noise, output to ./output/
    python -m phase1_data_architecture.main

    # Custom seed, no noise, specific output directory
    python -m phase1_data_architecture.main --seed 123 --no-noise --output-dir ./data

    # Help
    python -m phase1_data_architecture.main --help
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from phase1_data_architecture.config import RANDOM_SEED, ROW_COUNTS
from phase1_data_architecture.generators.base import BaseGenerator
from phase1_data_architecture.generators.dimension_generators import (
    DonorGenerator,
    ImpactIndicatorGenerator,
    ProgramGenerator,
    RegionGenerator,
    StaffGenerator,
)
from phase1_data_architecture.generators.fact_generators import (
    AssessmentGenerator,
    BeneficiaryGenerator,
    ExpenseGenerator,
    FundingGenerator,
    InterventionGenerator,
    OutcomeTrackingGenerator,
    ServiceDeliveryGenerator,
)
from phase1_data_architecture.generators.noise_injector import (
    NoiseInjector,
    QualityIssue,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def _configure_logging(verbose: bool = False) -> None:
    """Configure structured logging with optional colour support."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    try:
        import colorlog

        handler = colorlog.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter(
                f"%(log_color)s{fmt}",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    except ImportError:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------
def generate_all(
    seed: int = RANDOM_SEED,
    inject_noise: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Generate all 13 tables in dependency order.

    Args:
        seed: Random seed for reproducibility.
        inject_noise: Whether to inject data quality issues.

    Returns:
        Dictionary mapping table names to DataFrames.
    """
    tables: dict[str, pd.DataFrame] = {}

    # ── Step 1: Dimension tables (no FK dependencies) ─────────────────
    logger.info("═══ Phase 1: Generating dimension tables ═══")

    regions_gen = RegionGenerator(seed=seed)
    tables["regions"] = regions_gen.generate()
    region_ids = tables["regions"]["region_id"].tolist()

    donors_gen = DonorGenerator(seed=seed)
    tables["donors"] = donors_gen.generate()
    donor_ids = tables["donors"]["donor_id"].tolist()

    programs_gen = ProgramGenerator(region_ids=region_ids, seed=seed)
    tables["programs"] = programs_gen.generate()
    program_ids = tables["programs"]["program_id"].tolist()

    staff_gen = StaffGenerator(region_ids=region_ids, seed=seed)
    tables["staff"] = staff_gen.generate()
    staff_ids = tables["staff"]["staff_id"].tolist()

    indicators_gen = ImpactIndicatorGenerator(seed=seed)
    tables["impact_indicators"] = indicators_gen.generate()
    indicator_ids = tables["impact_indicators"]["indicator_id"].tolist()

    # ── Step 2: Fact tables (depend on dimensions) ────────────────────
    logger.info("═══ Phase 2: Generating fact tables ═══")

    ben_gen = BeneficiaryGenerator(
        region_ids=region_ids, program_ids=program_ids, seed=seed
    )
    tables["beneficiaries"] = ben_gen.generate()
    beneficiary_ids = tables["beneficiaries"]["beneficiary_id"].tolist()

    funding_gen = FundingGenerator(
        donor_ids=donor_ids, program_ids=program_ids, seed=seed
    )
    tables["funding"] = funding_gen.generate()

    intervention_gen = InterventionGenerator(
        program_ids=program_ids,
        staff_ids=staff_ids,
        region_ids=region_ids,
        programs_df=tables["programs"],
        seed=seed,
    )
    tables["interventions"] = intervention_gen.generate()
    intervention_ids = tables["interventions"]["intervention_id"].tolist()

    svc_gen = ServiceDeliveryGenerator(
        beneficiary_ids=beneficiary_ids,
        intervention_ids=intervention_ids,
        interventions_df=tables["interventions"],
        seed=seed,
    )
    tables["service_delivery"] = svc_gen.generate()

    asm_gen = AssessmentGenerator(
        beneficiary_ids=beneficiary_ids,
        intervention_ids=intervention_ids,
        staff_ids=staff_ids,
        seed=seed,
    )
    tables["assessments"] = asm_gen.generate()

    outcome_gen = OutcomeTrackingGenerator(
        program_ids=program_ids,
        indicator_ids=indicator_ids,
        staff_ids=staff_ids,
        seed=seed,
    )
    tables["outcome_tracking"] = outcome_gen.generate()

    expense_gen = ExpenseGenerator(
        program_ids=program_ids, staff_ids=staff_ids, seed=seed
    )
    tables["expenses"] = expense_gen.generate()

    # ── Step 3: Noise injection ───────────────────────────────────────
    all_issues: list[QualityIssue] = []

    if inject_noise:
        logger.info("═══ Phase 3: Injecting data quality issues ═══")
        injector = NoiseInjector(seed=seed)

        # Beneficiaries: heaviest noise target
        tables["beneficiaries"], issues = injector.inject_all(
            df=tables["beneficiaries"],
            table_name="beneficiaries",
            id_column="beneficiary_id",
            date_columns=["registration_date"],
            categorical_columns=["gender"],
            name_columns=["full_name"],
            nullable_columns=["phone", "age", "income_bracket", "education_level"],
            numeric_columns=["age", "household_size"],
        )
        all_issues.extend(issues)

        # Service delivery
        tables["service_delivery"], issues = injector.inject_all(
            df=tables["service_delivery"],
            table_name="service_delivery",
            id_column="delivery_id",
            date_columns=["delivery_date"],
            categorical_columns=["status"],
            nullable_columns=["dosage", "notes"],
        )
        all_issues.extend(issues)

        # Assessments
        tables["assessments"], issues = injector.inject_all(
            df=tables["assessments"],
            table_name="assessments",
            id_column="assessment_id",
            date_columns=["assessment_date"],
            categorical_columns=["assessment_type"],
            nullable_columns=["score", "remarks"],
            numeric_columns=["score"],
        )
        all_issues.extend(issues)

        # Funding
        tables["funding"], issues = injector.inject_all(
            df=tables["funding"],
            table_name="funding",
            id_column="funding_id",
            date_columns=["disbursement_date"],
            nullable_columns=["grant_type"],
        )
        all_issues.extend(issues)

        # Staff
        tables["staff"], issues = injector.inject_all(
            df=tables["staff"],
            table_name="staff",
            id_column="staff_id",
            name_columns=["full_name"],
            nullable_columns=["phone", "email"],
        )
        all_issues.extend(issues)

    # ── Step 4: Data quality log ──────────────────────────────────────
    log_rows: list[dict[str, Any]] = []
    for i, issue in enumerate(all_issues[: ROW_COUNTS.data_quality_log], start=1):
        log_rows.append(
            {
                "log_id": BaseGenerator.make_id("DQL", i),
                "table_name": issue.table_name,
                "column_name": issue.column_name,
                "record_id": issue.record_id,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "detected_date": date.today(),
                "resolved": 0,
            }
        )
    tables["data_quality_log"] = pd.DataFrame(log_rows)

    # ── Summary ───────────────────────────────────────────────────────
    total_rows = sum(len(df) for df in tables.values())
    logger.info("═══ Generation complete ═══")
    logger.info("Tables: %d | Total rows: %d", len(tables), total_rows)
    for name, df in tables.items():
        logger.info("  %-22s %6d rows  ×  %2d cols", name, len(df), len(df.columns))

    return tables


# ---------------------------------------------------------------------------
# Export utilities
# ---------------------------------------------------------------------------
def export_to_csv(tables: dict[str, pd.DataFrame], output_dir: str) -> None:
    """Write each table as a CSV file to the output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        filepath = out_path / f"{name}.csv"
        df.to_csv(filepath, index=False, encoding="utf-8")
        logger.info("Exported: %s (%d rows)", filepath, len(df))


def export_to_sqlite(tables: dict[str, pd.DataFrame], db_path: str) -> None:
    """Write all tables to a SQLite database file."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB to ensure clean state
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    try:
        for name, df in tables.items():
            df.to_sql(name, conn, index=False, if_exists="replace")
            logger.info("Loaded into SQLite: %s (%d rows)", name, len(df))
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    logger.info("SQLite database written to: %s", path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="ngo-data-generator",
        description="Generate synthetic NGO M&E datasets for the Impact Dashboard.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed for reproducibility (default: {RANDOM_SEED})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory for CSV output (default: ./output)",
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default="./output/ngo_impact.db",
        help="Path for the SQLite database (default: ./output/ngo_impact.db)",
    )
    parser.add_argument(
        "--no-noise",
        action="store_true",
        help="Generate clean data without noise injection",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the synthetic data generator."""
    args = parse_args(argv)
    _configure_logging(verbose=args.verbose)

    logger.info("NGO Impact Dashboard — Synthetic Data Generator")
    logger.info("Seed: %d | Noise: %s", args.seed, not args.no_noise)

    tables = generate_all(seed=args.seed, inject_noise=not args.no_noise)
    export_to_csv(tables, output_dir=args.output_dir)
    export_to_sqlite(tables, db_path=args.sqlite_path)

    logger.info("✅ All exports complete. Ready for Phase 2 cleaning.")


if __name__ == "__main__":
    main()

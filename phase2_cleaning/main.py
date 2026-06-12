"""
Phase 2 CLI entry point — runs the cleaning pipeline end-to-end.

Usage::

    # Generate messy data (Phase 1) → clean it (Phase 2) → export
    python -m phase2_cleaning.main

    # Clean from existing dirty CSVs
    python -m phase2_cleaning.main --input-dir ./output --output-dir ./output/cleaned

    # Generate fresh data inline and clean (all-in-one)
    python -m phase2_cleaning.main --generate --seed 42

    # Help
    python -m phase2_cleaning.main --help
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

import pandas as pd

from phase2_cleaning.pipeline import run_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging
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
    # Avoid duplicate handlers on re-import
    if not root.handlers:
        root.addHandler(handler)


# ---------------------------------------------------------------------------
# I/O utilities
# ---------------------------------------------------------------------------
def load_dirty_csvs(input_dir: str) -> dict[str, pd.DataFrame]:
    """
    Load all CSV files from the input directory.

    Args:
        input_dir: Path to directory containing dirty CSV files.

    Returns:
        Dictionary mapping table names to DataFrames.

    Raises:
        FileNotFoundError: If the input directory doesn't exist.
        ValueError: If no CSV files are found.
    """
    path = Path(input_dir)
    if not path.exists():
        raise FileNotFoundError(f"Input directory not found: {path}")

    csv_files = list(path.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in: {path}")

    tables: dict[str, pd.DataFrame] = {}
    for csv_file in csv_files:
        table_name = csv_file.stem
        tables[table_name] = pd.read_csv(csv_file, encoding="utf-8")
        logger.info("Loaded: %s (%d rows)", csv_file.name, len(tables[table_name]))

    return tables


def export_cleaned_csvs(
    tables: dict[str, pd.DataFrame],
    output_dir: str,
) -> None:
    """Write cleaned DataFrames to CSV files."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        filepath = out_path / f"{name}.csv"
        df.to_csv(filepath, index=False, encoding="utf-8")
        logger.info("Exported clean: %s (%d rows)", filepath, len(df))


def export_cleaned_sqlite(
    tables: dict[str, pd.DataFrame],
    db_path: str,
) -> None:
    """Write cleaned DataFrames to a SQLite database."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    try:
        for name, df in tables.items():
            df.to_sql(name, conn, index=False, if_exists="replace")
            logger.info("SQLite: %s (%d rows)", name, len(df))
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    logger.info("Clean SQLite database written to: %s", path)


def export_audit_report(
    report_df: pd.DataFrame,
    output_dir: str,
) -> None:
    """Export the cleaning audit report as a CSV."""
    out_path = Path(output_dir) / "cleaning_audit_report.csv"
    report_df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("Audit report exported: %s", out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="ngo-data-cleaner",
        description="Clean messy NGO M&E datasets for BI ingestion.",
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./output",
        help="Directory containing dirty CSV files (default: ./output)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output/cleaned",
        help="Directory for cleaned CSV output (default: ./output/cleaned)",
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default="./output/cleaned/ngo_impact_clean.db",
        help="Path for clean SQLite database",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate fresh synthetic data before cleaning (runs Phase 1 inline)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for data generation (only used with --generate)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the cleaning pipeline."""
    args = parse_args(argv)
    _configure_logging(verbose=args.verbose)

    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║  NGO Impact Dashboard — Data Cleaning Pipeline  ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # ── Load or generate data ─────────────────────────────────────
    if args.generate:
        logger.info("Generating fresh synthetic data (seed=%d)...", args.seed)
        from phase1_data_architecture.main import generate_all, export_to_csv

        dirty_tables = generate_all(seed=args.seed, inject_noise=True)
        export_to_csv(dirty_tables, output_dir=args.input_dir)
    else:
        logger.info("Loading dirty CSVs from: %s", args.input_dir)
        dirty_tables = load_dirty_csvs(args.input_dir)

    # ── Run cleaning pipeline ─────────────────────────────────────
    cleaned_tables, report = run_pipeline(dirty_tables)

    # ── Export cleaned outputs ────────────────────────────────────
    export_cleaned_csvs(cleaned_tables, output_dir=args.output_dir)
    export_cleaned_sqlite(cleaned_tables, db_path=args.sqlite_path)
    export_audit_report(report.to_dataframe(), output_dir=args.output_dir)

    # ── Final summary ─────────────────────────────────────────────
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║  ✅ Cleaning complete. Outputs ready for BI.    ║")
    logger.info("╚══════════════════════════════════════════════════╝")
    logger.info("Clean CSVs:   %s", args.output_dir)
    logger.info("Clean SQLite: %s", args.sqlite_path)
    logger.info("Audit report: %s/cleaning_audit_report.csv", args.output_dir)


if __name__ == "__main__":
    main()

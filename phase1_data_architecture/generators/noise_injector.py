"""
Controlled noise injection for synthetic NGO datasets.

This module simulates the real-world data quality problems endemic to
NGO field data collection: inconsistent date formats from paper forms
digitised by different data entry operators, duplicate beneficiary
registrations across program sites, transliteration variants of Hindi
names, and the perennial problem of missing phone numbers.

Each noise method operates on a DataFrame in-place and returns a log
of injected issues for the ``data_quality_log`` table.

Design principle: noise is *deterministic* given the same seed, so that
the cleaning pipeline can be validated against known corruptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from phase1_data_architecture.config import NOISE_CONFIG, RANDOM_SEED

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """Structured log entry for a single data quality issue."""

    table_name: str
    column_name: str | None
    record_id: str | None
    issue_type: str
    description: str


class NoiseInjector:
    """
    Injects controlled, realistic data quality issues into DataFrames.

    Usage::

        injector = NoiseInjector(seed=42)
        dirty_df, issues = injector.inject_all(
            df=clean_df,
            table_name="beneficiaries",
            id_column="beneficiary_id",
            date_columns=["registration_date"],
            categorical_columns=["gender"],
            name_columns=["full_name"],
            nullable_columns=["phone", "age", "income_bracket"],
        )

    Attributes:
        config: NoiseConfig controlling corruption rates.
        rng: Seeded NumPy random generator.
        issues: Accumulated quality issue log.
    """

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self.rng = np.random.default_rng(seed)
        self.config = NOISE_CONFIG
        self.issues: list[QualityIssue] = []

    # ------------------------------------------------------------------
    # Main orchestrator
    # ------------------------------------------------------------------
    def inject_all(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        date_columns: list[str] | None = None,
        categorical_columns: list[str] | None = None,
        name_columns: list[str] | None = None,
        nullable_columns: list[str] | None = None,
        numeric_columns: list[str] | None = None,
    ) -> tuple[pd.DataFrame, list[QualityIssue]]:
        """
        Apply all noise injection methods to a DataFrame.

        Args:
            df: Clean DataFrame to corrupt.
            table_name: Name of the table (for logging).
            id_column: Primary key column name.
            date_columns: Columns containing dates to corrupt formats.
            categorical_columns: Columns to apply casing inconsistencies.
            name_columns: Columns with names for transliteration fuzzing.
            nullable_columns: Columns where NULLs should be injected.
            numeric_columns: Columns where outliers should be injected.

        Returns:
            Tuple of (corrupted DataFrame, list of QualityIssue logs).
        """
        self.issues = []
        dirty = df.copy()

        logger.info("Injecting noise into '%s' (%d rows)", table_name, len(dirty))

        if nullable_columns:
            dirty = self._inject_nulls(dirty, table_name, id_column, nullable_columns)

        if date_columns:
            dirty = self._corrupt_dates(dirty, table_name, id_column, date_columns)

        if categorical_columns:
            dirty = self._corrupt_categoricals(
                dirty, table_name, id_column, categorical_columns
            )

        if name_columns:
            dirty = self._fuzz_names(dirty, table_name, id_column, name_columns)

        if numeric_columns:
            dirty = self._add_outliers(dirty, table_name, id_column, numeric_columns)

        # Duplicates (appended rows)
        dirty = self._add_duplicates(dirty, table_name, id_column)

        logger.info(
            "Noise injection complete for '%s': %d issues logged, %d final rows",
            table_name,
            len(self.issues),
            len(dirty),
        )
        return dirty, self.issues

    # ------------------------------------------------------------------
    # NULL injection
    # ------------------------------------------------------------------
    def _inject_nulls(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        columns: list[str],
    ) -> pd.DataFrame:
        """Set random cells to None/NaN in the specified columns."""
        n_rows = len(df)
        n_corrupt = max(1, int(n_rows * self.config.null_rate))

        for col in columns:
            if col not in df.columns:
                logger.warning(
                    "Column '%s' not found in '%s', skipping NULL injection",
                    col,
                    table_name,
                )
                continue

            indices = self.rng.choice(n_rows, size=n_corrupt, replace=False)
            for idx in indices:
                record_id = (
                    str(df.iloc[idx][id_column]) if id_column in df.columns else None
                )
                df.at[df.index[idx], col] = None
                self.issues.append(
                    QualityIssue(
                        table_name=table_name,
                        column_name=col,
                        record_id=record_id,
                        issue_type="missing_value",
                        description=f"NULL injected into '{col}'",
                    )
                )

        logger.debug("Injected NULLs into %d columns of '%s'", len(columns), table_name)
        return df

    # ------------------------------------------------------------------
    # Date format corruption
    # ------------------------------------------------------------------
    def _corrupt_dates(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        columns: list[str],
    ) -> pd.DataFrame:
        """
        Convert a fraction of date values to inconsistent string formats.

        Simulates what happens when paper forms are digitised by different
        data entry operators using DD/MM/YYYY, DD-Mon-YY, etc.
        """
        n_rows = len(df)
        n_corrupt = max(1, int(n_rows * self.config.inconsistent_date_rate))
        alt_formats = ["%d/%m/%Y", "%d-%b-%y", "%m-%d-%Y", "%d.%m.%Y", "%Y/%m/%d"]

        for col in columns:
            if col not in df.columns:
                continue

            indices = self.rng.choice(n_rows, size=n_corrupt, replace=False)
            for idx in indices:
                val = df.iloc[idx][col]
                if val is None or pd.isna(val):
                    continue

                # Convert to date if needed
                if isinstance(val, str):
                    try:
                        val = pd.to_datetime(val).date()
                    except (ValueError, TypeError):
                        continue

                if isinstance(val, date):
                    fmt = self.rng.choice(alt_formats)
                    corrupted = val.strftime(fmt)
                    df.at[df.index[idx], col] = corrupted

                    record_id = (
                        str(df.iloc[idx][id_column])
                        if id_column in df.columns
                        else None
                    )
                    self.issues.append(
                        QualityIssue(
                            table_name=table_name,
                            column_name=col,
                            record_id=record_id,
                            issue_type="inconsistent_date_format",
                            description=f"Date reformatted to '{fmt}' → '{corrupted}'",
                        )
                    )

        return df

    # ------------------------------------------------------------------
    # Categorical casing corruption
    # ------------------------------------------------------------------
    def _corrupt_categoricals(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        columns: list[str],
    ) -> pd.DataFrame:
        """
        Apply random casing transformations to categorical values.

        e.g., 'Male' → 'male', 'MALE', 'M', 'male '
        """
        n_rows = len(df)
        n_corrupt = max(1, int(n_rows * self.config.inconsistent_case_rate))
        transforms = [
            lambda s: s.lower(),
            lambda s: s.upper(),
            lambda s: s[0] if len(s) > 0 else s,  # Abbreviate to first letter
            lambda s: s.lower() + " ",  # Trailing whitespace
            lambda s: " " + s,  # Leading whitespace
            lambda s: s.title(),  # Already title-case (no-op for many)
        ]

        for col in columns:
            if col not in df.columns:
                continue

            indices = self.rng.choice(n_rows, size=n_corrupt, replace=False)
            for idx in indices:
                val = df.iloc[idx][col]
                if val is None or pd.isna(val):
                    continue

                transform = self.rng.choice(transforms)
                original = str(val)
                corrupted = transform(original)
                df.at[df.index[idx], col] = corrupted

                record_id = (
                    str(df.iloc[idx][id_column]) if id_column in df.columns else None
                )
                self.issues.append(
                    QualityIssue(
                        table_name=table_name,
                        column_name=col,
                        record_id=record_id,
                        issue_type="inconsistent_casing",
                        description=f"'{original}' → '{corrupted}'",
                    )
                )

        return df

    # ------------------------------------------------------------------
    # Name transliteration fuzzing
    # ------------------------------------------------------------------
    _TRANSLITERATION_MAP: dict[str, list[str]] = {
        "sh": ["s", "shh"],
        "th": ["t", "dh"],
        "aa": ["a"],
        "ee": ["i", "e"],
        "oo": ["u"],
        "Kumar": ["Kumaar", "Kumer"],
        "Singh": ["Sing", "Sigh"],
        "Sharma": ["Sharme", "Sharmaa"],
        "Devi": ["Devee", "Davi"],
        "Patel": ["Patell", "Ptael"],
        "Gupta": ["Gupte", "Gupt"],
    }

    def _fuzz_names(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        columns: list[str],
    ) -> pd.DataFrame:
        """
        Simulate transliteration variants of Indian names.

        This mirrors the real problem where Hindi/regional names are
        romanised differently by different field workers.
        """
        n_rows = len(df)
        n_corrupt = max(1, int(n_rows * self.config.encoding_fuzz_rate))

        for col in columns:
            if col not in df.columns:
                continue

            indices = self.rng.choice(n_rows, size=n_corrupt, replace=False)
            for idx in indices:
                val = df.iloc[idx][col]
                if val is None or pd.isna(val):
                    continue

                original = str(val)
                corrupted = original
                for pattern, replacements in self._TRANSLITERATION_MAP.items():
                    if pattern in corrupted:
                        replacement = self.rng.choice(replacements)
                        corrupted = corrupted.replace(pattern, replacement, 1)
                        break  # One substitution per name

                if corrupted != original:
                    df.at[df.index[idx], col] = corrupted
                    record_id = (
                        str(df.iloc[idx][id_column])
                        if id_column in df.columns
                        else None
                    )
                    self.issues.append(
                        QualityIssue(
                            table_name=table_name,
                            column_name=col,
                            record_id=record_id,
                            issue_type="transliteration_variant",
                            description=f"Name fuzzed: '{original}' → '{corrupted}'",
                        )
                    )

        return df

    # ------------------------------------------------------------------
    # Outlier injection
    # ------------------------------------------------------------------
    def _add_outliers(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
        columns: list[str],
    ) -> pd.DataFrame:
        """
        Inject unrealistic outlier values into numeric columns.

        e.g., age = 999, attendance = -5, score = 9999
        """
        n_rows = len(df)
        n_corrupt = max(1, int(n_rows * self.config.outlier_rate))
        outlier_values = [999, -1, -5, 0, 99999, 9999]

        for col in columns:
            if col not in df.columns:
                continue

            indices = self.rng.choice(n_rows, size=n_corrupt, replace=False)
            for idx in indices:
                outlier = self.rng.choice(outlier_values)
                original = df.iloc[idx][col]
                df.at[df.index[idx], col] = outlier

                record_id = (
                    str(df.iloc[idx][id_column]) if id_column in df.columns else None
                )
                self.issues.append(
                    QualityIssue(
                        table_name=table_name,
                        column_name=col,
                        record_id=record_id,
                        issue_type="outlier",
                        description=f"Outlier injected: {original} → {outlier}",
                    )
                )

        return df

    # ------------------------------------------------------------------
    # Duplicate injection
    # ------------------------------------------------------------------
    def _add_duplicates(
        self,
        df: pd.DataFrame,
        table_name: str,
        id_column: str,
    ) -> pd.DataFrame:
        """
        Append near-duplicate rows with slight modifications.

        Simulates the common NGO problem of a beneficiary being
        re-registered at a different program site with minor
        differences in their recorded details.
        """
        n_rows = len(df)
        n_dupes = max(1, int(n_rows * self.config.duplicate_rate))
        indices = self.rng.choice(n_rows, size=n_dupes, replace=False)

        duplicates: list[dict[str, Any]] = []
        for idx in indices:
            row = df.iloc[idx].to_dict()
            original_id = row[id_column]

            # Modify the ID to create a "new" record
            row[id_column] = f"{original_id}-DUP"

            # Slight modification to one field to make it a near-duplicate
            str_cols = [
                c
                for c in df.columns
                if c != id_column
                and df[c].dtype == "object"
                and row.get(c) is not None
                and not pd.isna(row.get(c, None))
            ]
            if str_cols:
                mod_col = self.rng.choice(str_cols)
                val = str(row[mod_col])
                # Introduce a typo: swap two adjacent characters
                if len(val) > 3:
                    pos = int(self.rng.integers(1, len(val) - 1))
                    val_list = list(val)
                    val_list[pos], val_list[pos - 1] = val_list[pos - 1], val_list[pos]
                    row[mod_col] = "".join(val_list)

            duplicates.append(row)
            self.issues.append(
                QualityIssue(
                    table_name=table_name,
                    column_name=None,
                    record_id=original_id,
                    issue_type="duplicate_entry",
                    description=f"Near-duplicate created as '{row[id_column]}'",
                )
            )

        if duplicates:
            dupe_df = pd.DataFrame(duplicates)
            df = pd.concat([df, dupe_df], ignore_index=True)

        logger.debug("Added %d duplicate rows to '%s'", len(duplicates), table_name)
        return df

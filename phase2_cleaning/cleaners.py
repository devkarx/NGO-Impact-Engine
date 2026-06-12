"""
Domain-specific data cleaners for NGO M&E datasets.

Architecture:
    Each cleaner is a pure function that takes a DataFrame + config
    and returns a cleaned DataFrame + a cleaning report.  This makes
    them individually testable, composable, and auditable.

    The cleaners are ordered by the standard cleaning waterfall:
        1. Deduplication  (remove noise before other transforms)
        2. Date parsing   (normalise to ISO 8601)
        3. Categoricals   (canonical casing / values)
        4. Outliers       (clamp or nullify impossible values)
        5. Imputation     (fill remaining NULLs per strategy)
        6. Type casting   (ensure correct dtypes for BI ingestion)

    Each step logs what it changed so the pipeline produces a full
    audit trail — critical for M&E data governance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from phase2_cleaning.config import CleaningConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cleaning report structure
# ---------------------------------------------------------------------------
@dataclass
class CleaningReport:
    """
    Structured audit trail for a single cleaning operation.

    Attributes:
        table_name: Name of the table that was cleaned.
        step: Name of the cleaning step (e.g., 'deduplication').
        rows_before: Row count before this step.
        rows_after: Row count after this step.
        rows_affected: Number of rows modified or removed.
        details: Per-column or per-issue detail log.
    """

    table_name: str
    step: str
    rows_before: int
    rows_after: int
    rows_affected: int
    details: list[str] = field(default_factory=list)


# =========================================================================
# 1. DEDUPLICATION
# =========================================================================
def deduplicate(
    df: pd.DataFrame,
    table_name: str,
    id_column: str,
    config: CleaningConfig,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Remove duplicate and near-duplicate rows.

    Strategy (two-pass):
        1. **Exact ID match**: Remove rows where the ID contains '-DUP'
           (these are synthetic near-duplicates injected by the noise
           generator).
        2. **Fuzzy match**: For tables with defined match columns, flag
           remaining rows that match on all specified demographic fields.
           Keep the first occurrence, drop subsequent.

    This ordering ensures we remove the obvious fakes first, then catch
    any organic duplicates that slipped through.

    Args:
        df: Input DataFrame with potential duplicates.
        table_name: Name of the table for logging.
        id_column: Primary key column name.
        config: Cleaning configuration.

    Returns:
        Tuple of (deduplicated DataFrame, CleaningReport).
    """
    rows_before = len(df)
    details: list[str] = []

    # Pass 1: Remove synthetic '-DUP' records
    dup_mask = df[id_column].astype(str).str.contains("-DUP", na=False)
    n_synthetic = int(dup_mask.sum())
    if n_synthetic > 0:
        df = df[~dup_mask].copy()
        details.append(
            f"Removed {n_synthetic} synthetic duplicates (ID contains '-DUP')"
        )
        logger.info("[%s] Removed %d synthetic duplicates", table_name, n_synthetic)

    # Pass 2: Fuzzy deduplication on match columns
    match_cols = config.deduplication.match_columns.get(table_name, [])
    valid_cols = [c for c in match_cols if c in df.columns]

    if valid_cols:
        before_fuzzy = len(df)
        # Normalise match columns for comparison (lowercase, strip)
        temp_cols = {}
        for col in valid_cols:
            temp_name = f"_match_{col}"
            temp_cols[temp_name] = col
            df[temp_name] = df[col].astype(str).str.lower().str.strip()

        df = df.drop_duplicates(subset=list(temp_cols.keys()), keep="first")
        df = df.drop(columns=list(temp_cols.keys()))

        n_fuzzy = before_fuzzy - len(df)
        if n_fuzzy > 0:
            details.append(
                f"Removed {n_fuzzy} fuzzy duplicates on columns: {valid_cols}"
            )
            logger.info("[%s] Removed %d fuzzy duplicates", table_name, n_fuzzy)

    rows_after = len(df)
    report = CleaningReport(
        table_name=table_name,
        step="deduplication",
        rows_before=rows_before,
        rows_after=rows_after,
        rows_affected=rows_before - rows_after,
        details=details,
    )
    return df.reset_index(drop=True), report


# =========================================================================
# 2. DATE NORMALISATION
# =========================================================================
def normalise_dates(
    df: pd.DataFrame,
    table_name: str,
    config: CleaningConfig,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Parse all date columns into a consistent ISO 8601 format (YYYY-MM-DD).

    Handles the mix of formats injected by the noise generator:
        - DD/MM/YYYY (Indian convention)
        - DD-Mon-YY  (abbreviated month)
        - MM-DD-YYYY (US format — ambiguous)
        - DD.MM.YYYY (European)
        - YYYY/MM/DD (ISO-ish)

    Strategy:
        We use ``pd.to_datetime`` with ``dayfirst=True`` and
        ``format='mixed'`` (pandas 3.x).  The ``dayfirst`` flag is
        critical for Indian data — 05/06/2023 should be 5 June, not
        6 May.  Unparseable values are coerced to NaT.

    Args:
        df: Input DataFrame with mixed-format date columns.
        table_name: Table name for config lookup.
        config: Cleaning configuration.

    Returns:
        Tuple of (date-normalised DataFrame, CleaningReport).
    """
    date_cols = config.dates.date_columns.get(table_name, [])
    valid_cols = [c for c in date_cols if c in df.columns]
    rows_before = len(df)
    details: list[str] = []

    for col in valid_cols:
        n_non_null_before = df[col].notna().sum()

        # Attempt parsing with dayfirst=True
        parsed = pd.to_datetime(
            df[col],
            dayfirst=config.dates.dayfirst,
            errors="coerce",
            format="mixed",
        )

        n_coerced = int(n_non_null_before - parsed.notna().sum())
        if n_coerced > 0:
            details.append(
                f"Column '{col}': {n_coerced} unparseable dates coerced to NaT"
            )
            logger.warning(
                "[%s] %d unparseable dates in '%s' coerced to NaT",
                table_name,
                n_coerced,
                col,
            )

        # Convert to date strings in target format (no time component)
        df[col] = parsed.dt.strftime(config.dates.target_format)
        # Replace 'NaT' strings back to actual None
        df[col] = df[col].replace("NaT", None)

        n_normalised = int(n_non_null_before - n_coerced)
        details.append(f"Column '{col}': {n_normalised} dates normalised to ISO 8601")

    report = CleaningReport(
        table_name=table_name,
        step="date_normalisation",
        rows_before=rows_before,
        rows_after=len(df),
        rows_affected=len(valid_cols),  # columns affected, not rows
        details=details,
    )
    return df, report


# =========================================================================
# 3. CATEGORICAL STANDARDISATION
# =========================================================================
def standardise_categoricals(
    df: pd.DataFrame,
    table_name: str,
    config: CleaningConfig,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Map dirty categorical values to their canonical forms.

    Handles:
        - Casing inconsistencies ('male' → 'Male')
        - Abbreviations ('M' → 'Male', 'F' → 'Female')
        - Leading/trailing whitespace
        - Unknown values → mapped or left as-is with a warning

    Strategy:
        1. Strip and lowercase the value.
        2. Look up in the canonical map.
        3. If found → replace. If not → log a warning and keep original.

    Args:
        df: Input DataFrame with inconsistent categoricals.
        table_name: Table name for context.
        config: Cleaning configuration.

    Returns:
        Tuple of (standardised DataFrame, CleaningReport).
    """
    details: list[str] = []

    # Define which columns use which map
    column_map_registry: dict[str, dict[str, str]] = {
        "gender": config.categoricals.gender_map,
        "status": (
            config.categoricals.service_status_map
            if table_name == "service_delivery"
            else config.categoricals.outcome_status_map
        ),
        "assessment_type": config.categoricals.assessment_type_map,
    }

    total_fixed = 0
    for col, canonical_map in column_map_registry.items():
        if col not in df.columns:
            continue

        # Vectorized approach: build a lookup key, map in one pass
        non_null_mask = df[col].notna()
        if not non_null_mask.any():
            continue

        original = df.loc[non_null_mask, col].astype(str)
        lookup_keys = original.str.strip().str.lower()
        mapped = lookup_keys.map(canonical_map)

        # Identify values that mapped successfully and actually changed
        changed_mask = mapped.notna() & (mapped != original)
        n_fixed = int(changed_mask.sum())

        if n_fixed > 0:
            df.loc[changed_mask[changed_mask].index, col] = mapped[changed_mask]
            details.append(f"Column '{col}': {n_fixed} values standardised")
            total_fixed += n_fixed

        # Identify unmapped values (not in map keys AND not already canonical)
        canonical_values = set(canonical_map.values())
        unmapped_mask = mapped.isna()
        unmapped_raw = original[unmapped_mask].str.strip()
        unmapped_values = set(v for v in unmapped_raw if v not in canonical_values)

        if unmapped_values:
            details.append(
                f"Column '{col}': {len(unmapped_values)} unmapped values: "
                f"{sorted(unmapped_values)[:5]}"
            )
            logger.warning(
                "[%s] Unmapped values in '%s': %s",
                table_name,
                col,
                sorted(unmapped_values)[:5],
            )

    report = CleaningReport(
        table_name=table_name,
        step="categorical_standardisation",
        rows_before=len(df),
        rows_after=len(df),
        rows_affected=total_fixed,
        details=details,
    )
    return df, report


# =========================================================================
# 4. OUTLIER TREATMENT
# =========================================================================
def treat_outliers(
    df: pd.DataFrame,
    table_name: str,
    config: CleaningConfig,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Clamp or nullify numeric values outside domain-valid ranges.

    Strategy:
        - Values outside the valid range are set to NaN (not clamped),
          because fabricating a "reasonable" value is worse than marking
          it as missing in an M&E context.  The downstream imputation
          step will handle NaNs according to its strategy.

    Domain bounds come from ``OutlierConfig`` and are justified by
    real-world constraints (e.g., age cannot be 999 or negative).

    Args:
        df: Input DataFrame with potential outliers.
        table_name: Table name for logging.
        config: Cleaning configuration.

    Returns:
        Tuple of (outlier-treated DataFrame, CleaningReport).
    """
    bounds: dict[str, tuple[float, float]] = {
        "age": (config.outliers.age_min, config.outliers.age_max),
        "household_size": (
            config.outliers.household_min,
            config.outliers.household_max,
        ),
        "score": (config.outliers.score_min, float("inf")),  # max bounded by max_score
        "dosage": (config.outliers.dosage_min, config.outliers.dosage_max),
        "planned_attendance": (
            config.outliers.attendance_min,
            config.outliers.attendance_max,
        ),
        "actual_attendance": (
            config.outliers.attendance_min,
            config.outliers.attendance_max,
        ),
        "amount_inr": (config.outliers.amount_min, config.outliers.amount_max),
    }

    details: list[str] = []
    total_nullified = 0

    for col, (lo, hi) in bounds.items():
        if col not in df.columns:
            continue

        # Coerce to numeric first (some values may be strings after noise)
        numeric_col = pd.to_numeric(df[col], errors="coerce")
        outlier_mask = (numeric_col < lo) | (numeric_col > hi)

        # Special case: score should not exceed max_score
        if col == "score" and "max_score" in df.columns:
            max_scores = pd.to_numeric(df["max_score"], errors="coerce")
            outlier_mask = outlier_mask | (numeric_col > max_scores)

        n_outliers = int(outlier_mask.sum())
        if n_outliers > 0:
            df.loc[outlier_mask, col] = np.nan
            details.append(
                f"Column '{col}': {n_outliers} outliers nullified "
                f"(valid range: [{lo}, {hi}])"
            )
            total_nullified += n_outliers
            logger.info(
                "[%s] Nullified %d outliers in '%s' (range [%s, %s])",
                table_name,
                n_outliers,
                col,
                lo,
                hi,
            )

    report = CleaningReport(
        table_name=table_name,
        step="outlier_treatment",
        rows_before=len(df),
        rows_after=len(df),
        rows_affected=total_nullified,
        details=details,
    )
    return df, report


# =========================================================================
# 5. IMPUTATION
# =========================================================================
def impute_missing(
    df: pd.DataFrame,
    table_name: str,
    config: CleaningConfig,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Fill remaining NaN/None values using the configured strategy per column.

    Strategies:
        - ``median``:  For numeric columns. Robust to the outliers we
          just nullified.  Preferred over mean in skewed distributions
          (income, household size).
        - ``mode``:    Most frequent value.  Used sparingly — only for
          columns where imputing the mode is defensible.
        - ``unknown``: Explicit sentinel string 'Unknown'. Preferred for
          demographic fields (gender, education) to avoid introducing
          bias.  BI tools can filter on 'Unknown' for data quality KPIs.
        - ``zero``:    For flag/counter columns (is_disabled, dosage).
        - ``skip``:    Leave as NULL.  Used for truly optional fields
          (phone, notes, remarks) or fields where imputation would be
          intellectually dishonest (test scores).

    Args:
        df: Input DataFrame with NaN values.
        table_name: Table name for strategy lookup.
        config: Cleaning configuration.

    Returns:
        Tuple of (imputed DataFrame, CleaningReport).
    """
    strategies = config.imputation.strategies.get(table_name, {})
    details: list[str] = []
    total_filled = 0

    for col, strategy in strategies.items():
        if col not in df.columns:
            continue

        n_null = int(df[col].isna().sum())
        if n_null == 0:
            continue

        if strategy == "median":
            numeric_col = pd.to_numeric(df[col], errors="coerce")
            fill_value = numeric_col.median()
            if pd.notna(fill_value):
                df[col] = numeric_col.fillna(fill_value)
                # Round if the column looks like an integer
                if df[col].dropna().apply(float.is_integer).all():
                    df[col] = df[col].round(0).astype("Int64")
                details.append(
                    f"Column '{col}': {n_null} NULLs filled with median ({fill_value:.1f})"
                )
                total_filled += n_null

        elif strategy == "mode":
            mode_val = df[col].mode()
            if not mode_val.empty:
                df[col] = df[col].fillna(mode_val.iloc[0])
                details.append(
                    f"Column '{col}': {n_null} NULLs filled with mode ('{mode_val.iloc[0]}')"
                )
                total_filled += n_null

        elif strategy == "unknown":
            df[col] = df[col].fillna("Unknown")
            details.append(f"Column '{col}': {n_null} NULLs filled with 'Unknown'")
            total_filled += n_null

        elif strategy == "zero":
            df[col] = df[col].fillna(0)
            details.append(f"Column '{col}': {n_null} NULLs filled with 0")
            total_filled += n_null

        elif strategy == "skip":
            details.append(
                f"Column '{col}': {n_null} NULLs intentionally preserved (skip)"
            )

        else:
            logger.warning(
                "[%s] Unknown imputation strategy '%s' for column '%s'",
                table_name,
                strategy,
                col,
            )

    report = CleaningReport(
        table_name=table_name,
        step="imputation",
        rows_before=len(df),
        rows_after=len(df),
        rows_affected=total_filled,
        details=details,
    )
    return df, report


# =========================================================================
# 6. TYPE CASTING
# =========================================================================
def cast_types(
    df: pd.DataFrame,
    table_name: str,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Enforce correct dtypes for BI tool ingestion.

    BI tools (Metabase, Power BI, Tableau) are sensitive to column types.
    This step ensures:
        - Integer columns use pandas nullable Int64 (handles NaN gracefully)
        - Float columns use float64
        - Date columns remain as strings in ISO format (for CSV portability)
        - String columns are stripped of whitespace

    Args:
        df: Input DataFrame post-imputation.
        table_name: Table name for logging.

    Returns:
        Tuple of (type-cast DataFrame, CleaningReport).
    """
    details: list[str] = []

    # Columns that should be integers
    int_columns = {
        "age",
        "household_size",
        "is_disabled",
        "is_active",
        "planned_attendance",
        "actual_attendance",
        "dosage",
        "target_beneficiaries",
        "receipt_available",
        "resolved",
    }

    # Columns that should be floats
    float_columns = {
        "score",
        "max_score",
        "target_value",
        "actual_value",
        "amount_inr",
        "latitude",
        "longitude",
    }

    for col in df.columns:
        if col in int_columns:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                details.append(f"Column '{col}': cast to Int64")
            except (ValueError, TypeError):
                logger.warning("[%s] Could not cast '%s' to Int64", table_name, col)

        elif col in float_columns:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
                details.append(f"Column '{col}': cast to float64")
            except (ValueError, TypeError):
                logger.warning("[%s] Could not cast '%s' to float64", table_name, col)

        elif df[col].dtype == "object":
            # Vectorized whitespace strip (avoids row-level lambda)
            df[col] = df[col].str.strip()

    report = CleaningReport(
        table_name=table_name,
        step="type_casting",
        rows_before=len(df),
        rows_after=len(df),
        rows_affected=len(details),
        details=details,
    )
    return df, report


# =========================================================================
# 7. REFERENTIAL INTEGRITY CHECK
# =========================================================================
def check_referential_integrity(
    df: pd.DataFrame,
    table_name: str,
    fk_column: str,
    parent_df: pd.DataFrame,
    parent_id_column: str,
) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Validate and repair broken foreign key references.

    Strategy:
        Rows referencing non-existent parent IDs are set to NULL in the
        FK column (not dropped), because losing the row entirely would
        discard valuable data.  The BI layer can filter on NULL FKs to
        surface "unlinked" records as a data quality KPI.

    Args:
        df: Child table DataFrame.
        table_name: Child table name.
        fk_column: Foreign key column in the child table.
        parent_df: Parent table DataFrame.
        parent_id_column: Primary key column in the parent table.

    Returns:
        Tuple of (integrity-checked DataFrame, CleaningReport).
    """
    if fk_column not in df.columns:
        return df, CleaningReport(
            table_name=table_name,
            step="referential_integrity",
            rows_before=len(df),
            rows_after=len(df),
            rows_affected=0,
            details=[f"Column '{fk_column}' not found, skipping"],
        )

    valid_ids = set(parent_df[parent_id_column].dropna().astype(str))
    orphan_mask = ~df[fk_column].astype(str).isin(valid_ids) & df[fk_column].notna()
    n_orphans = int(orphan_mask.sum())

    details: list[str] = []
    if n_orphans > 0:
        df.loc[orphan_mask, fk_column] = None
        details.append(f"Column '{fk_column}': {n_orphans} orphan references nullified")
        logger.warning(
            "[%s] Nullified %d orphan FKs in '%s'",
            table_name,
            n_orphans,
            fk_column,
        )

    report = CleaningReport(
        table_name=table_name,
        step="referential_integrity",
        rows_before=len(df),
        rows_after=len(df),
        rows_affected=n_orphans,
        details=details,
    )
    return df, report

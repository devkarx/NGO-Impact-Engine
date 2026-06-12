"""
Abstract base class for all synthetic data generators.

Provides shared utilities: ID generation, date randomisation,
weighted random selection, and consistent seeding.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Any, Sequence

import numpy as np
import pandas as pd
from faker import Faker

from phase1_data_architecture.config import RANDOM_SEED

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """
    Abstract base for all table generators.

    Subclasses must implement ``_generate_rows`` which returns a list of
    row dicts.  The public ``generate()`` method wraps this in error
    handling, logging, and DataFrame construction.

    Attributes:
        fake: Seeded Faker instance configured for ``en_IN`` locale.
        rng:  Seeded NumPy random generator for reproducible sampling.
    """

    def __init__(self, seed: int = RANDOM_SEED) -> None:
        self.fake = Faker("en_IN")
        Faker.seed(seed)
        self.rng = np.random.default_rng(seed)
        self._seed = seed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self) -> pd.DataFrame:
        """
        Generate the synthetic DataFrame for this table.

        Returns:
            pd.DataFrame with the generated rows.

        Raises:
            RuntimeError: If row generation fails unexpectedly.
        """
        table_name = self.__class__.__name__.replace("Generator", "").lower()
        logger.info("Generating table: %s", table_name)

        try:
            rows = self._generate_rows()
            df = pd.DataFrame(rows)
            logger.info(
                "Generated %d rows for '%s' (%d columns)",
                len(df),
                table_name,
                len(df.columns),
            )
            return df
        except Exception as exc:
            logger.exception("Failed to generate '%s'", table_name)
            raise RuntimeError(f"Generation failed for '{table_name}'") from exc

    @abstractmethod
    def _generate_rows(self) -> list[dict[str, Any]]:
        """Return a list of row dictionaries. Must be implemented by subclasses."""
        ...

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------
    @staticmethod
    def make_id(prefix: str, index: int, width: int = 3) -> str:
        """
        Create a padded ID string.

        Examples:
            >>> BaseGenerator.make_id("DON", 1)
            'DON-001'
            >>> BaseGenerator.make_id("BEN", 42, width=5)
            'BEN-00042'
        """
        return f"{prefix}-{str(index).zfill(width)}"

    def random_date(
        self, start: date, end: date, allow_none: bool = False, none_prob: float = 0.05
    ) -> date | None:
        """
        Generate a random date between ``start`` and ``end`` (inclusive).

        Args:
            start: Earliest possible date.
            end: Latest possible date.
            allow_none: If True, may return None with probability ``none_prob``.
            none_prob: Probability of returning None when ``allow_none`` is True.

        Returns:
            A random date, or None.
        """
        if allow_none and self.rng.random() < none_prob:
            return None
        delta_days = (end - start).days
        if delta_days <= 0:
            return start
        random_days = int(self.rng.integers(0, delta_days + 1))
        return start + timedelta(days=random_days)

    def weighted_choice(
        self,
        options: Sequence[str],
        weights: Sequence[float] | None = None,
    ) -> str:
        """
        Pick one item from ``options`` using optional probability weights.

        Args:
            options: Sequence of choices.
            weights: Optional probability weights (must sum to ~1.0).

        Returns:
            A single selected item.
        """
        if weights is not None:
            # Normalise to handle floating-point drift
            w = np.array(weights, dtype=np.float64)
            w /= w.sum()
            idx = self.rng.choice(len(options), p=w)
        else:
            idx = self.rng.choice(len(options))
        return options[idx]

    def maybe_null(self, value: Any, null_prob: float = 0.10) -> Any | None:
        """Return ``value`` or ``None`` with probability ``null_prob``."""
        if self.rng.random() < null_prob:
            return None
        return value

    def indian_phone(self) -> str:
        """Generate a realistic Indian mobile number."""
        prefix = self.rng.choice([6, 7, 8, 9])
        suffix = "".join(str(self.rng.integers(0, 10)) for _ in range(9))
        return f"+91-{prefix}{suffix}"

    def fiscal_year_label(self, dt: date) -> str:
        """
        Derive the Indian fiscal year label from a date.

        Examples:
            date(2023, 5, 15) → 'FY2023-24'
            date(2024, 2, 1)  → 'FY2023-24'
        """
        if dt.month >= 4:
            return f"FY{dt.year}-{str(dt.year + 1)[-2:]}"
        return f"FY{dt.year - 1}-{str(dt.year)[-2:]}"

"""Generic ComparisonResult dataclass with precision/recall/F1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass
class ComparisonResult(Generic[T, U]):
    """Result of comparing extracted vs target items with precision/recall/F1."""

    matched_pairs: list[tuple[T, U]]
    unmatched_target: list[T]
    unmatched_extracted: list[U]

    @property
    def num_target(self) -> int:
        return len(self.matched_pairs) + len(self.unmatched_target)

    @property
    def num_extracted(self) -> int:
        return len(self.matched_pairs) + len(self.unmatched_extracted)

    @property
    def precision(self) -> float:
        if self.num_extracted == 0:
            return 0.0
        return len(self.matched_pairs) / self.num_extracted

    @property
    def recall(self) -> float:
        if self.num_target == 0:
            return 0.0
        return len(self.matched_pairs) / self.num_target

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

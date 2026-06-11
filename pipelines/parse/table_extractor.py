"""Table extraction strategy helpers for Week07.

This lightweight module encodes the deck's three table strategies. It does not
run heavyweight table models by default; it gives downstream code a stable
decision object.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableStrategy:
    strategy: str
    reason: str
    storage_hint: str

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "reason": self.reason,
            "storage_hint": self.storage_hint,
        }


def choose_table_strategy(row_count: int, *, has_business_keys: bool = False) -> TableStrategy:
    if row_count < 20:
        return TableStrategy("markdown_chunk", "small_table", "store table markdown with chunk")
    if row_count <= 200 and not has_business_keys:
        return TableStrategy(
            "description_plus_markdown",
            "medium_table",
            "store LLM/table summary plus markdown evidence",
        )
    return TableStrategy("sql_table", "large_or_queryable_table", "materialize into relational table")

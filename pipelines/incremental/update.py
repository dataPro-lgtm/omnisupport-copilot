"""Incremental update planning for Week07 parse outputs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IncrementalDecision:
    action: str
    reason: str


def decide_incremental_update(previous_fingerprint: str | None, current_fingerprint: str) -> IncrementalDecision:
    if not previous_fingerprint:
        return IncrementalDecision(action="insert", reason="first_seen_source")
    if previous_fingerprint == current_fingerprint:
        return IncrementalDecision(action="skip", reason="source_fingerprint_unchanged")
    return IncrementalDecision(action="reparse", reason="source_fingerprint_changed")

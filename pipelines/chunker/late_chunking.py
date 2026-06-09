"""Late chunking planning stub for Week07.

Late chunking embeds a larger context window and pools token spans back into
chunks. The course runtime records the plan and keeps heavyweight model calls
outside the default Docker/Podman path.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LateChunkingPlan:
    encoder_name: str
    context_window: int
    chunk_count: int
    enabled: bool
    reason: str


def plan_late_chunking(
    chunk_count: int,
    *,
    encoder_name: str = "jinaai/jina-embeddings-v3",
    context_window: int = 8192,
    model_available: bool = False,
) -> LateChunkingPlan:
    if not model_available:
        return LateChunkingPlan(
            encoder_name=encoder_name,
            context_window=context_window,
            chunk_count=chunk_count,
            enabled=False,
            reason="optional_embedding_model_not_loaded",
        )
    return LateChunkingPlan(
        encoder_name=encoder_name,
        context_window=context_window,
        chunk_count=chunk_count,
        enabled=True,
        reason="late_chunking_ready",
    )

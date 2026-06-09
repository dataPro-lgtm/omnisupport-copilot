"""Optional CLIP-style embedding adapter."""

from dataclasses import dataclass
import importlib.util


@dataclass(frozen=True)
class ClipEmbeddingPlan:
    model_name: str
    available: bool
    reason: str


def clip_embedding_plan(model_name: str = "openai/clip-vit-base-patch32") -> ClipEmbeddingPlan:
    available = importlib.util.find_spec("sentence_transformers") is not None
    return ClipEmbeddingPlan(
        model_name=model_name,
        available=available,
        reason="ready" if available else "optional_sentence_transformers_not_installed",
    )

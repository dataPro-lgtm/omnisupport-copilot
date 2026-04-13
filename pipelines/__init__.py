"""Dagster module root.

Expose ``defs`` lazily so ``dagster dev -m pipelines`` can discover the
repository, while regular Python entrypoints such as
``python -m pipelines.ingestion.seed_loader`` do not require Dagster to be
installed locally.
"""

__all__ = ["defs"]


def __getattr__(name: str):
    if name == "defs":
        from .definitions import defs

        return defs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

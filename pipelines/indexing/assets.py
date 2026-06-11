"""Dagster assets for Week8 indexing.

The assets wrap the existing index builder; they do not introduce a parallel
embedding or retrieval system.
"""

import asyncio
import os

from dagster import asset

from pipelines.indexing.embedder import build_index


@asset(group_name="week08_indexing")
def week8_index_manifest(context) -> dict:
    index_release_id = os.environ.get("WEEK08_INDEX_RELEASE_ID", "index-week08-dev")
    data_release_id = os.environ.get("WEEK08_DATA_RELEASE_ID", "data-week08-dev")
    chunk_strategy_version = os.environ.get("WEEK08_CHUNK_STRATEGY_VERSION", "section_aware_v1")
    manifest = {
        "index_release_id": index_release_id,
        "data_release_id": data_release_id,
        "chunk_strategy_version": chunk_strategy_version,
        "source_table": "knowledge_section",
    }
    context.add_output_metadata(manifest)
    return manifest


@asset(group_name="week08_indexing", deps=[week8_index_manifest])
def build_knowledge_index(context) -> dict:
    stats = asyncio.run(
        build_index(
            index_release_id=os.environ.get("WEEK08_INDEX_RELEASE_ID", "index-week08-dev"),
            data_release_id=os.environ.get("WEEK08_DATA_RELEASE_ID", "data-week08-dev"),
            chunk_strategy_version=os.environ.get(
                "WEEK08_CHUNK_STRATEGY_VERSION", "section_aware_v1"
            ),
            batch_size=int(os.environ.get("WEEK08_INDEX_BATCH_SIZE", "32")),
            dry_run=os.environ.get("WEEK08_INDEX_DRY_RUN", "true").lower() == "true",
            report_dir=os.environ.get("WEEK08_REPORT_DIR", "reports/week08"),
        )
    )
    metadata = {
        "total_chunks": stats.total_chunks,
        "embedded": stats.embedded,
        "skipped": stats.skipped,
        "errors": stats.errors,
        "elapsed_sec": stats.elapsed_sec,
    }
    context.add_output_metadata(metadata)
    return metadata

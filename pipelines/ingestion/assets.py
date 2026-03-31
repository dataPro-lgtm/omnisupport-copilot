"""Dagster 资产定义 — 数据采集层

Week01 骨架：定义资产图，建立从 seed manifest 到 raw zone 的链路。
Week03 起接入真实采集器，打通 MinIO 落盘与 PostgreSQL 元数据写入。
"""

from dagster import (
    asset,
    AssetExecutionContext,
    MetadataValue,
    Output,
    define_asset_job,
    AssetSelection,
)
from dagster import EnvVar
import json
import os
from pathlib import Path


# ── 常量 ─────────────────────────────────────────────────────────────────────
MANIFEST_DIR = Path(os.getenv("SEED_MANIFEST_PATH", "/manifests"))
INGEST_BATCH_ID = os.getenv("INGEST_BATCH_ID", "batch-dev-001")


# ── Layer 1 → Layer 2: Seed Manifest → Raw Zone ──────────────────────────────

@asset(
    group_name="ingestion",
    description="从 seed manifest 目录加载所有清单文件，校验 schema，输出有效清单列表",
    tags={"layer": "landing", "modality": "all"},
)
def seed_manifests(context: AssetExecutionContext) -> Output[list[dict]]:
    """
    加载并校验所有 seed manifest 文件。

    Week01: 读取 data/seed_manifests/*.json，做基础 schema 检查。
    Week03: 增加 jsonschema 完整校验 + pii_scan 触发。
    """
    manifests = []
    manifest_path = MANIFEST_DIR

    if not manifest_path.exists():
        context.log.warning(f"Manifest directory not found: {manifest_path}")
        return Output([], metadata={"manifest_count": MetadataValue.int(0)})

    for f in manifest_path.glob("*.json"):
        if f.name.startswith("source_manifest"):  # schema 文件跳过
            continue
        try:
            data = json.loads(f.read_text())
            manifests.append(data)
            context.log.info(f"Loaded manifest: {f.name} ({data.get('modality')})")
        except Exception as e:
            context.log.error(f"Failed to load {f.name}: {e}")

    return Output(
        manifests,
        metadata={
            "manifest_count": MetadataValue.int(len(manifests)),
            "manifest_ids": MetadataValue.json([m.get("manifest_id") for m in manifests]),
        },
    )


@asset(
    group_name="ingestion",
    deps=["seed_manifests"],
    description="将 document 类型 manifest 中的资产元数据写入 raw_doc_asset 表（Bronze 层）",
    tags={"layer": "bronze", "modality": "document"},
)
def raw_doc_assets(
    context: AssetExecutionContext,
    seed_manifests: list[dict],
) -> Output[list[dict]]:
    """
    文档资产 Bronze 落盘。

    Week01: 过滤 document 类型清单，输出元数据列表（不实际写 DB）。
    Week03: 接入 PostgreSQL，写入 raw_doc_asset 表。
    Week04: 写入 Iceberg Bronze 表。
    """
    doc_manifests = [m for m in seed_manifests if m.get("modality") == "document"]
    all_assets = []

    for manifest in doc_manifests:
        for asset_item in manifest.get("assets", []):
            record = {
                "source_id": asset_item["source_id"],
                "asset_type": asset_item["asset_type"],
                "source_url_or_path": asset_item["source_url_or_path"],
                "manifest_id": manifest["manifest_id"],
                "ingest_batch_id": manifest["batch_id"],
                "license_tag": manifest["license_tag"],
                "product_line": manifest.get("product_line"),
                "canonization_status": manifest.get("canonization_status", "raw"),
                "schema_version": "raw_doc_asset_v1",
            }
            all_assets.append(record)

    context.log.info(f"Staged {len(all_assets)} document assets for Bronze layer")

    # TODO(Week03): 写入 PostgreSQL raw_doc_asset 表
    # TODO(Week04): 写入 Iceberg raw_doc_asset 表

    return Output(
        all_assets,
        metadata={
            "asset_count": MetadataValue.int(len(all_assets)),
            "batch_id": MetadataValue.text(INGEST_BATCH_ID),
        },
    )


@asset(
    group_name="ingestion",
    deps=["seed_manifests"],
    description="将 structured (ticket) 类型 manifest 写入 raw_ticket_event Bronze 层",
    tags={"layer": "bronze", "modality": "structured"},
)
def raw_ticket_events(
    context: AssetExecutionContext,
    seed_manifests: list[dict],
) -> Output[list[dict]]:
    """
    工单事件 Bronze 落盘。

    Week01: 过滤 structured 类型清单，输出元数据。
    Week03: 接入 PostgreSQL 写入 + ticket simulator 集成。
    """
    structured_manifests = [m for m in seed_manifests if m.get("modality") == "structured"]
    all_events = []

    for manifest in structured_manifests:
        for asset_item in manifest.get("assets", []):
            record = {
                "source_id": asset_item["source_id"],
                "asset_type": asset_item.get("asset_type", "jsonl"),
                "source_path": asset_item["source_url_or_path"],
                "manifest_id": manifest["manifest_id"],
                "ingest_batch_id": manifest["batch_id"],
                "license_tag": manifest["license_tag"],
                "schema_version": "raw_ticket_event_v1",
            }
            all_events.append(record)

    context.log.info(f"Staged {len(all_events)} ticket event sources for Bronze layer")

    # TODO(Week03): 写入 PostgreSQL raw_ticket_event 表

    return Output(
        all_events,
        metadata={"event_source_count": MetadataValue.int(len(all_events))},
    )


# ── Dagster Job 定义 ──────────────────────────────────────────────────────────

ingest_all_job = define_asset_job(
    name="ingest_all",
    selection=AssetSelection.groups("ingestion"),
    description="全量采集作业 — 从 seed manifest 到 Bronze 层落盘",
)

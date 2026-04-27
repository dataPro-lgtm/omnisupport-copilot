"""Dagster 资产定义 — Lakehouse 层 (Iceberg)

Week01 骨架：定义 Bronze→Silver→Gold 链路资产。
Week04 起接入 PyIceberg，真实建表，演示 snapshot/time travel/schema evolution。
"""

from dagster import AssetExecutionContext, MetadataValue, Output, asset


@asset(
    group_name="lakehouse_bronze",
    deps=["raw_doc_assets", "raw_ticket_events"],
    description="初始化 Iceberg Bronze 层表（Week04 接入真实 PyIceberg）",
    tags={"layer": "bronze", "technology": "iceberg"},
)
def iceberg_bronze_tables(context: AssetExecutionContext) -> Output[dict]:
    """
    Week01: 输出 Bronze 层表 schema 清单（占位）。
    Week04: 使用 PyIceberg 在 MinIO 上创建实际 Iceberg 表，
            演示 snapshot 隔离和 time travel 查询。
    """
    from pipelines.lakehouse.iceberg_schemas import BRONZE_SCHEMAS

    result = _try_ensure_week04_tables(("bronze.raw_ticket_event", "bronze.raw_doc_asset"))
    if result["status"] == "ok":
        context.log.info("Week04 Bronze Iceberg tables ensured through PyIceberg")
        return Output(
            result,
            metadata={
                "table_count": MetadataValue.int(len(result["tables"])),
                "stub": MetadataValue.bool(False),
            },
        )

    context.log.info(
        "Week04 Bronze Dagster wrapper skipped; use devbox CLI for the primary Week04 path"
    )

    return Output(
        {
            "tables": list(BRONZE_SCHEMAS.keys()),
            "status": "devbox_cli_primary_path",
            "reason": result["reason"],
        },
        metadata={
            "table_count": MetadataValue.int(len(BRONZE_SCHEMAS)),
            "stub": MetadataValue.bool(True),
        },
    )


@asset(
    group_name="lakehouse_silver",
    deps=["iceberg_bronze_tables", "ticket_facts", "knowledge_chunks"],
    description="初始化 Iceberg Silver 层表，建立规范化后的可查询实体",
    tags={"layer": "silver", "technology": "iceberg"},
)
def iceberg_silver_tables(context: AssetExecutionContext) -> Output[dict]:
    """
    Week01: schema 占位。
    Week04: 真实建表，写入 ticket_fact/knowledge_doc/knowledge_section/evidence_anchor。
    """
    from pipelines.lakehouse.iceberg_schemas import SILVER_SCHEMAS

    result = _try_ensure_week04_tables(("silver.ticket_fact", "silver.knowledge_doc"))
    if result["status"] == "ok":
        context.log.info("Week04 Silver Iceberg tables ensured through PyIceberg")
        return Output(
            result,
            metadata={"table_count": MetadataValue.int(len(result["tables"]))},
        )

    context.log.info(
        "Week04 Silver Dagster wrapper skipped; use devbox CLI for the primary Week04 path"
    )

    return Output(
        {
            "tables": list(SILVER_SCHEMAS.keys()),
            "status": "devbox_cli_primary_path",
            "reason": result["reason"],
        },
        metadata={"table_count": MetadataValue.int(len(SILVER_SCHEMAS))},
    )


@asset(
    group_name="lakehouse_gold",
    deps=["iceberg_silver_tables"],
    description="初始化 Iceberg Gold 层服务消费视图",
    tags={"layer": "gold", "technology": "iceberg"},
)
def iceberg_gold_views(context: AssetExecutionContext) -> Output[dict]:
    """
    Week01: schema 占位。
    Week05: 建立 support_kpi_mart，接入 KPI 查询工具。
    Week08: 建立 kb_serving_asset，供 RAG 检索消费。
    """
    from pipelines.lakehouse.iceberg_schemas import GOLD_SCHEMAS

    context.log.info(f"[Week01 stub] Would create {len(GOLD_SCHEMAS)} Gold views")

    return Output(
        {"views": list(GOLD_SCHEMAS.keys()), "status": "stub"},
        metadata={"view_count": MetadataValue.int(len(GOLD_SCHEMAS))},
    )


def _try_ensure_week04_tables(tables: tuple[str, ...]) -> dict:
    """Best-effort Dagster wrapper.

    The compose Dagster service uses the upstream Dagster image.  The official
    Week04 path is the devbox CLI where PyIceberg dependencies are installed.
    If a future Dagster image contains PyIceberg, this wrapper can ensure tables
    without duplicating business logic in Dagster assets.
    """

    try:
        from pipelines.lakehouse.catalog import ensure_core_tables

        ensured = ensure_core_tables(tables=tables)
        return {"status": "ok", "tables": ensured}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}

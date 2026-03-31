"""Dagster 资产定义 — Lakehouse 层 (Iceberg)

Week01 骨架：定义 Bronze→Silver→Gold 链路资产。
Week04 起接入 PyIceberg，真实建表，演示 snapshot/time travel/schema evolution。
"""

from dagster import asset, AssetExecutionContext, MetadataValue, Output


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

    context.log.info(f"[Week01 stub] Would create {len(BRONZE_SCHEMAS)} Bronze tables")
    # TODO(Week04): catalog = load_catalog("omni", **config)
    # TODO(Week04): for table_name, schema in BRONZE_SCHEMAS.items():
    #                   catalog.create_table_if_not_exists(...)

    return Output(
        {"tables": list(BRONZE_SCHEMAS.keys()), "status": "stub"},
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

    context.log.info(f"[Week01 stub] Would create {len(SILVER_SCHEMAS)} Silver tables")

    return Output(
        {"tables": list(SILVER_SCHEMAS.keys()), "status": "stub"},
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

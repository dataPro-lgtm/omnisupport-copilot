# Week04 Bronze/Silver Table Design v1

## Core Tables

| Layer | Table | Purpose |
|---|---|---|
| Bronze | `bronze.raw_ticket_event` | Preserve ticket event source payloads and ingest evidence. |
| Bronze | `bronze.raw_doc_asset` | Preserve document asset metadata and raw object references. |
| Silver | `silver.ticket_fact` | Current support-ticket business entity for Week05 semantic work. |
| Silver | `silver.knowledge_doc` | Current knowledge document entity for Week07-08 parsing and retrieval. |

## Design Rules

- Every table carries a time field.
- Every table carries batch or release trace fields where available.
- Bronze keeps source fidelity and uses deterministic dedupe/full refresh in Week04.
- Silver is rebuilt deterministically to avoid blind append of current-state rows.
- No Gold table is materialized in Week04.

## Snapshot Semantics

Each successful Iceberg write creates an inspectable table snapshot. Classroom demos should show:

```bash
python -m pipelines.lakehouse.inspect_metadata --table silver.ticket_fact --view snapshots
```

Run this through devbox in the course path.

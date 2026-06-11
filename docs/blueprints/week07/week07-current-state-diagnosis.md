# Week07 Current State Diagnosis

Week07 focuses on turning raw document assets into parse-normalized, evidence-anchored chunks that Week08 can index safely.

## Repository Check

- Active repository: `omnisupport-copilot`.
- Branch source: latest `origin/main`.
- Existing local transient outputs under `docs/blueprints/week03/` and `reports/week03/` are not part of Week07 scope.
- Current `origin/main` already contains Week08 indexing/RAG work, so Week07 must be implemented as an additive upstream layer and must not remove or rewrite Week08 contracts.

## Required Questions

1. Existing parse/normalize code is under `pipelines/parse_normalize/`, but it is mostly a Week01 stub plus an early `doc_parser.py`.
2. `pipelines/parse_normalize/assets.py` registers Dagster assets but currently returns empty outputs for document sections and chunks.
3. Existing document parse code combines parser, chunker, DB persistence, and CLI in one file, which is hard to validate contract-by-contract.
4. Existing `knowledge_doc`, `knowledge_section`, and `evidence_anchor` tables exist in `infra/migrations/001_init.sql`.
5. Week08 added index-oriented fields through `infra/migrations/003_week08_index_rag.sql`.
6. There are no Week07-specific JSON schemas for `knowledge_section`, `document_chunk`, `evidence_anchor`, `parse_run`, or `chunk_quality_sample`.
7. There are no Week07 fixtures or contract tests yet.
8. Existing seed manifests contain document assets, but the referenced S3 objects are course placeholders rather than local raw files.
9. Existing manifest checksums are declaration fields; local fallback parsing must not silently pretend those bytes were fetched from object storage.
10. Existing Week08 retrieval requires chunks with evidence metadata and must not rely on LLM-generated citations.
11. Existing Docker/Podman devbox path is the right validation path because the project already supports `docker compose --profile tools` and `podman compose`.
12. Week07 should not add heavy parser dependencies as a hard requirement; Docling/Unstructured can be optional with a deterministic fallback parser.
13. Week07 needs a CLI-first path, with Dagster assets as a thin wrapper rather than a second implementation.

## Safe To Change

- `contracts/data/*week07*.schema.json` and Week07 parse output schemas.
- Additive migrations under `infra/migrations/`.
- `pipelines/parse_normalize/` modules and tests.
- Week07 docs, runbooks, sample reports, and fixtures.
- Additive environment variables in `infra/docker-compose.yml` for Week07 runtime defaults.

## Should Not Touch

- Week01 startup path and root service topology.
- Week02 input-control contracts and seed loader behavior.
- Week03 ticket ingest semantics and local lab outputs.
- Week04 lakehouse materialization semantics.
- Week05 semantic/dbt metric path.
- Week06 data factory assets, checks, resources, and run evidence.
- Week08 retrieval/index contracts except for documenting the upstream handoff.

## Diagnosis

The main gap is not a missing parser library. The gap is a missing controlled handoff from document parsing to retrieval-ready evidence. Week07 must create explicit contracts and artifacts before runtime code so that Week08 can reject unanchored, low-quality, or fallback-only chunks.

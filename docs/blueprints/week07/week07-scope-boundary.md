# Week07 Scope Boundary

## Week07 Does

- Parse document-like assets from manifests or local files.
- Normalize parser output into section records with stable IDs.
- Chunk sections using `section_aware_v1`.
- Generate evidence anchors from source metadata, page/section provenance, parser capability, and source fingerprint.
- Run a quality gate for metadata completeness, anchor coverage, orphan chunks, empty chunks, PDF page/bbox rules, and fallback limitations.
- Emit artifacts and reports that Week08 can consume.
- Keep Docker and Podman devbox commands aligned.

## Week07 Does Not

- Build embeddings.
- Create pgvector ANN indexes.
- Implement RAG generation.
- Let LLMs generate citations.
- Add HITL workflows.
- Replace Week06 data factory orchestration.
- Rework Week08 retrieval contracts that already exist on `main`.

## Student Core

Students should be able to run a local dry-run using the devbox and inspect:

- `artifacts/week07/sections.json`
- `artifacts/week07/chunks.json`
- `artifacts/week07/evidence_anchors.json`
- `reports/week07/parse_run_report.json`
- `reports/week07/chunk_quality_report.md`
- `reports/week07/week8_ready_gate.json`

## Instructor Scale

Instructors can swap in real Docling/Unstructured dependencies and real raw files without changing the contracts. The fallback parser remains useful for deterministic classroom demos and for enterprise environments where native parser dependencies are not yet approved.

## Week08 Handoff Rules

- Week08 can consume only chunks with at least one evidence anchor.
- Week08 cannot index `allowed_for_indexing=false`.
- Week08 cannot invent citations during generation.
- Week08 must carry `source_fingerprint`, `doc_version`, `data_release_id`, `chunk_strategy_version`, and `parse_strategy_version`.
- Week08 must treat fallback parser output as lower-fidelity evidence.

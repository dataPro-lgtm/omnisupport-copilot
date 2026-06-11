# Week07 Data Model Notes

Week07 treats the existing `knowledge_section` table as the database representation of retrieval chunks because Week08 already reads from it. The new `document_chunk` contract describes the same logical object in artifact form and maps `chunk_id` to `knowledge_section.section_id`.

## Tables

- `knowledge_doc`: document-level metadata, source fingerprint, parser capability, parse run id, and release lineage.
- `knowledge_section`: retrieval chunk rows with chunk strategy, parse strategy, evidence ids, quality status, and indexing eligibility.
- `evidence_anchor`: citation source metadata. Week08 must build citations only from these rows or the matching `evidence_anchors.json` artifact.
- `document_parse_run`: run-level evidence for parse/normalize execution.
- `chunk_quality_sample`: sampled quality checks for classroom review and bad-case analysis.

## Week08 Compatibility

The migration is additive and preserves Week08 fields:

- `data_release_id`
- `index_release_id`
- `chunk_strategy_version`
- `indexed_at`
- `embedding`
- `embedding_model`

Week07 intentionally does not create embeddings or vector indexes. It only marks whether a chunk is `allowed_for_indexing`.

## Artifact Mapping

| Artifact | Database target |
|---|---|
| `sections.json` | `knowledge_doc` plus parser provenance |
| `chunks.json` | `knowledge_section` |
| `evidence_anchors.json` | `evidence_anchor` |
| `parse_run_report.json` | `document_parse_run` |
| `chunk_quality_samples.json` | `chunk_quality_sample` |

## Fallback Handling

If raw source files are unavailable and the CLI uses manifest metadata to create deterministic classroom fallback sections, the parser capability records `fallback_used=true`. Those outputs remain useful for teaching the control plane, but production ingestion should replace them with real raw files or object-store fetches.

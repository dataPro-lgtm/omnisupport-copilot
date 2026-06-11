# Week07 Chunk Quality Report

- Parse run: `parse-run-week07-sample`
- Data release: `week07-dev-local`
- Quality status: `warn`
- Week8 ready: `false`

## Metrics

- `section_count`: 4
- `chunk_count`: 4
- `anchor_count`: 4
- `metadata_completeness`: 1.0
- `anchor_coverage`: 1.0
- `empty_chunk_count`: 0
- `unanchored_chunk_count`: 0
- `orphan_chunk_count`: 0
- `orphan_anchor_count`: 0
- `pdf_missing_page_count`: 0
- `fallback_chunk_count`: 4
- `synthetic_source_chunk_count`: 4
- `pii_suspected_chunk_count`: 0
- `allowed_for_indexing_count`: 0

## Warnings

- `fallback_parser_used`
- `source_path_missing_synthetic_fallback`

## Errors

- None

## Week8 Handoff

- Week8 may index only chunks where `allowed_for_indexing=true`.
- Citations must be generated from `evidence_anchors.json` or `evidence_anchor` rows.
- Fallback parser output must not be treated as Docling-quality page/bbox evidence.

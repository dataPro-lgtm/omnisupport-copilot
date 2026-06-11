# Chunking Strategy v1

Strategy name: `section_aware_v1`.

## Rules

- Keep parser section boundaries as the first split.
- Split only within a section when content exceeds the configured chunk size.
- Prefer paragraph, sentence, list, table, transcript, and code boundaries before raw character windows.
- Preserve `section_id`, `section_path`, `section_type`, `source_fingerprint`, `doc_version`, `data_release_id`, and `parse_strategy_version`.
- Preserve `span_start`, `span_end`, `heading_path`, and `context_prefix` so evidence anchors can explain where a chunk came from.
- Generate stable `chunk_id` from `source_fingerprint + section_id + section_chunk_index + chunk_strategy_version`.
- Do not merge content across unrelated sections.

## PPT Alignment

The course deck introduces structure-aware chunking, late chunking, contextual retrieval, and code AST chunking. The default strategy remains `section_aware_v1`; optional helper modules live under:

- `pipelines/chunker/structure_aware.py`
- `pipelines/chunker/late_chunking.py`
- `pipelines/chunker/contextual.py`
- `pipelines/chunker/code_ast.py`

Late chunking and AST parsing are explicit extension points. They do not run heavyweight embedding or Tree-sitter dependencies in the default Docker/Podman classroom path.

## Defaults

- `chunk_size`: manifest `ingest_config.chunk_size` or `512`.
- `chunk_overlap`: manifest `ingest_config.chunk_overlap` or `64`.

## Week08 Contract

Week08 must include `chunk_strategy_version` in its index manifest. If the chunking strategy changes, Week08 should rebuild the index with a new `index_release_id`.

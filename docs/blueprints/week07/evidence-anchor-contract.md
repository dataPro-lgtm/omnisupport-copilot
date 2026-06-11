# Evidence Anchor Contract

Evidence anchors are the only valid citation source for Week08.

## Required Fields

- `anchor_id`
- `chunk_id`
- `section_id`
- `doc_id`
- `source_id`
- `source_fingerprint`
- `asset_type`
- `source_url_or_path`
- `section_path`
- `doc_version`
- `parser_backend`
- `parser_capability`
- `data_release_id`

## PDF Rule

PDF anchors require `page_no`. If `bbox` is missing, `bbox_missing_reason` must be present.

## Non-PDF Rule

HTML/API/release-note anchors can use section-level evidence. Page and bbox may be null, but the parser capability must make that explicit.

## No LLM Citations

The LLM may phrase an answer, but it must not invent citations. It can only cite evidence IDs produced by Week07 parsing or returned by Week08 retrieval.

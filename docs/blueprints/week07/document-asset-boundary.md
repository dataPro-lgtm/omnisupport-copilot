# Document Asset Boundary

## In Scope

- HTML help center pages.
- API reference pages.
- Release notes.
- FAQ/community-like text.
- PDF manuals through Docling when available or deterministic fallback when unavailable.

## Out Of Scope

- Audio ASR.
- Video frame/OCR pipelines.
- Embedding generation.
- RAG generation.
- Citation synthesis by LLM.

## Boundary Rule

A Week07 document asset is accepted only when it can produce:

- Stable `source_id`.
- Stable `source_fingerprint`.
- At least one `knowledge_section`.
- At least one `document_chunk`.
- At least one `evidence_anchor` per chunk.
- A parse run report and quality gate.

If the raw object is unavailable, the pipeline may produce a classroom fallback from manifest metadata. That output is explicitly marked with `source_path_missing_synthetic_fallback` and is not Week08-ready for production indexing.

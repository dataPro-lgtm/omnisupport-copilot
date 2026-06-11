# Week07 Schema Validation Summary

Validated schema set:

- `contracts/data/knowledge_section.schema.json`
- `contracts/data/document_chunk.schema.json`
- `contracts/data/evidence_anchor.schema.json`
- `contracts/data/parse_run.schema.json`
- `contracts/data/chunk_quality_sample.schema.json`

Validation command:

```bash
pytest tests/contract/test_week07_parse_contracts.py -v
```

Expected result: all Week07 schema fixtures validate, and invalid missing-anchor/PDF-missing-page fixtures are rejected.

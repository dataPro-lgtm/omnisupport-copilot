# Week07 Bad Case Review

| Case | Symptom | Expected Action |
|---|---|---|
| Missing raw object | `source_path_missing_synthetic_fallback` | Use for classroom dry-run only; provide real raw file before production indexing. |
| Missing anchor | `missing_evidence_anchor` | Fail quality gate; do not index. |
| PDF no page number | `pdf_missing_page_no` | Fix parser adapter or source extraction. |
| PDF no bbox reason | `pdf_missing_bbox_reason` | Preserve bbox or explain why missing. |
| PII suspected | `pii_suspected` | Review/redact before indexing. |

Review principle: retrieval quality starts before embedding. Bad evidence should be rejected before Week08 index build.

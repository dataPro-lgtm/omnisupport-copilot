-- Week07 PPT alignment fields.
-- Additive only: preserves Week01-Week06 tables and previous Week07 outputs.

ALTER TABLE knowledge_section
    ADD COLUMN IF NOT EXISTS span_start INT,
    ADD COLUMN IF NOT EXISTS span_end INT,
    ADD COLUMN IF NOT EXISTS heading_path JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS context_prefix TEXT;

ALTER TABLE evidence_anchor
    ADD COLUMN IF NOT EXISTS span_start INT,
    ADD COLUMN IF NOT EXISTS span_end INT,
    ADD COLUMN IF NOT EXISTS heading_path JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS retrieval_method TEXT,
    ADD COLUMN IF NOT EXISTS rerank_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_week07_anchor_doc_span
    ON evidence_anchor (doc_id, span_start, span_end);

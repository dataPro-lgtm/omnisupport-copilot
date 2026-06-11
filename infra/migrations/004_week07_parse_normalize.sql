-- Week07 parse/normalize support.
-- Additive only: this does not rename or drop Week01-Week08 tables.

ALTER TABLE knowledge_doc
    ADD COLUMN IF NOT EXISTS parse_strategy_version TEXT,
    ADD COLUMN IF NOT EXISTS parser_backend TEXT,
    ADD COLUMN IF NOT EXISTS parser_capability JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS source_url_or_path TEXT,
    ADD COLUMN IF NOT EXISTS parse_run_id TEXT,
    ADD COLUMN IF NOT EXISTS parsed_at TIMESTAMPTZ;

ALTER TABLE knowledge_section
    ADD COLUMN IF NOT EXISTS asset_type TEXT,
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS parse_strategy_version TEXT,
    ADD COLUMN IF NOT EXISTS parser_backend TEXT,
    ADD COLUMN IF NOT EXISTS parser_capability JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS bbox_missing_reason TEXT,
    ADD COLUMN IF NOT EXISTS evidence_anchor_ids TEXT[] DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS anchor_count INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS quality_status TEXT DEFAULT 'warn',
    ADD COLUMN IF NOT EXISTS allowed_for_indexing BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reason_codes TEXT[] DEFAULT ARRAY[]::TEXT[];

ALTER TABLE evidence_anchor
    ADD COLUMN IF NOT EXISTS section_id TEXT,
    ADD COLUMN IF NOT EXISTS doc_id TEXT,
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS asset_type TEXT,
    ADD COLUMN IF NOT EXISTS anchor_type TEXT DEFAULT 'section',
    ADD COLUMN IF NOT EXISTS source_url_or_path TEXT,
    ADD COLUMN IF NOT EXISTS bbox TEXT,
    ADD COLUMN IF NOT EXISTS bbox_missing_reason TEXT,
    ADD COLUMN IF NOT EXISTS parser_backend TEXT,
    ADD COLUMN IF NOT EXISTS parser_capability JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS data_release_id TEXT;

CREATE TABLE IF NOT EXISTS document_parse_run (
    parse_run_id           TEXT PRIMARY KEY,
    status                 TEXT NOT NULL,
    manifest_id            TEXT,
    batch_id               TEXT,
    parser                 TEXT NOT NULL,
    chunk_strategy_version TEXT NOT NULL,
    parse_strategy_version TEXT NOT NULL,
    data_release_id        TEXT NOT NULL,
    started_at             TIMESTAMPTZ NOT NULL,
    finished_at            TIMESTAMPTZ NOT NULL,
    source_count           INT DEFAULT 0,
    section_count          INT DEFAULT 0,
    chunk_count            INT DEFAULT 0,
    anchor_count           INT DEFAULT 0,
    quality_status         TEXT DEFAULT 'warn',
    week8_ready            BOOLEAN DEFAULT FALSE,
    warnings               JSONB DEFAULT '[]'::jsonb,
    errors                 JSONB DEFAULT '[]'::jsonb,
    artifacts              JSONB DEFAULT '{}'::jsonb,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunk_quality_sample (
    sample_id      TEXT PRIMARY KEY,
    chunk_id       TEXT,
    section_id     TEXT,
    status         TEXT NOT NULL,
    reason_codes   TEXT[] DEFAULT ARRAY[]::TEXT[],
    checks         JSONB DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_week07_ksection_fingerprint
    ON knowledge_section (source_fingerprint);

CREATE INDEX IF NOT EXISTS idx_week07_ksection_quality
    ON knowledge_section (quality_status, allowed_for_indexing);

CREATE INDEX IF NOT EXISTS idx_week07_anchor_source
    ON evidence_anchor (source_id, source_fingerprint);

CREATE INDEX IF NOT EXISTS idx_week07_parse_run_release
    ON document_parse_run (data_release_id, quality_status);

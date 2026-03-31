-- OmniSupport Copilot — PostgreSQL 初始化 DDL
-- 文件: 001_init.sql
-- 执行时机: docker-entrypoint-initdb.d (首次启动时自动执行)

-- ── 扩展 ──────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- BM25-like FTS 支持

-- ── Enum 类型 ─────────────────────────────────────────────────────────────────
CREATE TYPE ticket_status AS ENUM (
    'open', 'pending', 'in_progress', 'resolved', 'closed', 'escalated'
);

CREATE TYPE ticket_priority AS ENUM (
    'p1_critical', 'p2_high', 'p3_medium', 'p4_low'
);

CREATE TYPE product_line AS ENUM (
    'northstar_workspace', 'northstar_edge_gateway',
    'northstar_studio', 'cross_product'
);

CREATE TYPE sla_tier AS ENUM (
    'enterprise', 'professional', 'standard', 'free'
);

CREATE TYPE pii_level AS ENUM ('none', 'low', 'high');
CREATE TYPE quality_gate AS ENUM ('pass', 'warn', 'fail', 'pending');
CREATE TYPE asset_modality AS ENUM ('document', 'audio', 'video', 'structured');

-- ═════════════════════════════════════════════════════════════════════════════
-- BRONZE 层 (Raw Zone 元数据，真实文件在 MinIO)
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE raw_doc_asset (
    source_id           TEXT PRIMARY KEY,
    asset_type          TEXT NOT NULL,
    raw_object_path     TEXT,
    manifest_id         TEXT,
    ingest_batch_id     TEXT,
    license_tag         TEXT,
    product_line        product_line,
    doc_version         TEXT,
    page_count          INT,
    source_fingerprint  TEXT,
    source_url          TEXT,
    pii_level           pii_level DEFAULT 'none',
    quality_gate        quality_gate DEFAULT 'pending',
    schema_version      TEXT DEFAULT 'raw_doc_asset_v1',
    ingest_ts           TIMESTAMPTZ DEFAULT NOW(),
    tags                TEXT[]
);

CREATE INDEX idx_raw_doc_product_line ON raw_doc_asset (product_line);
CREATE INDEX idx_raw_doc_ingest_ts ON raw_doc_asset (ingest_ts);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE raw_ticket_event (
    event_id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    source_id           TEXT NOT NULL,
    manifest_id         TEXT,
    ingest_batch_id     TEXT,
    raw_payload         JSONB,
    schema_version      TEXT DEFAULT 'raw_ticket_event_v1',
    license_tag         TEXT,
    pii_level           pii_level DEFAULT 'low',
    source_fingerprint  TEXT,
    ingest_ts           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_raw_ticket_source ON raw_ticket_event (source_id);
CREATE INDEX idx_raw_ticket_batch ON raw_ticket_event (ingest_batch_id);

-- ═════════════════════════════════════════════════════════════════════════════
-- SILVER 层 — 结构化 (ticket / customer / entitlement)
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE customer_dim (
    customer_id     TEXT PRIMARY KEY,
    org_id          TEXT,
    org_name        TEXT,
    contact_email   TEXT,   -- PII，不入检索索引
    sla_tier        sla_tier DEFAULT 'standard',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE TABLE ticket_fact (
    ticket_id           TEXT PRIMARY KEY,
    customer_id         TEXT REFERENCES customer_dim(customer_id),
    org_id              TEXT,
    status              ticket_status DEFAULT 'open',
    priority            ticket_priority DEFAULT 'p3_medium',
    category            TEXT,
    product_line        product_line,
    product_version     TEXT,
    subject             TEXT,
    error_codes         TEXT[],
    asset_ids           TEXT[],
    assignee_id         TEXT,
    sla_tier            sla_tier,
    sla_due_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    pii_level           pii_level DEFAULT 'low',
    pii_redacted        BOOLEAN DEFAULT FALSE,
    data_release_id     TEXT,
    ingest_batch_id     TEXT,
    schema_version      TEXT DEFAULT 'ticket_v1'
);

CREATE INDEX idx_ticket_status ON ticket_fact (status);
CREATE INDEX idx_ticket_priority ON ticket_fact (priority);
CREATE INDEX idx_ticket_product_line ON ticket_fact (product_line);
CREATE INDEX idx_ticket_customer ON ticket_fact (customer_id);
CREATE INDEX idx_ticket_created_at ON ticket_fact (created_at DESC);

CREATE TABLE ticket_comment_fact (
    comment_id      TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    ticket_id       TEXT REFERENCES ticket_fact(ticket_id),
    author_id       TEXT,
    author_role     TEXT,
    body            TEXT,
    body_preview    TEXT GENERATED ALWAYS AS (LEFT(body, 200)) STORED,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comment_ticket ON ticket_comment_fact (ticket_id);

-- ═════════════════════════════════════════════════════════════════════════════
-- SILVER 层 — 知识资产 (文档 chunks + 向量索引)
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE knowledge_doc (
    doc_id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    source_id           TEXT REFERENCES raw_doc_asset(source_id),
    asset_type          TEXT,
    product_line        product_line,
    doc_version         TEXT,
    title               TEXT,
    language            TEXT DEFAULT 'en',
    page_count          INT,
    section_count       INT DEFAULT 0,
    chunk_count         INT DEFAULT 0,
    source_url          TEXT,
    source_fingerprint  TEXT,
    license_tag         TEXT,
    pii_level           pii_level DEFAULT 'none',
    quality_gate        quality_gate DEFAULT 'pending',
    data_release_id     TEXT,
    index_release_id    TEXT,
    indexed_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kdoc_product_line ON knowledge_doc (product_line);
CREATE INDEX idx_kdoc_index_release ON knowledge_doc (index_release_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Week08 核心：知识 chunk 表，带 pgvector 列

CREATE TABLE knowledge_section (
    section_id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    doc_id              TEXT REFERENCES knowledge_doc(doc_id),
    source_id           TEXT,
    section_path        TEXT,                   -- 如 '安装指南 > 步骤 > 接线'
    section_type        TEXT DEFAULT 'text',    -- text/table/image/list
    content             TEXT NOT NULL,
    page_no             INT,
    bbox                TEXT,                   -- JSON 坐标 [x0,y0,x1,y1]
    chunk_index         INT DEFAULT 0,
    -- 嵌入向量：Week08 开始填充（dim=1536 for claude/openai，可调）
    embedding           vector(1536),
    embedding_model     TEXT,
    data_release_id     TEXT,
    index_release_id    TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- FTS 索引（BM25-like lexical 检索）
CREATE INDEX idx_ksection_content_fts
    ON knowledge_section USING GIN (to_tsvector('english', content));

-- 向量相似度索引（Week08 建立后启用）
-- CREATE INDEX idx_ksection_embedding
--     ON knowledge_section USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

CREATE INDEX idx_ksection_doc ON knowledge_section (doc_id);
CREATE INDEX idx_ksection_product ON knowledge_section (doc_id, section_type);

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE evidence_anchor (
    anchor_id       TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    chunk_id        TEXT REFERENCES knowledge_section(section_id),
    source_id       TEXT,
    source_url      TEXT,
    page_no         INT,
    section_path    TEXT,
    doc_version     TEXT,
    modality        asset_modality DEFAULT 'document',
    start_ts        DOUBLE PRECISION,   -- 音视频起始秒
    end_ts          DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_anchor_chunk ON evidence_anchor (chunk_id);

-- ═════════════════════════════════════════════════════════════════════════════
-- 审计日志（Tool API 审计追踪）
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE audit_log (
    log_id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    request_id      TEXT NOT NULL,
    actor           TEXT,
    tool_name       TEXT NOT NULL,
    args_hash       TEXT,
    result_code     TEXT,
    hitl_triggered  BOOLEAN DEFAULT FALSE,
    reviewer        TEXT,
    release_id      TEXT,
    trace_id        TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_tool ON audit_log (tool_name);
CREATE INDEX idx_audit_created ON audit_log (created_at DESC);
CREATE INDEX idx_audit_actor ON audit_log (actor);

-- ═════════════════════════════════════════════════════════════════════════════
-- Source Manifest 元数据表
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE source_manifest (
    manifest_id         TEXT PRIMARY KEY,
    batch_id            TEXT,
    modality            asset_modality,
    source_type         TEXT,
    product_line        product_line,
    license_tag         TEXT,
    canonization_status TEXT DEFAULT 'raw',
    asset_count         INT DEFAULT 0,
    owner               TEXT,
    schema_version      TEXT DEFAULT 'source_manifest_v1',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    notes               TEXT
);

-- ═════════════════════════════════════════════════════════════════════════════
-- Release Manifest 版本追踪
-- ═════════════════════════════════════════════════════════════════════════════

CREATE TABLE release_manifest (
    release_id          TEXT PRIMARY KEY,
    env                 TEXT NOT NULL,
    data_release_id     TEXT NOT NULL,
    index_release_id    TEXT NOT NULL,
    prompt_release_id   TEXT NOT NULL,
    eval_run_id         TEXT,
    git_sha             CHAR(40),
    status              TEXT DEFAULT 'pending',
    previous_release_id TEXT,
    eval_summary        JSONB,
    rollout_notes       TEXT,
    rollback_reason     TEXT,
    services            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    created_by          TEXT,
    schema_version      TEXT DEFAULT 'release_manifest_v1'
);

-- 插入 Week01 初始化 release
INSERT INTO release_manifest (
    release_id, env, data_release_id, index_release_id,
    prompt_release_id, eval_run_id, git_sha, status,
    rollout_notes, created_by
) VALUES (
    'dev-20260331-001', 'dev', 'data-v0.0.1', 'index-v0.0.1',
    'prompt-v0.0.1', 'eval-run-20260331-001',
    '0000000000000000000000000000000000000000', 'active',
    'Phase 0 初始化 — 工程基线骨架', 'system/init'
);

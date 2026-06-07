-- Week07 real multimodal parse support.
-- Additive only: keeps Week01-Week06 tables and existing Week07 columns intact.

ALTER TYPE asset_modality ADD VALUE IF NOT EXISTS 'image';

ALTER TABLE evidence_anchor
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Week03 ticket ingest idempotency guard.
-- Additive/safe cleanup: keeps the newest duplicate raw event per source fingerprint.

DELETE FROM raw_ticket_event older
USING raw_ticket_event newer
WHERE older.source_id = newer.source_id
  AND older.source_fingerprint = newer.source_fingerprint
  AND older.source_fingerprint IS NOT NULL
  AND (
      older.ingest_ts < newer.ingest_ts
      OR (older.ingest_ts = newer.ingest_ts AND older.event_id < newer.event_id)
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_ticket_event_source_fingerprint
    ON raw_ticket_event (source_id, source_fingerprint);

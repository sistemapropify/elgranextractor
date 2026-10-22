-- Append-only review decisions for incremental catalog records. The source
-- version remains immutable; only this review projection changes.
CREATE TABLE catalog_review_status (
 target_table TEXT NOT NULL,
 target_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN
   ('candidate','observed','verified','rejected','superseded','expired')),
 revision INTEGER NOT NULL CHECK(revision>0),
 reviewed_at TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 evidence_json TEXT NOT NULL,
 source_version TEXT NOT NULL REFERENCES versions(id),
 PRIMARY KEY(target_table,target_id)
);
CREATE INDEX catalog_review_status_filter
 ON catalog_review_status(status,target_table,reviewed_at);
CREATE TABLE catalog_review_events (
 id TEXT PRIMARY KEY,
 target_table TEXT NOT NULL,
 target_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN
   ('candidate','observed','verified','rejected','superseded','expired')),
 previous_status TEXT,
 revision INTEGER NOT NULL CHECK(revision>0),
 reviewed_at TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 evidence_json TEXT NOT NULL,
 source_version TEXT NOT NULL REFERENCES versions(id)
);
CREATE INDEX catalog_review_target
 ON catalog_review_events(target_table,target_id,revision);
CREATE INDEX catalog_review_recent
 ON catalog_review_events(revision DESC);

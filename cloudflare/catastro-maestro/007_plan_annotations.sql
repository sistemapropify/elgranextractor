-- Administrative workspace metadata for source versions and locally inventoried
-- map documents. This does not alter immutable source payloads.
CREATE TABLE plan_workspace (
 document_key TEXT PRIMARY KEY,
 document_type TEXT NOT NULL CHECK(document_type IN ('source-version','dwg')),
 source_version TEXT REFERENCES versions(id),
 scope_ubigeo TEXT NOT NULL,
 display_title TEXT,
 updated_at TEXT NOT NULL,
 updated_by TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0)
);
CREATE INDEX plan_workspace_scope ON plan_workspace(scope_ubigeo,document_type);
CREATE TABLE plan_notes (
 id TEXT PRIMARY KEY,
 document_key TEXT NOT NULL,
 scope_ubigeo TEXT NOT NULL,
 note TEXT NOT NULL,
 created_at TEXT NOT NULL,
 actor TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0)
);
CREATE INDEX plan_notes_document ON plan_notes(document_key,created_at);
CREATE INDEX plan_notes_scope ON plan_notes(scope_ubigeo,created_at);

CREATE TABLE IF NOT EXISTS boundary_segments (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 side TEXT NOT NULL CHECK(side IN ('front','back','left','right','other','unknown')),
 length_m REAL CHECK(length_m>=0), geometry_json TEXT, source_version TEXT NOT NULL REFERENCES versions(id),
 evidence_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS boundary_entity ON boundary_segments(entity_id,side);
CREATE INDEX IF NOT EXISTS people_document_number ON people(document_number);

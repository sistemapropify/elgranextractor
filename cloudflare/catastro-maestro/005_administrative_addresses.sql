CREATE TABLE administrative_areas (
 id TEXT PRIMARY KEY, parent_id TEXT REFERENCES administrative_areas(id),
 kind TEXT NOT NULL, code TEXT, code_scheme TEXT, name TEXT NOT NULL,
 valid_from TEXT, valid_to TEXT, source_version TEXT REFERENCES versions(id),
 details_json TEXT NOT NULL
);
CREATE INDEX administrative_code ON administrative_areas(kind,code_scheme,code);
CREATE INDEX administrative_parent ON administrative_areas(parent_id,kind);
CREATE TABLE addresses (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 address_type TEXT NOT NULL, full_address TEXT, street_type TEXT, street_name TEXT,
 municipal_number TEXT, interior TEXT, postal_code TEXT, precision TEXT,
 status TEXT NOT NULL, source_version TEXT NOT NULL REFERENCES versions(id),
 evidence_json TEXT NOT NULL
);
CREATE INDEX addresses_entity ON addresses(entity_id,address_type);
CREATE INDEX addresses_street ON addresses(street_name,municipal_number);

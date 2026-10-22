-- Additive catalog for incremental ingestion. All rows remain linked to an
-- immutable source version; no observation becomes current by being inserted.
CREATE TABLE attribute_definitions (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, value_type TEXT NOT NULL
   CHECK(value_type IN ('text','number','boolean','date','json')),
 unit TEXT, scope TEXT NOT NULL, description TEXT,
 source_version TEXT REFERENCES versions(id)
);
CREATE TABLE property_observations (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 namespace TEXT NOT NULL, field_name TEXT NOT NULL, value_type TEXT NOT NULL,
 value_json TEXT NOT NULL, unit TEXT, method TEXT, status TEXT NOT NULL,
 observed_at TEXT, valid_from TEXT, valid_to TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), evidence_json TEXT NOT NULL
);
CREATE INDEX observations_entity ON property_observations(entity_id,namespace,field_name);
CREATE INDEX observations_target ON property_observations(source_version,target_ref);
CREATE TABLE external_identifiers (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 scheme TEXT NOT NULL, value TEXT NOT NULL, authority TEXT, scope TEXT,
 status TEXT NOT NULL, observed_at TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), evidence_json TEXT NOT NULL
);
CREATE INDEX identifiers_entity ON external_identifiers(entity_id,scheme);
CREATE INDEX identifiers_value ON external_identifiers(scheme,value);
CREATE TABLE listings (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 portal TEXT NOT NULL, external_id TEXT NOT NULL, url TEXT, operation TEXT,
 price REAL, currency TEXT, area_value REAL, area_unit TEXT, area_basis TEXT,
 status TEXT NOT NULL, first_seen TEXT, last_seen TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), details_json TEXT NOT NULL
);
CREATE INDEX listings_entity ON listings(entity_id);
CREATE INDEX listings_portal ON listings(portal,external_id);
CREATE INDEX listings_operation_price ON listings(operation,currency,price);
CREATE TABLE listing_observations (
 id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES listings(id),
 observed_at TEXT NOT NULL, price REAL, currency TEXT, operation TEXT,
 status TEXT NOT NULL, details_json TEXT NOT NULL,
 source_version TEXT NOT NULL REFERENCES versions(id)
);
CREATE INDEX listing_history ON listing_observations(listing_id,observed_at);
CREATE TABLE transactions (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 transaction_type TEXT NOT NULL, amount REAL, currency TEXT,
 transaction_date TEXT, recorded_date TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), evidence_json TEXT NOT NULL
);
CREATE INDEX transactions_entity ON transactions(entity_id,transaction_date);
CREATE TABLE organizations (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, organization_type TEXT NOT NULL,
 document_type TEXT, document_number TEXT, source_version TEXT NOT NULL REFERENCES versions(id),
 details_json TEXT NOT NULL
);
CREATE INDEX organizations_document ON organizations(document_type,document_number);
CREATE TABLE activities (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 organization_id TEXT REFERENCES organizations(id), category TEXT,
 subcategory TEXT, activity_name TEXT, ciiu_code TEXT, ciiu_version TEXT,
 valid_from TEXT, valid_to TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), evidence_json TEXT NOT NULL
);
CREATE INDEX activities_entity ON activities(entity_id);
CREATE INDEX activities_category ON activities(category,subcategory);
CREATE INDEX activities_ciiu ON activities(ciiu_version,ciiu_code);
CREATE TABLE visits (
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), target_ref TEXT,
 visited_at TEXT NOT NULL, observer TEXT, summary TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), details_json TEXT NOT NULL
);
CREATE INDEX visits_entity ON visits(entity_id,visited_at);
CREATE TABLE developments (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, developer_id TEXT REFERENCES organizations(id),
 status TEXT NOT NULL, expected_start TEXT, expected_end TEXT,
 source_version TEXT NOT NULL REFERENCES versions(id), details_json TEXT NOT NULL
);
CREATE TABLE development_lots (
 id TEXT PRIMARY KEY, development_id TEXT NOT NULL REFERENCES developments(id),
 entity_id TEXT REFERENCES entities(id), target_ref TEXT, role TEXT NOT NULL,
 source_version TEXT NOT NULL REFERENCES versions(id)
);
CREATE INDEX development_lots_entity ON development_lots(entity_id);
CREATE TABLE development_stages (
 id TEXT PRIMARY KEY, development_id TEXT NOT NULL REFERENCES developments(id),
 name TEXT NOT NULL, status TEXT NOT NULL, progress REAL,
 observed_at TEXT NOT NULL, source_version TEXT NOT NULL REFERENCES versions(id),
 details_json TEXT NOT NULL
);
CREATE INDEX development_stage_history ON development_stages(development_id,observed_at);
CREATE TABLE environment_features (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, ubigeo TEXT NOT NULL,
 geometry_json TEXT, source_version TEXT NOT NULL REFERENCES versions(id),
 evidence_json TEXT NOT NULL
);
CREATE INDEX environment_kind_district ON environment_features(kind,ubigeo);
CREATE TABLE coverage_records (
 id TEXT PRIMARY KEY, ubigeo TEXT NOT NULL, dataset TEXT NOT NULL,
 source_version TEXT REFERENCES versions(id), complete INTEGER NOT NULL CHECK(complete IN (0,1)),
 record_count INTEGER NOT NULL CHECK(record_count>=0), observed_at TEXT NOT NULL,
 details_json TEXT NOT NULL
);
CREATE INDEX coverage_district_dataset ON coverage_records(ubigeo,dataset,observed_at);

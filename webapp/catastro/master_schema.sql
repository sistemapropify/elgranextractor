-- Reference schema. Only initialized in RAM by this implementation.
-- No historical JSON is loaded and no production migration is executed.
PRAGMA foreign_keys=ON;
PRAGMA temp_store=MEMORY;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO meta VALUES ('revision','0');
CREATE TABLE projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, country_code TEXT NOT NULL,
 ubigeo TEXT NOT NULL, expected_sheets INTEGER CHECK(expected_sheets>0)
);
CREATE TABLE sources (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), name TEXT NOT NULL,
 ubigeo TEXT NOT NULL, sheet_code TEXT, role TEXT NOT NULL CHECK(role IN ('candidate','backup','contributing'))
);
CREATE TABLE versions (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), label TEXT NOT NULL,
 source_date TEXT, crs TEXT, georeferencing TEXT NOT NULL,
 original_name TEXT, original_sha256 TEXT, digest TEXT NOT NULL,
 created_at TEXT NOT NULL, created_by TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(source_id,label)
);
CREATE TABLE entities (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, country_code TEXT NOT NULL,
 ubigeo TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX entity_district_kind ON entities(ubigeo,kind);
CREATE TABLE boundary_segments (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 side TEXT NOT NULL CHECK(side IN ('front','back','left','right','other','unknown')),
 length_m REAL CHECK(length_m>=0), geometry_json TEXT, source_version TEXT NOT NULL REFERENCES versions(id),
 evidence_json TEXT NOT NULL
);
CREATE INDEX boundary_entity ON boundary_segments(entity_id,side);
CREATE TABLE contributions (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions(id),
 source_feature_id TEXT NOT NULL, layer TEXT NOT NULL, field TEXT NOT NULL,
 value_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
 UNIQUE(version_id,layer,source_feature_id,field)
);
CREATE TABLE identities (
 version_id TEXT NOT NULL REFERENCES versions(id), layer TEXT NOT NULL,
 source_feature_id TEXT NOT NULL, entity_id TEXT NOT NULL REFERENCES entities(id),
 PRIMARY KEY(version_id,layer,source_feature_id)
);
CREATE INDEX identity_entity ON identities(entity_id);
CREATE TABLE selections (
 entity_id TEXT NOT NULL REFERENCES entities(id), field TEXT NOT NULL,
 contribution_id TEXT NOT NULL REFERENCES contributions(id),
 PRIMARY KEY(entity_id,field)
);
CREATE INDEX selections_origin ON selections(contribution_id);
CREATE TABLE people (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, document_type TEXT,
 document_number TEXT, source_version TEXT REFERENCES versions(id)
);
CREATE INDEX people_document ON people(document_type,document_number);
CREATE INDEX people_document_number ON people(document_number);
CREATE TABLE relationships (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 related_entity_id TEXT REFERENCES entities(id), person_id TEXT REFERENCES people(id),
 kind TEXT NOT NULL, details_json TEXT NOT NULL, source_version TEXT REFERENCES versions(id)
);
CREATE INDEX relationship_entity ON relationships(entity_id);
CREATE INDEX relationship_related ON relationships(related_entity_id);
CREATE TABLE media (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 kind TEXT NOT NULL, object_key TEXT NOT NULL, sha256 TEXT, observed_at TEXT,
 source_version TEXT REFERENCES versions(id), details_json TEXT NOT NULL
);
CREATE INDEX media_entity ON media(entity_id);
CREATE TABLE registral_acts (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 kind TEXT NOT NULL, registry_office TEXT, registry_number TEXT, registry_seat TEXT,
 observed_at TEXT, source_version TEXT REFERENCES versions(id), details_json TEXT NOT NULL
);
CREATE INDEX acts_entity ON registral_acts(entity_id);
CREATE INDEX acts_entry ON registral_acts(registry_office,registry_number);
CREATE TABLE zones (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, revision INTEGER NOT NULL,
 geometry_json TEXT NOT NULL, rules_json TEXT NOT NULL, source_version TEXT REFERENCES versions(id)
);
CREATE TABLE current_attributes (
 entity_id TEXT PRIMARY KEY REFERENCES entities(id), country_code TEXT, ubigeo TEXT,
 postal_code TEXT, department TEXT, province TEXT, district TEXT, zone TEXT, sector TEXT,
 urbanization TEXT, block TEXT, lot TEXT, building TEXT, entrance TEXT, floor TEXT, unit TEXT,
 address TEXT, address_block TEXT, address_lot TEXT, street_type TEXT, street_name TEXT,
 municipal_number TEXT, condition TEXT, registry_office TEXT, registry_entry_type TEXT,
 notary_name TEXT, notary_kardex TEXT, deed_date TEXT, registry_folios TEXT, registry_seat TEXT,
 property_registration_date TEXT, construction_declaration TEXT,
 construction_registration_seat TEXT, construction_registration_date TEXT,
 cuc TEXT, cadastral_reference TEXT, cadastral_use TEXT, observed_use TEXT, zoning TEXT,
 use_category TEXT, business_category TEXT, business_subcategory TEXT, ciiu_code TEXT,
 ciiu_version TEXT, commercial_name TEXT, registry_entry_number TEXT,
 land_area REAL, built_area REAL, geometric_land_area REAL, gis_land_area REAL, gis_built_area REAL,
 front REAL, back REAL, left REAL, right REAL, perimeter REAL,
 bedrooms REAL, bathrooms REAL, half_bathrooms REAL, parking_spaces REAL, floors REAL, units REAL,
 is_corner INTEGER, is_through INTEGER, faces_park INTEGER
);
CREATE INDEX current_ubigeo ON current_attributes(ubigeo);
CREATE INDEX current_territory ON current_attributes(country_code,department,province,district);
CREATE INDEX current_postal ON current_attributes(country_code,postal_code);
CREATE INDEX current_sector_block_lot ON current_attributes(ubigeo,sector,block,lot);
CREATE INDEX current_urbanization ON current_attributes(ubigeo,urbanization);
CREATE INDEX current_cuc ON current_attributes(cuc);
CREATE INDEX current_registry ON current_attributes(registry_entry_number);
CREATE INDEX current_business ON current_attributes(ubigeo,business_category,business_subcategory);
CREATE INDEX current_ciiu ON current_attributes(ciiu_version,ciiu_code);
CREATE INDEX current_use ON current_attributes(ubigeo,use_category,cadastral_use);
CREATE INDEX current_land_area ON current_attributes(ubigeo,land_area);
CREATE TABLE attribute_definitions (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, value_type TEXT NOT NULL
   CHECK(value_type IN ('text','number','boolean','date','json')),
 unit TEXT, scope TEXT NOT NULL, description TEXT,
 source_version TEXT REFERENCES versions(id)
);
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
CREATE TABLE journal (
 revision INTEGER PRIMARY KEY, operation TEXT NOT NULL, actor TEXT NOT NULL,
 created_at TEXT NOT NULL, reason TEXT NOT NULL, details_json TEXT NOT NULL, snapshot_json TEXT NOT NULL
);
CREATE INDEX journal_scope ON journal(json_extract(details_json,'$.scope_ubigeo'),revision);

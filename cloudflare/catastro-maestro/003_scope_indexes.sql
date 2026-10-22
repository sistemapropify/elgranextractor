CREATE INDEX IF NOT EXISTS identity_entity ON identities(entity_id);
CREATE INDEX IF NOT EXISTS relationship_entity ON relationships(entity_id);
CREATE INDEX IF NOT EXISTS relationship_related ON relationships(related_entity_id);
CREATE INDEX IF NOT EXISTS media_entity ON media(entity_id);
CREATE INDEX IF NOT EXISTS acts_entity ON registral_acts(entity_id);
CREATE INDEX IF NOT EXISTS journal_scope ON journal(json_extract(details_json,'$.scope_ubigeo'),revision);

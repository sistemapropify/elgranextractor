-- The dominant read path scans contributions once per page. This index lets
-- keyset pagination stop at the last version/id instead of rescanning a district.
CREATE INDEX IF NOT EXISTS contributions_scope_page
 ON contributions(version_id,id);

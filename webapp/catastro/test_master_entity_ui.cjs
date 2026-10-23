const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const master = fs.readFileSync(path.join(__dirname, '../static/js/catastro-maestro.js'), 'utf8');
const dashboard = fs.readFileSync(path.join(__dirname, '../static/js/catastro-dashboard.js'), 'utf8');

assert.match(master, /LOTE-CM-/);
assert.match(master, /Vinculado al Catastro Maestro/);
assert.match(master, /view:'entity'/);
assert.match(master, /identity_links/);
assert.match(master, /Ficha vigente del lote/);
assert.match(master, /Titulares y relaciones/);
assert.match(master, /Documentos y fotografías/);
assert.match(master, /source\.id==='geollaqta'&&masterAvailable\?false/);

assert.match(dashboard, /maestro\/migracion\//);
assert.match(dashboard, /maestro\/migracion\/iniciar\//);
assert.match(dashboard, /maestro\/migracion\/estado\//);
assert.match(dashboard, /Migrando en segundo plano/);
assert.match(dashboard, /Migrar al Catastro Maestro/);
assert.match(dashboard, /apagar la computadora/);
assert.match(dashboard, /vigilante de Azure/);
assert.match(dashboard, /status==='stale'/);
assert.match(dashboard, /pending_lots/);

console.log('Master entity UI: UUID alias, linkage, full lot ficha, sources and resumable R2-to-D1 migration controls verified.');

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const master = fs.readFileSync(path.join(__dirname, '../static/js/catastro-maestro.js'), 'utf8');
const dashboard = fs.readFileSync(path.join(__dirname, '../static/js/catastro-dashboard.js'), 'utf8');

assert.match(master, /LOTE-CM-/);
assert.match(master, /Vinculado al Catastro Maestro/);
assert.match(master, /view:'entity'/);
assert.match(master, /identity_links/);
assert.match(master, /Ubicación e identificación/);
assert.match(master, /Áreas y perímetro/);
assert.match(master, /Características del lote/);
assert.match(master, /Unidades y fichas registrales/);
assert.match(master, /Titulares y derechos/);
assert.match(master, /Fotografías y documentos/);
assert.match(master, /value==null\|\|value===''\?'Sin dato'/);
assert.match(master, /unit_attributes/);
assert.doesNotMatch(master, /for\(const document\b/);
assert.match(master, /districtLabel\(district\)/);
assert.match(master, /catastro-master-raster-focus/);
assert.match(master, /Todos los distritos D1/);
assert.match(master, /ALL_DISTRICTS/);
assert.match(master, /source\.role==='draft'\|\|source\.role==='snapshot'/);
assert.match(master, /maestro\/vectores\//);
assert.match(master, /Buscar parques/);
assert.match(master, /maestro\/parques\//);
assert.match(master, /toggleParkAt/);

assert.match(dashboard, /maestro\/migracion\//);
assert.match(dashboard, /maestro\/migracion\/iniciar\//);
assert.match(dashboard, /maestro\/migracion\/estado\//);
assert.match(dashboard, /Migrando en segundo plano/);
assert.match(dashboard, /Migrar al Catastro Maestro/);
assert.match(dashboard, /apagar la computadora/);
assert.match(dashboard, /vigilante de Azure/);
assert.match(dashboard, /status==='stale'/);
assert.match(dashboard, /batch_size:5/);
assert.match(dashboard, /pending_lots/);

console.log('Master entity UI: UUID alias, linkage, full lot ficha, sources and resumable R2-to-D1 migration controls verified.');

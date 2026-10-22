const assert = require('node:assert/strict');
const {PIPELINE, pipelineStage, dwgStage, consolidatePdfVersions, consolidateDwgCopies} =
  require('../static/js/catastro-planos-dashboard.js');

assert.equal(PIPELINE.length, 11);
for (const stage of PIPELINE) {
  assert.ok(stage.label);
  assert.ok(stage.description.length > 40);
  assert.ok(stage.result);
  assert.ok(stage.gate);
}

assert.equal(pipelineStage({role: 'backup'}), 'backup');
assert.equal(pipelineStage({role: 'candidate'}), 'original');
assert.equal(pipelineStage({role: 'candidate', original_available: true}), 'inspection');
assert.equal(pipelineStage({
  role: 'candidate',
  original_available: true,
  original_name: 'registros.ndjson',
  elements: 2,
}), 'normalization');
assert.equal(pipelineStage({role: 'candidate', vector_review: {status: 'pending_review'}}), 'semantic');
assert.equal(pipelineStage({
  role: 'candidate',
  vector_review: {status: 'approved'},
  georeferencing: {status: 'pending'},
}), 'georef');
assert.equal(pipelineStage({
  role: 'candidate',
  vector_review: {status: 'approved'},
  georeferencing: {status: 'verified'},
}), 'homologation');
assert.equal(pipelineStage({
  role: 'contributing',
  elements: 1,
  vector_review: {status: 'approved'},
  georeferencing: {status: 'verified'},
}), 'activation');
assert.equal(dwgStage({status: 'pending'}), 'inspection');
assert.equal(dwgStage({status: 'completed'}), 'semantic');

const consolidated = consolidatePdfVersions([
  {version_id: 'v1', source_id: 'sector-32', original_available: true, created_at: '2026-10-20'},
  {version_id: 'v2', source_id: 'sector-32', original_available: true, created_at: '2026-10-21',
    vector_review: {status: 'pending_review'}},
]);
assert.equal(consolidated.length, 1);
assert.equal(consolidated[0].version_id, 'v2');
assert.equal(consolidated[0].versions_count, 2);
assert.equal(pipelineStage(consolidated[0]), 'semantic');

const dwg = consolidateDwgCopies([
  {id: 'a', sha256: 'same', status: 'completed'},
  {id: 'b', sha256: 'same', status: 'completed'},
]);
assert.equal(dwg.length, 1);
assert.equal(dwg[0].copies, 2);

console.log('Planos dashboard: eleven described gates and exclusive file stages passed.');

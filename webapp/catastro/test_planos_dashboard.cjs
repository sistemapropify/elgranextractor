const assert = require('node:assert/strict');
const {PIPELINE, pipelineStage, dwgStage} = require('../static/js/catastro-planos-dashboard.js');

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

console.log('Planos dashboard: eleven described gates and exclusive file stages passed.');

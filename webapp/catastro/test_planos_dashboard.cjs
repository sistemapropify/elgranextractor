const assert = require('node:assert/strict');
const {PIPELINE, pipelineStage, dwgStage} = require('../static/js/catastro-planos-dashboard.js');

assert.equal(PIPELINE.length, 6);
for (const stage of PIPELINE) {
  assert.ok(stage.label);
  assert.ok(stage.description.length > 40);
  assert.ok(stage.result);
  assert.ok(stage.gate);
}

assert.equal(pipelineStage({role: 'backup'}), 'backup');
assert.equal(pipelineStage({role: 'candidate'}), 'extract');
assert.equal(pipelineStage({role: 'candidate', vector_review: {status: 'pending_review'}}), 'review');
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
assert.equal(dwgStage({status: 'pending'}), 'extract');
assert.equal(dwgStage({status: 'completed'}), 'review');

console.log('Planos dashboard: six described gates and exclusive file stages passed.');

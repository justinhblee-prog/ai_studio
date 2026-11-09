import assert from 'node:assert/strict';
import { KeyedRequestGate } from '../src/keyedRequestGate.mjs';

const gate = new KeyedRequestGate();
const firstPreview = gate.next('asset-a:version-1');
const secondPreview = gate.next('asset-a:version-1');
assert.equal(gate.isCurrent('asset-a:version-1', firstPreview), false, 'newer preview request must supersede older request');
assert.equal(gate.isCurrent('asset-a:version-1', secondPreview), true, 'latest preview request must remain current');
const independentPreview = gate.next('asset-b:version-2');
assert.equal(gate.isCurrent('asset-a:version-1', secondPreview), true, 'independent preview key must not invalidate another key');
assert.equal(gate.isCurrent('asset-b:version-2', independentPreview), true, 'independent preview key must be current');
gate.invalidate('asset-a:version-1');
assert.equal(gate.isCurrent('asset-a:version-1', secondPreview), false, 'explicit invalidation must reject pending response');
assert.equal(gate.isCurrent('asset-b:version-2', independentPreview), true, 'single-key invalidation must preserve other requests');
const afterInvalidation = gate.next('asset-a:version-1');
gate.invalidateAll();
assert.equal(gate.isCurrent('asset-a:version-1', afterInvalidation), false, 'scope reset must invalidate every pending preview');
assert.equal(gate.isCurrent('asset-b:version-2', independentPreview), false, 'scope reset must invalidate independent preview too');
console.log('KeyedRequestGate behavior: 7 assertions passed');

import assert from 'node:assert/strict';
import { RequestScopeGate } from '../src/requestScopeGate.mjs';

const gate = new RequestScopeGate('["api-a","token-a","workspace-a"]');
const first = gate.capture();
assert.equal(gate.isCurrent(first), true, 'fresh token should be current');

gate.update('["api-a","token-a","workspace-b"]');
assert.equal(gate.isCurrent(first), false, 'workspace change must invalidate old token');
const second = gate.capture();
assert.equal(gate.isCurrent(second), true, 'new scope token should be current');

gate.update('["api-a","token-b","workspace-b"]');
assert.equal(gate.isCurrent(second), false, 'auth token change must invalidate old token');
const third = gate.capture();
gate.dispose();
assert.equal(gate.isCurrent(third), false, 'unmount must invalidate pending async work');

gate.activate();
const afterRemount = gate.capture();
assert.equal(gate.isCurrent(afterRemount), true, 'reactivation must allow fresh work');
assert.equal(gate.isCurrent(third), false, 'pre-dispose token must stay invalid after reactivation');

gate.update('["api-b","token-b","workspace-b"]');
assert.equal(gate.isCurrent(afterRemount), false, 'API origin change must invalidate old token');

console.log('RequestScopeGate behavior: 7 assertions passed');

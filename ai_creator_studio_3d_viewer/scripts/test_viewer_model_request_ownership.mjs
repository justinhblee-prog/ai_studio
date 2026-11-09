import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { KeyedRequestGate } from '../src/keyedRequestGate.mjs';
import { finalizeGltfLoad } from '../src/finalizeGltfLoad.mjs';
import { reportGltfParseError } from '../src/reportGltfParseError.mjs';

const gate = new KeyedRequestGate();
const first = gate.next('model');
const events = [];
const staleGltf = { scene: { name: 'stale' } };
const staleSuccess = finalizeGltfLoad({
  gltf: staleGltf,
  cancelled: !gate.isCurrent('model', first),
  commit: () => events.push('stale-commit'),
  rollback: (gltf) => events.push(`dispose:${gltf.scene.name}`),
});
assert.equal(staleSuccess.status, 'committed', 'request is initially current');
assert.deepEqual(events, ['stale-commit']);

const second = gate.next('model');
assert.equal(gate.isCurrent('model', first), false, 'new model supersedes prior request');
assert.equal(gate.isCurrent('model', second), true, 'newest model owns completion');
const lateGltf = { scene: { name: 'late-first' } };
const lateSuccess = finalizeGltfLoad({
  gltf: lateGltf,
  cancelled: !gate.isCurrent('model', first),
  commit: () => events.push('late-first-commit'),
  rollback: (gltf) => events.push(`dispose:${gltf.scene.name}`),
});
assert.equal(lateSuccess.status, 'cancelled', 'late parse success cannot commit');
assert.deepEqual(events, ['stale-commit', 'dispose:late-first']);

let staleErrorEvents = 0;
assert.equal(reportGltfParseError({
  cancelled: !gate.isCurrent('model', first),
  message: 'stale parse failure',
  setErrorMessage: () => { staleErrorEvents += 1; },
  setLoadState: () => { staleErrorEvents += 1; },
  notifyError: () => { staleErrorEvents += 1; },
}), false, 'late parse failure is ignored');
assert.equal(staleErrorEvents, 0, 'stale failure has no UI or consumer side effects');

const third = gate.next('model');
assert.equal(gate.isCurrent('model', second), false, 'rapid third replacement supersedes second');
assert.equal(gate.isCurrent('model', third), true);
const activeGltf = { scene: { name: 'active-third' } };
const activeSuccess = finalizeGltfLoad({
  gltf: activeGltf,
  cancelled: !gate.isCurrent('model', third),
  commit: () => events.push('active-third-commit'),
  rollback: () => events.push('active-third-dispose'),
});
assert.equal(activeSuccess.status, 'committed', 'latest parse may commit');
assert.equal(events.at(-1), 'active-third-commit');

gate.invalidate('model');
assert.equal(gate.isCurrent('model', third), false, 'unmount invalidation rejects outstanding callbacks');

const source = await readFile(new URL('../src/Studio3DViewer.tsx', import.meta.url), 'utf8');
assert.ok(source.includes("const requestId = modelRequestGateRef.current.next('model');"));
assert.ok(source.includes("const isCurrentRequest = () => modelRequestGateRef.current.isCurrent('model', requestId);"));
assert.ok(source.includes("cancelled: !isCurrentRequest(),"), 'parse success and error use the owner token');
assert.ok(source.includes("if (!isCurrentRequest()) return;"), 'fetch completion checks ownership');
assert.ok(source.includes("modelRequestGateRef.current.invalidate('model');"), 'effect cleanup invalidates owner synchronously');
console.log('Viewer model request ownership: 13 assertions passed');

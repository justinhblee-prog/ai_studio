import assert from 'node:assert/strict';
import { disposeGltfResources } from '../src/disposeGltfResources.mjs';
import { disposeViewerResources } from '../src/disposeViewerResources.mjs';
import { runViewerCleanupSteps } from '../src/runViewerCleanupSteps.mjs';

function resource(name, extra = {}) {
  return { name, disposeCount: 0, dispose() { this.disposeCount += 1; }, ...extra };
}
function node(name, props = {}) {
  return {
    name, children: [], parent: null, ...props,
    add(child) { child.parent?.remove(child); child.parent = this; this.children.push(child); },
    remove(child) { this.children = this.children.filter((item) => item !== child); child.parent = null; },
    traverse(callback) { callback(this); for (const child of [...this.children]) child.traverse(callback); },
  };
}
function makeModel(prefix) {
  const texture = resource(`${prefix}-texture`, { isTexture: true });
  const material = resource(`${prefix}-material`, { map: texture, uniforms: { nested: { value: [texture] } } });
  const geometry = resource(`${prefix}-geometry`);
  const skeleton = resource(`${prefix}-skeleton`);
  const root = node(`${prefix}-root`);
  root.add(node(`${prefix}-mesh-a`, { geometry, material, skeleton }));
  root.add(node(`${prefix}-mesh-b`, { geometry, material, skeleton }));
  return { scene: root, resources: { texture, material, geometry, skeleton } };
}

// Exercise the same scene/resource/cleanup boundaries as Studio3DViewer with a
// nested scene graph and shared GPU resources, without claiming real WebGL E2E.
const events = [];
const host = { canvasCount: 1, removeCanvas() { events.push('remove-canvas'); this.canvasCount = 0; } };
const renderer = { disposeCount: 0, dispose() { events.push('renderer-dispose'); this.disposeCount += 1; } };
const observer = { disconnectCount: 0, disconnect() { events.push('observer-disconnect'); this.disconnectCount += 1; } };
const controls = { disposeCount: 0, dispose() { events.push('controls-dispose'); this.disposeCount += 1; } };
const mixer = { stopped: 0, uncached: 0, stopAllAction() { events.push('mixer-stop'); this.stopped += 1; }, uncacheRoot() { events.push('mixer-uncache'); this.uncached += 1; } };
const model = makeModel('active-model');
const stage = makeModel('stage');
const sceneRoot = node('scene-root');
sceneRoot.add(model.scene);
sceneRoot.add(stage.scene);

const cleanup = runViewerCleanupSteps([
  { name: 'cancel-frame', run: () => events.push('cancel-frame') },
  { name: 'disconnect-observer', run: () => observer.disconnect() },
  { name: 'dispose-controls', run: () => controls.dispose() },
  { name: 'stop-mixer', run: () => mixer.stopAllAction() },
  { name: 'uncache-mixer', run: () => mixer.uncacheRoot(model.scene) },
  { name: 'dispose-model-resources', run: () => disposeViewerResources(model.scene) },
  { name: 'dispose-stage-resources', run: () => disposeViewerResources(stage.scene) },
  { name: 'renderer-dispose', run: () => renderer.dispose() },
  { name: 'canvas-remove', run: () => host.removeCanvas() },
]);
assert.equal(cleanup.attemptedCount, 9);
assert.equal(cleanup.completedCount, 9);
assert.deepEqual(cleanup.errors, []);
assert.equal(observer.disconnectCount, 1);
assert.equal(controls.disposeCount, 1);
assert.equal(mixer.stopped, 1);
assert.equal(mixer.uncached, 1);
assert.equal(renderer.disposeCount, 1);
assert.equal(host.canvasCount, 0);
for (const item of [...Object.values(model.resources), ...Object.values(stage.resources)]) {
  assert.equal(item.disposeCount, 1, `${item.name} released once`);
}
assert.ok(events.indexOf('mixer-stop') < events.indexOf('renderer-dispose'));
assert.ok(events.indexOf('renderer-dispose') < events.indexOf('remove-canvas'));

// Model replacement must detach the old root and release its resources before
// the next model is attached; shared nested resources are still disposed once.
const replacementParent = node('replacement-scene');
const oldModel = makeModel('old-model');
const newModel = makeModel('new-model');
replacementParent.add(oldModel.scene);
const replacement = runViewerCleanupSteps([
  { name: 'detach-old-root', run: () => replacementParent.remove(oldModel.scene) },
  { name: 'stop-old-mixer', run: () => events.push('old-mixer-stop') },
  { name: 'dispose-old-gltf', run: () => disposeViewerResources({ scene: oldModel.scene, scenes: [oldModel.scene] }) },
  { name: 'attach-new-root', run: () => replacementParent.add(newModel.scene) },
]);
assert.equal(replacement.completedCount, 4);
assert.equal(oldModel.scene.parent, null);
assert.equal(newModel.scene.parent, replacementParent);
for (const item of Object.values(oldModel.resources)) assert.equal(item.disposeCount, 1);
for (const item of Object.values(newModel.resources)) assert.equal(item.disposeCount, 0);

// A failing cleanup action is isolated; subsequent resource release still runs.
const failedResource = resource('injected-failure', { dispose() { this.disposeCount += 1; throw new Error('injected GPU release failure'); } });
const survivingResource = resource('surviving-resource');
const failureScene = node('failure-scene');
failureScene.add(node('failure-mesh', { geometry: failedResource, material: resource('failure-material') }));
const failureResult = runViewerCleanupSteps([
  { name: 'injected-failure', run: () => disposeViewerResources(failureScene) },
  { name: 'release-independent-resource', run: () => survivingResource.dispose() },
]);
assert.equal(failureResult.completedCount, 1, 'resource diagnostic is surfaced to lifecycle runner');
assert.equal(failureResult.errors.length, 1);
assert.equal(failureResult.errors[0].name, 'injected-failure');
assert.match(failureResult.errors[0].message, /injected GPU release failure/);
assert.equal(failedResource.disposeCount, 1);
assert.equal(survivingResource.disposeCount, 1);

console.log('Viewer lifecycle integration: 32 assertions passed');

import assert from 'node:assert/strict';
import { publishProjectLifecycleChange, subscribeProjectLifecycleChanges, PROJECT_LIFECYCLE_CHANGED } from '../src/projectLifecycleEvents.mjs';

class TestCustomEvent extends Event {
  constructor(type, options = {}) { super(type); this.detail = options.detail; }
}
const listeners = new Map();
globalThis.CustomEvent = TestCustomEvent;
globalThis.window = {
  addEventListener(type, handler) { const set = listeners.get(type) || new Set(); set.add(handler); listeners.set(type, set); },
  removeEventListener(type, handler) { listeners.get(type)?.delete(handler); },
  dispatchEvent(event) { for (const handler of listeners.get(event.type) || []) handler(event); return true; },
};

const received = [];
const unsubscribe = subscribeProjectLifecycleChanges((change) => received.push(change));
publishProjectLifecycleChange({ workspaceId: 'ws-a', projectId: 'project-1' });
assert.deepEqual(received, [{ workspaceId: 'ws-a', projectId: 'project-1' }], 'published lifecycle changes reach subscribers');
window.dispatchEvent(new TestCustomEvent(PROJECT_LIFECYCLE_CHANGED, { detail: { workspaceId: 'ws-b' } }));
assert.equal(received.length, 1, 'malformed lifecycle events are ignored');
unsubscribe();
publishProjectLifecycleChange({ workspaceId: 'ws-a', projectId: 'project-2' });
assert.equal(received.length, 1, 'unsubscribe prevents later notifications');
assert.equal(listeners.get(PROJECT_LIFECYCLE_CHANGED)?.size || 0, 0, 'listener cleanup removes the handler');
console.log('4 project lifecycle event assertions passed');

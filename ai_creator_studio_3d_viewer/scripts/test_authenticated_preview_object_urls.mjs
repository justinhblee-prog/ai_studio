import assert from 'node:assert/strict';
import { AuthenticatedPreviewObjectUrls } from '../src/authenticatedPreviewObjectUrls.mjs';

const created = [];
const revoked = [];
let sequence = 0;
const urlApi = {
  createObjectURL(blob) { const url = `blob:test-${++sequence}`; created.push([url, blob]); return url; },
  revokeObjectURL(url) { revoked.push(url); },
};
const registry = new AuthenticatedPreviewObjectUrls(urlApi);
const firstBlob = { id: 'first' };
const secondBlob = { id: 'second' };
assert.equal(registry.replace('asset:version', firstBlob), 'blob:test-1');
assert.equal(registry.replace('asset:version', secondBlob), 'blob:test-2');
assert.deepEqual(revoked, ['blob:test-1'], 'replacing a keyed preview revokes the old object URL');
registry.revoke('asset:version');
assert.deepEqual(revoked, ['blob:test-1', 'blob:test-2'], 'explicit invalidation revokes current object URL');
registry.replace('output-1', firstBlob);
registry.replace('output-2', secondBlob);
registry.clear();
assert.deepEqual(revoked, ['blob:test-1', 'blob:test-2', 'blob:test-3', 'blob:test-4'], 'clear revokes all remaining URLs');
assert.equal(registry.urls.size, 0);
console.log('Authenticated preview object URL tests: 5 assertions PASS');

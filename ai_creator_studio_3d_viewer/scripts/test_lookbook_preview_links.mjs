import assert from 'node:assert/strict';
import { getSignedDownloadExpiry, isSignedLinkUsable, isCurrentPreviewUrl } from '../src/lookbookPreviewLinks.mjs';

assert.equal(getSignedDownloadExpiry('/v1/lookbook-drafts/exports/lbx_1/download?expires=1794000000&signature=x'), 1794000000);
assert.equal(getSignedDownloadExpiry('https://example.test/download?signature=x'), null);
assert.equal(getSignedDownloadExpiry('/download?expires=abc'), null);
assert.equal(getSignedDownloadExpiry('/download?expires=1.5'), null);
assert.equal(getSignedDownloadExpiry('/download?expires=9007199254740992'), null);
assert.equal(isSignedLinkUsable(120, 119), true);
assert.equal(isSignedLinkUsable(120, 120), false);
assert.equal(isSignedLinkUsable(null, 100), false);
assert.equal(isSignedLinkUsable(Number.NaN, 100), false);
assert.equal(isCurrentPreviewUrl('https://cdn.test/new', 'https://cdn.test/old'), false);
assert.equal(isCurrentPreviewUrl('https://cdn.test/current', 'https://cdn.test/current'), true);
assert.equal(isCurrentPreviewUrl('', ''), false);
console.log('Lookbook signed-link and stale-preview tests: 12 assertions passed');

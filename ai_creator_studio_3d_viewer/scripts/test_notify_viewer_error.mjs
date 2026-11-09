import assert from 'node:assert/strict';
import { notifyViewerError } from '../src/notifyViewerError.mjs';

let received = '';
assert.equal(notifyViewerError((message) => { received = message; }, 'render failed'), true);
assert.equal(received, 'render failed');
assert.equal(notifyViewerError(undefined, 'ignored'), false);
assert.equal(notifyViewerError(null, 'ignored'), false);
assert.equal(notifyViewerError('not a callback', 'ignored'), false);
assert.equal(notifyViewerError(() => { throw new Error('consumer failure'); }, 'safe'), false);
assert.equal(notifyViewerError(() => { throw 'unusual failure'; }, 'safe'), false);
console.log('Viewer error notification: 7 assertions passed');

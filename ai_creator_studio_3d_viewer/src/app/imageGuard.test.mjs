import test from 'node:test';
import assert from 'node:assert/strict';
import { isProtectedTarget, blockIfProtected, installImageGuard, watermarkText, watermarkStyle } from './imageGuard.mjs';

const el = (matches) => ({ closest: (selector) => (matches && selector.includes(matches) ? {} : null) });
const event = (target) => ({ target, prevented: false, preventDefault() { this.prevented = true; } });

test('pictures are protected, text and forms are not', () => {
  assert.equal(isProtectedTarget(el('img')), true);
  assert.equal(isProtectedTarget(el('canvas')), true);
  assert.equal(isProtectedTarget(el('data-protect-image')), true);
  assert.equal(isProtectedTarget(el(null)), false);
  assert.equal(isProtectedTarget(null), false);
  assert.equal(isProtectedTarget({}), false);
});

test('right click and drag on a picture are cancelled; on anything else they are left alone', () => {
  const onImage = event(el('img')); const onText = event(el(null));
  assert.equal(blockIfProtected(onImage), true); assert.equal(onImage.prevented, true);
  assert.equal(blockIfProtected(onText), false); assert.equal(onText.prevented, false);
});

test('the guard listens for contextmenu and dragstart and removes both again', () => {
  const added = []; const removed = [];
  const doc = { addEventListener: (n, h) => added.push([n, h]), removeEventListener: (n, h) => removed.push([n, h]) };
  const uninstall = installImageGuard(doc);
  assert.deepEqual(added.map(([n]) => n).sort(), ['contextmenu', 'dragstart']);
  assert.ok(added.every(([, h]) => h === blockIfProtected));
  uninstall();
  assert.deepEqual(removed.map(([n]) => n).sort(), ['contextmenu', 'dragstart']);
  assert.equal(typeof installImageGuard(undefined), 'function');
});

test('the watermark text carries the name and the time, and is bounded', () => {
  assert.equal(watermarkText('팀원 A', new Date(2026, 10, 15, 9, 5)), '팀원 A · 2026-11-15 09:05');
  assert.match(watermarkText('', new Date(2026, 0, 2, 3, 4)), /^검수용 · 2026-01-02 03:04$/);
  assert.ok(watermarkText('x'.repeat(200)).startsWith('x'.repeat(40) + ' · '));
});

test('a name can never inject markup into the watermark image', () => {
  const style = watermarkStyle('<script>alert(1)</script> & "q"');
  const svg = decodeURIComponent(style.backgroundImage.split('utf8,')[1].replace(/"\)$/, ''));
  assert.ok(!svg.includes('<script>') && svg.includes('&lt;script&gt;') && svg.includes('&amp;') && svg.includes('&quot;q&quot;'));
  assert.equal(style.backgroundRepeat, 'repeat');
  assert.match(style.backgroundImage, /^url\("data:image\/svg\+xml;utf8,/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { monthOptions, limitBanner, usageCsv, fetchUsage } from './usageClient.mjs';

test('this month and last month are offered, also across a year change', () => {
  assert.deepEqual(monthOptions(new Date(Date.UTC(2026, 10, 16))), [{ value: '2026-11', label: '이번 달' }, { value: '2026-10', label: '지난 달' }]);
  assert.deepEqual(monthOptions(new Date(Date.UTC(2027, 0, 5))).map((o) => o.value), ['2027-01', '2026-12']);
});

test('limit banner: quiet below 80%, a warning from 80%, "reached" from the 90% stop line, nothing without a limit', () => {
  assert.equal(limitBanner(79, 100), null);
  assert.equal(limitBanner(80, 100).level, 80);
  assert.equal(limitBanner(89, 100).level, 80);
  const reached = limitBanner(90, 100);
  assert.equal(reached.level, 100); assert.match(reached.text, /한도에 도달했습니다 \(90\/100건\)/);
  assert.equal(limitBanner(0, 0), null); assert.equal(limitBanner(5, null), null); assert.equal(limitBanner(null, 100), null);
  assert.equal(limitBanner(1, 1).level, 100, 'a limit of 1 stops at 1');
});

test('csv: one row per member, services as columns, quotes escaped, formula-looking values neutralised', () => {
  const csv = usageCsv({ services: { tryon: 3 }, members: [
    { user_id: 'user-a', jobs: 3, failed: 1, services: { tryon: 3 } },
    { user_id: '=HYPERLINK("x")', jobs: 0, failed: 0, services: {} },
    { user_id: 'a,b"c', jobs: 1, failed: 0, services: { tryon: 1 } }] });
  assert.equal(csv, 'user_id,jobs,failed,tryon\r\nuser-a,3,1,3\r\n"\'=HYPERLINK(""x"")",0,0,0\r\n"a,b""c",1,0,1\r\n');
  assert.equal(usageCsv(null), 'user_id,jobs,failed\r\n');
});

test('the usage request goes to the workspace endpoint with the month and the token', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url: String(url), auth: init.headers.Authorization }; return new Response(JSON.stringify({ jobs: 0 }), { status: 200 }); };
  await fetchUsage('http://127.0.0.1:9', 'tok', 'ws 1', '2026-11');
  assert.deepEqual(seen, { url: 'http://127.0.0.1:9/v1/workspaces/ws%201/usage?month=2026-11', auth: 'Bearer tok' });
});

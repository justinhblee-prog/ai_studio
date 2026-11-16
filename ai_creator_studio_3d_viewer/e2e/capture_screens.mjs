// R-036: four real screens of the service for the homepage, captured from a TEMPORARY stack with SAMPLE data.
// Sample data: members "approver-a" / "approver-b" (no real names or e-mails), workspace "sample-team", library pictures are the
// placeholder display images of seed_library.py, the photo is a drawn sample (a coloured shape on a light background), jobs are mock-provider
// jobs (the finished ones carry a seeded output). Nothing here is a real customer, token or address.
// Usage: node e2e/capture_screens.mjs <output-dir>      Viewport 1440x900, scale 1, light theme (the app has no dark theme).
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { resolve } from 'node:path';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, apiCall, seedLibrary, seedFinishedJobOutput, sqliteExec, USERS } from './harness.mjs';

const outDir = resolve(process.argv[2] || 'design_assets/screens');
mkdirSync(outDir, { recursive: true });
USERS.a = { token: 'tok-sample-a', id: 'approver-a', email: 'approver-a@example.com' };
USERS.b = { token: 'tok-sample-b', id: 'approver-b', email: 'approver-b@example.com' };

const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc32 = (buf) => { let c = 0xFFFFFFFF; for (const b of buf) c = crcTable[(c ^ b) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
function drawPng(width, height, pixel) {   // pixel(x, y) -> [r, g, b]
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) { raw[y * (width * 3 + 1)] = 0; for (let x = 0; x < width; x += 1) { const [r, g, b] = pixel(x, y); const o = y * (width * 3 + 1) + 1 + x * 3; raw[o] = r; raw[o + 1] = g; raw[o + 2] = b; } }
  const chunk = (type, data) => { const t = Buffer.from(type, 'ascii'); const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data]))); return Buffer.concat([len, t, data, crc]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
// a "bag": rounded body with a handle, off-centre on a light grey backdrop, so auto-crop and canvas fit visibly change the picture
const sample = drawPng(640, 440, (x, y) => {
  const inBody = x > 200 && x < 470 && y > 170 && y < 380 && !((x < 215 || x > 455) && (y < 185 || y > 365));
  const inHandle = Math.abs(Math.hypot(x - 335, y - 175) - 70) < 7 && y < 175;
  if (inBody) return [Math.round(40 + (y - 170) * 0.3), Math.round(80 + (x - 200) * 0.2), Math.round(150 + (y - 170) * 0.2)];
  if (inHandle) return [30, 55, 110];
  return [236, 238, 240];
});

const stack = await startStack({ apiPort: 8768, webPort: 4768 });
const browser = await chromium.launch();
let failed = false;
try {
  seedLibrary(stack);
  const j = (token, path, init = {}) => apiCall(stack, token, path, { ...init, headers: { 'Content-Type': 'application/json', ...(init.headers || {}) } });
  const WS = 'sample-team';
  assert.equal((await j(USERS.a.token, '/v1/workspaces', { method: 'POST', body: JSON.stringify({ workspace_id: WS }) })).status, 201);
  assert.equal((await j(USERS.a.token, `/v1/workspaces/${WS}/members`, { method: 'POST', body: JSON.stringify({ user_id: USERS.b.id, role: 'admin' }) })).status, 201);
  const newJob = async () => { const r = await j(USERS.a.token, '/v1/generation-jobs', { method: 'POST', body: JSON.stringify({ workspace_id: WS, model_image_url: 'https://example.com/m.jpg', garment_image_url: 'https://example.com/g.jpg' }) }); assert.equal(r.status, 202); return r.body.job_id; };
  const jobs = [await newJob(), await newJob(), await newJob(), await newJob()];
  seedFinishedJobOutput(stack, jobs[0]); seedFinishedJobOutput(stack, jobs[1]);
  sqliteExec(stack, "UPDATE generation_jobs SET status='failed', error_code='PROVIDER_GENERATION_FAILED' WHERE job_id=?", [jobs[3]]);
  sqliteExec(stack, "UPDATE generation_jobs SET status='running' WHERE job_id=?", [jobs[2]]);

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await mockSupabase(context, USERS.a);
  const page = await context.newPage();
  await loginThroughUi(page, stack.webUrl, USERS.a);
  await page.locator('.workspace-select').selectOption(WS);
  const shot = async (name) => { await page.waitForTimeout(600); await page.screenshot({ path: resolve(outDir, name), fullPage: false }); console.log('captured', name); };

  // 1 jobs
  await gotoPage(page, '생성 작업 결과');
  await page.locator('ul[aria-label="작업 목록"] li').first().waitFor({ timeout: 15000 });
  await page.locator('ul[aria-label="작업 목록"] li').first().click().catch(() => {});
  await shot('screen-01-jobs.png');

  // 2 library, model tab, filters in use
  await page.locator('button.nav', { hasText: '라이브러리' }).filter({ hasNotText: '에셋' }).click();
  const lib = page.locator('section[aria-label="라이브러리"]');
  await lib.locator('ul[aria-label="라이브러리 항목"] li').first().waitFor({ timeout: 15000 });
  await lib.getByLabel('머리').selectOption('wavy');
  await page.waitForFunction(() => document.querySelectorAll('ul[aria-label="라이브러리 항목"] li').length >= 1, null, { timeout: 10000 });
  await page.waitForFunction(() => { const i = document.querySelector('ul[aria-label="라이브러리 항목"] li img'); return !!i && i.complete && i.naturalWidth > 0; }, null, { timeout: 10000 });
  await shot('screen-02-library.png');

  // 3 before/after slider on the photo screen
  const form = new FormData(); form.set('workspace_id', WS); form.set('rights_confirmed', 'true');
  form.set('file', new Blob([sample], { type: 'image/png' }), 'sample-bag.png');
  assert.equal((await fetch(`${stack.apiUrl}/v1/assets/images`, { method: 'POST', headers: { Authorization: `Bearer ${USERS.a.token}` }, body: form })).status, 201);
  await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 }); await page.locator('.workspace-select').selectOption(WS);
  await gotoPage(page, '포토 스튜디오');
  const panel = page.locator('section[aria-label="사진 단계 편집"]');
  await panel.getByLabel('편집할 이미지').selectOption({ label: 'sample-bag.png' });
  await panel.getByRole('button', { name: /자동 크롭/ }).click();
  await panel.getByRole('button', { name: /캔버스 맞춤/ }).click();
  const second = panel.locator('ol[aria-label="적용할 단계"] > li').nth(1);
  await second.getByLabel('가로(px)').fill('640'); await second.getByLabel('세로(px)').fill('440');
  await panel.getByRole('button', { name: /실행해서/ }).click();
  await panel.getByRole('group', { name: '전후 슬라이더' }).waitFor({ timeout: 20000 });
  await page.waitForFunction(() => [...document.querySelectorAll('img[alt^="슬라이더"]')].every(i => i.complete && i.naturalWidth > 0), null, { timeout: 10000 });
  await panel.getByRole('slider', { name: '전후 비교 슬라이더' }).fill('50');
  await panel.getByRole('group', { name: '전후 슬라이더' }).scrollIntoViewIfNeeded();
  await page.evaluate(() => { const el = document.querySelector('[aria-label="전후 슬라이더"]'); el?.scrollIntoView({ block: 'center' }); });
  await shot('screen-03-compare.png');

  // 4 approval history with two approvers
  const outputId = (await j(USERS.a.token, `/v1/generation-jobs/${jobs[0]}/outputs`)).body.data[0].id;
  const decide = (user, action, comment) => j(user.token, `/v1/generation-jobs/${jobs[0]}/outputs/${outputId}/review/${action}`, { method: 'POST', body: JSON.stringify({ comment }) });
  assert.equal((await decide(USERS.a, 'request-changes', '로고 색을 조금 더 진하게 부탁드립니다.')).status, 200);
  assert.equal((await decide(USERS.b, 'approve', '수정 확인했습니다. 승인합니다.')).status, 200);
  await page.getByRole('button', { name: /설정/ }).click();
  await page.locator('section.settings label', { hasText: '결과 검수 Job ID' }).locator('input').fill(jobs[0]);
  await page.getByRole('button', { name: /설정/ }).click();
  await gotoPage(page, '결과물 검수');
  await page.locator('article.acs-output-review-item ol.acs-output-review-history li').nth(1).waitFor({ timeout: 15000 });
  await shot('screen-04-approval.png');
} catch (error) { console.error(error); failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);

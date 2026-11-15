// R-030 B in the browser: when the server answers 503 / 429 or the connection is down, every list screen says so in Korean and never
// shows the server's English wording or the browser's "Failed to fetch". (401 is handled by the sign-in dialog: see session_flow.mjs.)
import assert from 'node:assert/strict';
import { startStack, chromium, mockSupabase, loginThroughUi, gotoPage, makeRunner, USERS } from './harness.mjs';
import { MESSAGES } from '../src/app/errorMessages.mjs';

const SCREENS = ['에셋 라이브러리', '프로젝트 관리', '상품 카탈로그', '프로젝트·상품 연결', '포토 스튜디오', '룩북 스튜디오', '가상 착장 시험 생성', '생성 작업 결과'];
const ENGLISH = /Failed to fetch|NetworkError|Load failed|Service Unavailable|Too Many Requests|Invalid|Unauthorized|Internal Server|Bad Gateway|undefined|\[object/i;
const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const context = await browser.newContext(); await mockSupabase(context, USERS.owner);
  const page = await context.newPage();
  const { run, results } = makeRunner(page, stack);
  const modes = {
    '503 (server trouble)': { expect: MESSAGES.server, handler: route => (route.request().method() === 'OPTIONS' ? route.fulfill({ status: 204, headers: cors }) : route.fulfill({ status: 503, contentType: 'application/json', headers: cors, body: JSON.stringify({ detail: 'Service Unavailable' }) })) },
    '429 (too many requests)': { expect: MESSAGES.tooMany, handler: route => (route.request().method() === 'OPTIONS' ? route.fulfill({ status: 204, headers: cors }) : route.fulfill({ status: 429, contentType: 'application/json', headers: cors, body: JSON.stringify({ detail: 'Too Many Requests' }) })) },
    'connection lost': { expect: MESSAGES.network, handler: route => route.abort('failed') },
  };
  await run('login', async () => { await loginThroughUi(page, stack.webUrl, USERS.owner); });
  for (const [name, { expect, handler }] of Object.entries(modes)) {
    await run(`${name}: all ${SCREENS.length} list screens show the Korean message and no English wording`, async () => {
      await page.route(`${stack.apiUrl}/v1/**`, handler);
      const bad = [];
      for (const screen of SCREENS) {
        await gotoPage(page, screen);
        await page.waitForTimeout(1000);
        const alerts = await page.locator('main [role=alert], main .auth-error').allInnerTexts();
        const joined = alerts.join(' | ');
        if (!joined.includes(expect)) bad.push(`${screen}: expected "${expect}" but saw "${joined.slice(0, 120)}"`);
        if (ENGLISH.test(joined)) bad.push(`${screen}: English wording visible: "${joined.slice(0, 120)}"`);
        if (!(await page.getByRole('button', { name: '다시 불러오기' }).isVisible())) bad.push(`${screen}: no retry (다시 불러오기) button`);
      }
      await page.unroute(`${stack.apiUrl}/v1/**`, handler);
      assert.deepEqual(bad, [], bad.join('\n'));
    });
  }
  await run('the retry button reloads a screen that failed: after the server is back the error is gone', async () => {
    await page.route(`${stack.apiUrl}/v1/**`, modes['503 (server trouble)'].handler);
    await gotoPage(page, '프로젝트 관리');
    await page.locator('main [role=alert], main .auth-error').first().waitFor({ timeout: 10000 });
    await page.unroute(`${stack.apiUrl}/v1/**`, modes['503 (server trouble)'].handler);
    await page.getByRole('button', { name: '다시 불러오기' }).click();
    await page.waitForFunction(() => !document.querySelector('main [role=alert], main .auth-error'), null, { timeout: 15000 });
  });
  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} error message steps passed`);
} catch { failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);

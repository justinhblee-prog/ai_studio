// Responsive layout: no screen may be wider than the viewport (a page that scrolls sideways is broken on phones and tablets).
// Real: web bundle, backend, SQLite. Mocked: Supabase Auth. The 3D studio (WebGL) and the job review screen (needs a job) are not covered.
import assert from 'node:assert/strict';
import { startStack, chromium, loginThroughUi, gotoPage, newUserPage, seedSharedWorkspace, makeRunner, USERS } from './harness.mjs';

const WIDTHS = [360, 390, 700, 701, 768, 840, 900, 901, 1024, 1280];
const SCREENS = ['대시보드', '프로젝트 관리', '에셋 라이브러리', '상품 카탈로그', '프로젝트·상품 연결', '포토 스튜디오', '룩북 스튜디오'];

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
try {
  const seed = await seedSharedWorkspace(stack);  // gives the lists real content (long ids)
  const { context, page } = await newUserPage(browser, USERS.owner, { viewport: { width: 1280, height: 800 } });
  const { run, results } = makeRunner(page, stack);
  await run('login and select the seeded workspace', async () => {
    await loginThroughUi(page, stack.webUrl, USERS.owner);
    await page.locator('.workspace-select').selectOption(seed.workspace);
  });
  for (const width of WIDTHS) {
    await run(`no screen is wider than a ${width}px viewport`, async () => {
      await page.setViewportSize({ width, height: 800 });
      const wide = [];
      for (const screen of SCREENS) {
        await gotoPage(page, screen);
        await page.waitForLoadState('networkidle').catch(() => {});
        await page.evaluate(() => document.fonts?.ready);
        await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
        await page.waitForTimeout(250);
        const m = await page.evaluate(() => {
          const inner = window.innerWidth;
          const offenders = [...document.querySelectorAll('body *')].map(el => ({ el, r: el.getBoundingClientRect() }))
            .filter(({ r }) => r.width > 0 && r.right > inner + 1).slice(0, 4)
            .map(({ el, r }) => `${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''} right=${Math.round(r.right)} text="${(el.textContent || '').trim().slice(0, 40)}"`);
          return { scroll: document.documentElement.scrollWidth, inner, offenders };
        });
        if (m.scroll > m.inner + 1) wide.push(`${screen}: ${m.scroll}px > ${m.inner}px [${m.offenders.join(' | ')}]`);
      }
      assert.deepEqual(wide, [], 'horizontal overflow on: ' + wide.join('; '));
    });
  }
  const overflowAt = async (pg, label) => {
    const wide = [];
    for (const width of WIDTHS) {
      await pg.setViewportSize({ width, height: 800 });
      await pg.waitForTimeout(150);
      const m = await pg.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
      if (m.scroll > m.inner + 1) wide.push(`${width}px: ${m.scroll}px`);
    }
    assert.deepEqual(wide, [], `horizontal overflow on ${label}: ` + wide.join('; '));
  };
  await run('the settings panel with the account section is not wider than the viewport at any width', async () => {
    await page.getByRole('button', { name: /설정/ }).click();
    await page.locator('.account-panel').waitFor();
    await overflowAt(page, 'settings + account panel');
    await page.getByRole('button', { name: /설정/ }).click();
  });
  await run('the legal acceptance gate is not wider than the viewport at any width', async () => {
    const fresh = await newUserPage(browser, USERS.editor, { viewport: { width: 1280, height: 800 } });
    await loginThroughUi(fresh.page, stack.webUrl, USERS.editor, { acceptLegal: false });
    await fresh.page.locator('.legal-gate').waitFor();
    await overflowAt(fresh.page, 'legal gate');
    await fresh.context.close();
  });
  await context.close();
  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} layout checks passed (${WIDTHS.length} widths x ${SCREENS.length} screens + settings account panel + legal gate)`);
} catch (error) { if (!(error && String(error.message).includes('horizontal overflow'))) console.log('ERROR ' + (error && error.stack || error).toString().slice(0, 600)); failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);

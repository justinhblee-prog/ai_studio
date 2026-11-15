// R-030 audit: looks at every screen and PRINTS findings (screen, category, detail). It never fails the build; it is a report tool.
// Real: web bundle, backend, SQLite. Mocked: Supabase Auth. No AI provider is called. Run: node e2e/audit_flow.mjs
import { startStack, chromium, loginThroughUi, gotoPage, newUserPage, seedSharedWorkspace, USERS } from './harness.mjs';

const SCREENS = ['대시보드', '프로젝트 관리', '에셋 라이브러리', '3D 스튜디오', '상품 카탈로그', '프로젝트·상품 연결', '포토 스튜디오', '가상 착장 시험 생성', '생성 작업 결과', '룩북 스튜디오', '결과물 검수'];
const findings = [];
const add = (screen, category, detail) => { findings.push({ screen, category, detail }); console.log(`FINDING | ${screen} | ${category} | ${detail}`); };
const RETRY = /다시 시도|재시도|새로고침|다시 불러오기|다시 확인/;
const RAW = /Failed to fetch|NetworkError|TypeError|Unexpected token|undefined|\[object|API 요청 실패|Load failed|fetch failed|HTTP \d{3}/i;

const stack = await startStack();
const browser = await chromium.launch();
try {
  const seed = await seedSharedWorkspace(stack);
  const { context, page } = await newUserPage(browser, USERS.owner, { viewport: { width: 1280, height: 800 } });
  await loginThroughUi(page, stack.webUrl, USERS.owner);
  await page.locator('.workspace-select').selectOption(seed.workspace);
  await page.waitForTimeout(500);

  // 1) failure modes: 401 / 503 / network down, screen by screen
  const modes = {
    '401': route => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Invalid token' }) }),
    '503': route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Service Unavailable' }) }),
    'network': route => route.abort('failed'),
  };
  for (const [mode, handler] of Object.entries(modes)) {
    await page.route('**/v1/**', handler);
    for (const screen of SCREENS) {
      try {
        await gotoPage(page, screen);
        await page.waitForTimeout(900);
        const info = await page.evaluate((retrySrc) => {
          const main = document.querySelector('main') || document.body;
          const text = main.innerText || '';
          const alerts = [...main.querySelectorAll('[role=alert], .auth-error, .warning, [role=status]')].map(e => e.innerText.trim()).filter(Boolean);
          const buttons = [...main.querySelectorAll('button')].map(b => (b.innerText || b.getAttribute('aria-label') || '').trim());
          const retry = buttons.some(t => new RegExp(retrySrc).test(t));
          return { text: text.slice(0, 2000), alerts, retry, loginShown: /로그인/.test(document.body.innerText) && !!document.querySelector('input[type=password], input[type=email]') };
        }, RETRY.source);
        const where = `${screen} (${mode})`;
        if (mode === '401' && info.loginShown) continue; // session-expiry handled by returning to login: fine
        const msg = info.alerts.join(' / ');
        if (!msg) add(screen, `오류 안내 없음 [${mode}]`, '화면에 오류·상태 안내(role=alert 등)가 보이지 않음(빈 화면이거나 조용히 실패)');
        else {
          if (!/[가-힣]/.test(msg)) add(screen, `영어 오류 [${mode}]`, `안내가 한국어가 아님: "${msg.slice(0, 120)}"`);
          if (RAW.test(msg)) add(screen, `기술 문구 노출 [${mode}]`, `내부 오류 문구가 그대로 보임: "${msg.slice(0, 120)}"`);
        }
        if (!info.retry) add(screen, `다시 시도 경로 없음 [${mode}]`, '오류 상태에서 "다시 시도/새로고침" 버튼이 없음(다른 화면으로 갔다 와야 할 수 있음)');
        void where;
      } catch (error) { add(screen, `점검 실패 [${mode}]`, String(error.message).split('\n')[0].slice(0, 150)); }
    }
    await page.unroute('**/v1/**', handler);
  }
  await page.reload(); await page.locator('.workspace-select').waitFor({ timeout: 20000 });
  await page.locator('.workspace-select').selectOption(seed.workspace);

  // 2) accessible names, labels, focus visibility, per screen
  for (const screen of SCREENS) {
    await gotoPage(page, screen);
    await page.waitForTimeout(500);
    const res = await page.evaluate(() => {
      const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const main = document.querySelector('main') || document.body;
      const nameOf = el => (el.getAttribute('aria-label') || '').trim() || (el.getAttribute('aria-labelledby') && [...el.getAttribute('aria-labelledby').split(' ')].map(id => document.getElementById(id)?.innerText || '').join(' ').trim()) || (el.labels && [...el.labels].map(l => l.innerText).join(' ').trim()) || (['BUTTON', 'A'].includes(el.tagName) ? (el.innerText || '').trim() : '') || (el.getAttribute('title') || '').trim();
      const noName = [], placeholderOnly = [], hiddenFile = [];
      for (const el of main.querySelectorAll('button, a[href], input, select, textarea, [role=button]')) {
        if (el.type === 'hidden') continue;
        const snippet = el.outerHTML.replace(/\s+/g, ' ').slice(0, 90);
        if (el.type === 'file') { if (!visible(el) && !el.closest('label')) hiddenFile.push(snippet); }
        if (!visible(el)) continue;
        if (!nameOf(el)) { if (el.getAttribute('placeholder') && el.tagName !== 'BUTTON') placeholderOnly.push(snippet); else noName.push(snippet); }
      }
      return { noName, placeholderOnly, hiddenFile };
    });
    for (const s of res.noName) add(screen, '이름 없는 컨트롤', s);
    for (const s of res.placeholderOnly) add(screen, '라벨 없음(자리표시자만)', s);
    for (const s of res.hiddenFile) add(screen, '파일 입력이 숨겨져 키보드로 못 감', s);
    // Tab through the first 30 stops: is focus ever invisible?
    await page.locator('main').first().click({ position: { x: 2, y: 2 } }).catch(() => {});
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    let invisible = 0; let stops = 0; const seen = new Set(); let example = '';
    for (let i = 0; i < 30; i += 1) {
      await page.keyboard.press('Tab');
      const f = await page.evaluate(() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
        return { key: e.tagName + '|' + (e.className || '') + '|' + (e.innerText || e.getAttribute('aria-label') || '').slice(0, 20), outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0, shadow: s.boxShadow !== 'none', border: s.borderColor, html: e.outerHTML.replace(/\s+/g, ' ').slice(0, 80) }; });
      if (!f || seen.has(f.key)) { if (f && seen.has(f.key)) break; continue; }
      seen.add(f.key); stops += 1;
      if (!f.outline && !f.shadow) { invisible += 1; if (!example) example = f.html; }
    }
    if (invisible) add(screen, '초점 표시 약함', `${stops}개 Tab 정지 중 ${invisible}개가 outline·box-shadow가 없음(예: ${example})`);
  }

  // 3) modal: Esc closes and returns focus (legal text opened from settings)
  try {
    await page.getByRole('button', { name: /설정/ }).click();
    await page.locator('.account-panel').waitFor({ timeout: 5000 });
    const opener = page.getByRole('button', { name: /본문 보기|약관|방침/ }).first();
    if (await opener.count()) {
      await opener.focus(); await opener.press('Enter');
      const dialog = page.locator('[role=dialog]').first();
      await dialog.waitFor({ timeout: 4000 });
      const hasLabel = await dialog.evaluate(d => !!(d.getAttribute('aria-label') || d.getAttribute('aria-labelledby')));
      if (!hasLabel) add('설정·약관 모달', '모달 이름 없음', 'role=dialog에 aria-label/labelledby가 없음');
      await page.keyboard.press('Escape'); await page.waitForTimeout(300);
      if (await page.locator('[role=dialog]').count()) add('설정·약관 모달', 'Esc로 안 닫힘', 'Esc를 눌러도 대화상자가 남아 있음');
      else if (!(await opener.evaluate(e => e === document.activeElement))) add('설정·약관 모달', '초점 복귀 안 됨', '닫은 뒤 초점이 연 버튼으로 돌아오지 않음');
    } else add('설정·약관 모달', '점검 불가', '"본문 보기" 버튼을 찾지 못함');
    await page.getByRole('button', { name: /설정/ }).click().catch(() => {});
  } catch (error) { add('설정·약관 모달', '점검 실패', String(error.message).split('\n')[0].slice(0, 150)); }

  // 4) phone width: sideways scroll on EVERY screen, and which element is widest
  await page.setViewportSize({ width: 360, height: 800 });
  for (const screen of SCREENS) {
    await gotoPage(page, screen); await page.waitForTimeout(400);
    const m = await page.evaluate(() => {
      const inner = window.innerWidth; const scroll = document.documentElement.scrollWidth;
      let worst = null;
      if (scroll > inner + 1) for (const el of document.querySelectorAll('main *')) { const r = el.getBoundingClientRect(); if (r.right > inner + 1 && (!worst || r.right > worst.right)) worst = { right: Math.round(r.right), html: el.outerHTML.replace(/\s+/g, ' ').slice(0, 90) }; }
      return { inner, scroll, worst };
    });
    if (m.scroll > m.inner + 1) add(screen, '360px 가로 스크롤', `${m.scroll}px > ${m.inner}px; 가장 넓은 요소: ${m.worst ? `${m.worst.right}px ${m.worst.html}` : '찾지 못함'}`);
  }
  await context.close();
} catch (error) { console.log('AUDIT_ERROR ' + (error && error.stack || error).toString().slice(0, 600)); }
finally { await browser.close(); await stack.stop(); }
const byCat = {};
for (const f of findings) byCat[f.category] = (byCat[f.category] || 0) + 1;
console.log('AUDIT_SUMMARY ' + findings.length + ' findings');
for (const [c, n] of Object.entries(byCat)) console.log(`AUDIT_CATEGORY | ${c} | ${n}`);
process.exit(0);

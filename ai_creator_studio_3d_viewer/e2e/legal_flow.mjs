// L-02 / L-01 in the browser: the acceptance gate, the optional AI-training consent, and account deletion requests.
// Real: web bundle, backend, SQLite. Mocked: Supabase Auth. The legal documents are drafts and their text is not in the app.
import assert from 'node:assert/strict';
import { startStack, chromium, newUserPage, loginThroughUi, acceptLegalThroughUi, makeRunner, apiCall, USERS } from './harness.mjs';

const stack = await startStack();
const browser = await chromium.launch();
let failed = false;
const status = who => apiCall(stack, who.token, '/v1/me/legal-status');
const aiConsent = async who => (await apiCall(stack, who.token, '/v1/me/consents')).body.items.find(c => c.purpose === 'ai_training').granted;
try {
  const a = await newUserPage(browser, USERS.owner);
  const { run, results } = makeRunner(a.page, stack);
  const gate = () => a.page.locator('.legal-gate');
  const submit = () => gate().getByRole('button', { name: '동의하고 계속' });

  await run('a user who has not accepted is stopped at the gate: the app is not shown and the button needs every required box', async () => {
    await loginThroughUi(a.page, stack.webUrl, USERS.owner, { acceptLegal: false });
    assert.equal(await gate().count(), 1);
    assert.equal(await a.page.locator('.workspace-select').count(), 0, 'the studio must not render behind the gate');
    assert.match(await gate().innerText(), /초안/);
    const required = gate().locator('.legal-list input[type=checkbox]');
    assert.equal(await required.count(), 3);
    assert.equal(await submit().isDisabled(), true);
    await required.nth(0).check(); await required.nth(1).check();
    assert.equal(await submit().isDisabled(), true, 'two of three is not enough');
    assert.equal(await gate().locator('.legal-optional input').isChecked(), false, 'the optional consent is off by default');
    assert.equal((await status(USERS.owner)).body.accepted, false, 'nothing is recorded before the button is pressed');
  });

  await run('accepting without the optional box opens the app, records the acceptance and leaves AI-training consent off', async () => {
    await gate().locator('.legal-list input[type=checkbox]').nth(2).check();
    await submit().click();
    await a.page.locator('.workspace-select').waitFor({ timeout: 20000 });
    assert.equal((await status(USERS.owner)).body.accepted, true);
    assert.equal(await aiConsent(USERS.owner), false);
  });

  await run('a second user who ticks the optional box has the consent recorded, and can withdraw it in settings', async () => {
    const b = await newUserPage(browser, USERS.editor);
    await loginThroughUi(b.page, stack.webUrl, USERS.editor, { acceptLegal: false });
    await acceptLegalThroughUi(b.page, { aiTraining: true });
    await b.page.locator('.workspace-select').waitFor({ timeout: 20000 });
    assert.equal(await aiConsent(USERS.editor), true);
    assert.equal(await aiConsent(USERS.owner), false, 'another user is unaffected');
    await b.page.getByRole('button', { name: /설정/ }).click();
    const box = b.page.locator('.account-consent input');
    await b.page.waitForFunction(() => { const i = document.querySelector('.account-consent input'); return i && !i.disabled; }); // enabled once the consents have loaded
    assert.equal(await box.isChecked(), true);
    await box.click(); // the box is controlled by server state, so it flips only after the PUT returns
    await b.page.waitForFunction(() => !document.querySelector('.account-consent input')?.checked);
    assert.equal(await aiConsent(USERS.editor), false);
    await b.context.close();
  });

  await run('account deletion request from settings: confirm, shown as pending, only recorded (nothing deleted), then cancelled', async () => {
    await a.page.getByRole('button', { name: /설정/ }).click();
    const panel = a.page.locator('.account-panel');
    await panel.getByRole('button', { name: '계정 삭제 요청' }).click();
    await panel.locator('.auth-notice').waitFor();
    assert.match(await panel.innerText(), /접수되어 있습니다/);
    const list = (await apiCall(stack, USERS.owner.token, '/v1/me/deletion-requests')).body.items;
    assert.deepEqual(list.map(r => [r.scope, r.status]), [['account', 'pending']]);
    const ws = await apiCall(stack, USERS.owner.token, '/v1/workspaces');
    assert.ok(ws.body.items.length >= 1, 'the workspace still exists: a request does not delete anything');
    await panel.getByRole('button', { name: '요청 취소' }).click();
    await panel.getByRole('button', { name: '계정 삭제 요청' }).waitFor();
    const after = (await apiCall(stack, USERS.owner.token, '/v1/me/deletion-requests')).body.items;
    assert.deepEqual(after.map(r => r.status), ['cancelled']);
  });

  await run('declining at the gate signs the user out and records nothing', async () => {
    const c = await newUserPage(browser, USERS.viewer);
    await loginThroughUi(c.page, stack.webUrl, USERS.viewer, { acceptLegal: false });
    await c.page.getByRole('button', { name: '동의하지 않고 로그아웃' }).click();
    await c.page.getByRole('button', { name: '로그인' }).first().waitFor({ timeout: 20000 });
    assert.equal((await status(USERS.viewer)).body.accepted, false);
    await c.context.close();
  });

  console.log(`SUMMARY ${results.filter(r => r.ok).length}/${results.length} legal screen steps passed`);
  await a.context.close();
} catch (error) { if (!(globalThis.__reported)) console.log('ERROR ' + (error && error.stack || error).toString().slice(0, 800)); failed = true; }
finally { await browser.close(); await stack.stop(); }
process.exit(failed ? 1 : 0);

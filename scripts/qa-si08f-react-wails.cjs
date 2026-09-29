// SI08-F nonvisual acceptance through actual React handlers and Wails bindings.
// The only substitution is the native project folder picker: it calls the
// existing read-only App.OpenProject with the explicitly supplied QA root.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../frontend/node_modules/playwright-core');

const root = process.env.PLATFORM_QA_PROJECT_ROOT;
const passwordFile = process.env.PLATFORM_QA_PASSWORD_FILE;
const keyFile = process.env.PLATFORM_QA_SSH_KEY;
if (!root || !path.isAbsolute(root) || !passwordFile || !keyFile) {
  throw new Error('QA_INPUT_REQUIRED');
}
const secret = fs.readFileSync(passwordFile, 'utf8').replace(/\r?\n$/, '');
if (!secret) throw new Error('QA_PASSWORD_EMPTY');
const url = 'http://127.0.0.1:34115';
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => {
    // Wails' development IPC emits this before its backend handshake; it is
    // outside React rendering. Every other page exception is a QA failure.
    if (error.stack?.includes('/wails/ipc.js') && error.message.includes("null (reading 'nodes')")) return;
    errors.push(error.message.slice(0, 200));
  });
  try {
    await page.goto(url, { timeout: 30000 });
    await page.waitForFunction(() => typeof window.go?.main?.App?.OpenProject === 'function');
    await page.evaluate((projectRoot) => {
      const app = window.go.main.App;
      const open = app.OpenProject.bind(app);
      app.ChooseProject = async () => { const result = await open(projectRoot); window.__qaOpen = result; return result; };
    }, root.replaceAll('\\', '/'));
    await page.getByRole('button', { name: 'Открыть проект' }).click();
    await page.locator('header strong').getByText('si08f-vault-endpoint-ha-20260928').waitFor({ timeout: 30000 });
    console.log('QA_OPEN=PASS');

    await page.locator('aside nav').getByRole('button', { name: 'Серверы', exact: true }).click();
    await page.getByRole('button', { name: 'Проверить узел' }).click();
    await page.waitForFunction(async () => (await window.go.main.App.GetExecutionNodeContext()).status === 'READY', undefined, { timeout: 90000 });
    console.log('QA_NODE=READY');

    const credentials = page.locator('.session-credentials');
    await credentials.getByLabel('Технический пользователь').fill('platform-automation');
    await credentials.getByLabel('SSH-аутентификация').selectOption('SSH_PRIVATE_KEY');
    await credentials.getByLabel('Абсолютный путь к приватному ключу').fill(keyFile);
    await credentials.getByRole('button', { name: 'Сохранить в сеансе' }).click();
    await page.waitForFunction(async () => {
      const value = await window.go.main.App.GetSessionCredentialStatus();
      return value.status === 'PRESENT' && Date.parse(value.expiresAt) > Date.now() + 25 * 60 * 1000;
    }, undefined, { timeout: 15000 });
    console.log('QA_CREDENTIAL=PRESENT');

    // Exercise the real Services -> Secrets React handlers and Wails import.
    // The dev-only OS picker supplies already-owned encrypted QA file paths;
    // neither the paths nor decrypted bytes are exposed to this browser script.
    await page.locator('aside nav').getByRole('button', { name: 'Сервисы', exact: true }).click();
    await page.locator('.topology-row').filter({ hasText: 'vault-endpoint-ha' }).click();
    await page.locator('.service-secrets-action').getByRole('button', { name: 'Секреты' }).click();
    const secretDialog = page.locator('dialog.runtime-secret-dialog[open]');
    try {
      await secretDialog.waitFor({ timeout: 15000 });
    } catch {
      const diagnostic = await page.evaluate(async () => {
        const operation = await window.go.main.App.GetPendingRuntimeSecretDescriptors('vault-endpoint-ha');
        const context = await window.go.main.App.GetExecutionNodeContext();
        const opened = window.__qaOpen;
        const vault = opened?.catalog?.services?.find((item) => item.id === 'vault');
        return { status: operation.status, code: operation.error?.code, purposes: operation.descriptors?.map((item) => item.purpose), uiError: document.querySelector('.service-secrets-action .error')?.textContent?.slice(0, 120), node: context.status, selectedHost: context.selectedHostId, catalog: opened?.catalog?.status, vaultInputs: vault?.secretInputs?.length, vaultModeCount: vault?.modes?.length, managed: !!opened?.managed };
      });
      console.log(`QA_SECRET_DIALOG_DIAGNOSTIC=${JSON.stringify(diagnostic)}`);
      throw new Error('QA_SECRET_DIALOG_UNAVAILABLE');
    }
    const imports = [
      { label: 'Administrative token', proof: 'QA_ADMIN_TOKEN=STORED' },
      { label: 'Unseal keys', proof: 'QA_UNSEAL_SHARES=STORED' },
    ];
    for (const entry of imports) {
      const row = secretDialog.locator('.runtime-secret-file-input').filter({ hasText: entry.label });
      await row.getByLabel('Пароль файла age, если файл зашифрован').fill(secret);
      await row.getByRole('button', { name: 'Выбрать файл' }).click();
      await row.getByText('Файл принят и сохранён только в сессии.').waitFor({ timeout: 15000 });
      console.log(entry.proof);
    }
    await secretDialog.getByRole('button', { name: 'Готово' }).click();

    await page.locator('aside nav').getByRole('button', { name: 'Установка', exact: true }).click();
    await page.getByRole('button', { name: 'Сформировать свежий план' }).click();
    await page.getByText('Свежий DeploymentPlan').waitFor({ timeout: 120000 });
    const state = await page.evaluate(() => window.go.main.App.GetInstallationState());
    const planId = state.plan?.planId;
    if (!planId) throw new Error('QA_PLAN_MISSING');
    const operation = await page.evaluate((id) => window.go.main.App.GetInstallationPlan(id), planId);
    if (operation.status !== 'PLAN_REVIEW' || operation.plan?.status !== 'EXECUTABLE') {
      throw new Error(`QA_PLAN_NOT_EXECUTABLE:${operation.status}:${operation.error?.code || ''}`);
    }
    console.log(`QA_PLAN=${planId}`);

    if (operation.plan.secretOutputEncryptionRequired) {
      const output = page.locator('.secret-output-setup');
      if (await output.getByLabel('Пароль шифрования').count()) {
        await output.getByLabel('Пароль шифрования').fill(secret);
        await output.getByLabel('Повторите пароль').fill(secret);
        await output.getByRole('button', { name: 'Сохранить пароль в сеансе' }).click();
      }
      await output.getByText('Пароль шифрования задан для текущего сеанса.').waitFor({ timeout: 15000 });
      console.log('QA_OUTPUT_ENCRYPTION=PRESENT');
    }
    const approval = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'Подтверждение' }) });
    const checks = approval.locator('input[type=checkbox]');
    for (let i = 0, count = await checks.count(); i < count; i++) await checks.nth(i).check();
    await approval.getByRole('button', { name: 'Одобрить план' }).click();
    await page.getByRole('heading', { name: 'План одобрен' }).waitFor({ timeout: 15000 });
    console.log('QA_APPROVAL=PASS');
    const start = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'План одобрен' }) });
    if (operation.plan.pkiStorePasswordRequired) {
      if (await start.getByLabel('Пароль хранилища PKI').count()) {
        await start.getByLabel('Пароль хранилища PKI').fill(secret);
        await start.getByRole('button', { name: 'Добавить пароль в сеанс' }).click();
      }
      await page.waitForFunction(async () => (await window.go.main.App.GetSessionCredentialStatus()).pkiStorePasswordStatus === 'PRESENT', undefined, { timeout: 15000 });
      console.log('QA_PKI_PASSWORD=PRESENT');
    }
    const finalCredential = await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus());
    if (finalCredential.status !== 'PRESENT' || finalCredential.pkiStorePasswordStatus !== 'PRESENT' || Date.parse(finalCredential.expiresAt) <= Date.now() + 20 * 60 * 1000) {
      throw new Error('QA_CREDENTIAL_STALE_BEFORE_START');
    }
    await start.getByRole('button', { name: 'Начать выполнение' }).waitFor({ state: 'visible' });
    try {
      await page.waitForFunction(() => {
        const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === 'Начать выполнение');
        return button && !button.disabled;
      }, undefined, { timeout: 15000 });
    } catch {
      const evidence = await page.evaluate(async (id) => {
        const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === 'Начать выполнение');
        const app = window.go.main.App;
        const plan = await app.GetInstallationPlan(id);
        const credentials = await app.GetSessionCredentialStatus();
        return { disabled: button?.disabled, outputStatusShown: !!document.querySelector('.secret-output-setup .success'),
          planApproved: plan.plan?.approved, outputBackend: plan.plan?.secretOutputEncryptionPasswordPresent,
          credential: credentials.status, pki: credentials.pkiStorePasswordStatus };
      }, planId);
      console.log(`QA_START_DISABLED=${JSON.stringify(evidence)}`);
      throw new Error('QA_START_DISABLED');
    }
    if (process.env.PLATFORM_QA_START !== 'yes') {
      console.log('QA_START=HELD');
      return;
    }
    await page.evaluate(() => {
      const app = window.go.main.App;
      const start = app.StartApprovedInstallation.bind(app);
      app.StartApprovedInstallation = async (id) => {
        const result = await start(id);
        window.__qaStartResult = { status: result.status, runId: result.run?.runId, error: result.error?.code };
        return result;
      };
    });
    await start.getByRole('button', { name: 'Начать выполнение' }).click();
    await page.waitForFunction(() => window.__qaStartResult !== undefined, undefined, { timeout: 120000 });
    const startResult = await page.evaluate(() => window.__qaStartResult);
    console.log(`QA_START_RESULT=${JSON.stringify(startResult)}`);
    if (startResult.status !== 'STARTED' || !startResult.runId) throw new Error('QA_START_BLOCKED');
    await page.getByRole('heading', { name: 'Выполнение' }).first().waitFor({ timeout: 15000 });
    const runId = startResult.runId;
    if (!runId) throw new Error('QA_RUN_ID_MISSING');
    console.log(`QA_RUN=${runId}`);
    const deadline = Date.now() + 90 * 60 * 1000;
    let terminal = false;
    while (Date.now() < deadline) {
      const current = await page.evaluate((id) => window.go.main.App.GetInstallationRun(id), runId);
      if (current.status === 'READY' && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(current.run?.state)) {
        console.log(`QA_TERMINAL=${current.run.state} SEQUENCE=${current.run.sequence}`);
        if (current.run.state !== 'SUCCEEDED') throw new Error('QA_RUN_NOT_SUCCEEDED');
        terminal = true;
        break;
      }
      await pause(30000);
    }
    if (!terminal) throw new Error('QA_RUN_TIMEOUT');
    if (errors.length) throw new Error(`QA_PAGE_EXCEPTION:${errors.join(',')}`);
  } finally {
    await browser.close();
  }
}
main().catch((error) => {
  console.error(error.message.slice(0, 300));
  process.exitCode = 1;
});

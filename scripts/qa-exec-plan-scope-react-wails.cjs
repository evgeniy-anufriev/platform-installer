// Selected-source acceptance through real React controls and Wails Go bindings.
// The native folder picker alone is replaced with an exact known QA root.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../frontend/node_modules/playwright-core');

const root = process.env.PLATFORM_QA_PROJECT_ROOT;
const source = process.env.PLATFORM_QA_SOURCE_DEPLOYMENT || 'clickhouse-qa-ha3x3';
const passwordFile = process.env.PLATFORM_QA_CLICKHOUSE_PASSWORD_FILE;
const pkiPasswordFile = process.env.PLATFORM_QA_PKI_PASSWORD_FILE;
const outputPasswordFile = process.env.PLATFORM_QA_OUTPUT_PASSWORD_FILE;
const sshKey = process.env.PLATFORM_QA_SSH_KEY;
const startRequested = process.env.PLATFORM_QA_START === 'yes';
const endpoint = process.env.PLATFORM_QA_WAILS_URL || 'http://127.0.0.1:34115';
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

if (!root || !path.isAbsolute(root)) throw new Error('QA_PROJECT_ROOT_REQUIRED');
if (!passwordFile || !path.isAbsolute(passwordFile)) throw new Error('QA_CLICKHOUSE_PASSWORD_PATH_REQUIRED');
if (startRequested && (!pkiPasswordFile || !sshKey || !path.isAbsolute(pkiPasswordFile) || !path.isAbsolute(sshKey))) throw new Error('QA_START_INPUT_PATH_REQUIRED');

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  const errors = [];
  const wailsDevBootstrapWarnings = [];
  page.on('pageerror', (error) => {
    const detail = (error.stack || error.message).slice(0, 800);
    if (error.message === "Cannot read properties of null (reading 'nodes')" &&
        detail.includes('/wails/ipc.js:')) {
      wailsDevBootstrapWarnings.push(detail);
    } else {
      errors.push(detail);
    }
  });
  try {
    await page.goto(endpoint, { timeout: 30000 });
    await page.waitForFunction(() => typeof window.go?.main?.App?.OpenProject === 'function');
    await page.evaluate((projectRoot) => {
      const app = window.go.main.App;
      window.__qaCalls = [];
      for (const name of ['CloseProject', 'OpenProject', 'SetSessionCredential', 'ClearSessionCredential', 'SetPKIStorePassword']) {
        const method = app[name]?.bind(app);
        if (method) app[name] = async (...args) => {
          window.__qaCalls.push(name);
          try {
            const result = await method(...args);
            if (name === 'SetSessionCredential') window.__qaCalls.push('SetSessionCredential:' + result?.status);
            return result;
          } catch (error) {
            window.__qaCalls.push(name + ':ERROR:' + String(error).slice(0, 80));
            throw error;
          }
        };
      }
      const open = app.OpenProject.bind(app);
      app.ChooseProject = async () => {
        await app.CloseProject();
        const result = await open(projectRoot);
        window.__qaOpen = { status: result.status, error: result.error?.code, catalog: result.catalog?.status, classification: result.classification, managed: !!result.managed };
        return result;
      };
    }, root.replaceAll('\\', '/'));
    await page.getByRole('button', { name: 'Открыть проект' }).click();
    await page.locator('header strong').getByText(path.basename(root)).waitFor({ timeout: 30000 });
    const opened = await page.evaluate(() => window.__qaOpen);
    if (opened.status !== 'OPEN') throw new Error(`QA_OPEN_FAILED:${opened.error || opened.status}`);
    console.log('QA_OPEN=PASS');

    await page.locator('aside nav').getByRole('button', { name: 'Серверы', exact: true }).click();
    await page.getByRole('button', { name: 'Проверить узел' }).click();
    await page.waitForFunction(async () => (await window.go.main.App.GetExecutionNodeContext()).status === 'READY', undefined, { timeout: 90000 });
    console.log('QA_NODE=READY');

    const password = fs.readFileSync(passwordFile, 'utf8').replace(/\r?\n$/, '');
    if (!password) throw new Error('QA_CLICKHOUSE_PASSWORD_EMPTY');
    await page.locator('aside nav').getByRole('button', { name: 'Сервисы', exact: true }).click();
    await page.locator('.topology-row').filter({ hasText: source }).click();
    await page.locator('.service-secrets-action').getByRole('button', { name: 'Секреты' }).click();
    const secretDialog = page.locator('dialog.runtime-secret-dialog[open]');
    await secretDialog.waitFor({ timeout: 15000 }).catch(async (error) => {
      console.log('QA_SECRET_DIALOG_DIAGNOSTIC=' + JSON.stringify({
        opened: await page.evaluate(() => window.__qaOpen),
        pending: await page.evaluate((deployment) => window.go.main.App.GetPendingRuntimeSecretDescriptors(deployment).then((result) => ({ status: result.status, code: result.error?.code })), source),
        dialogs: await page.locator('dialog.runtime-secret-dialog').count(),
        openDialogs: await secretDialog.count(),
        alerts: await page.locator('[role=alert]').allTextContents(),
      }));
      throw error;
    });
    await secretDialog.locator('input[type=password]').first().fill(password);
    await secretDialog.getByRole('button', { name: 'Сохранить в сессии' }).click();
    await secretDialog.waitFor({ state: 'hidden', timeout: 15000 });
    console.log('QA_CLICKHOUSE_SECRET=SESSION_ONLY');

    await page.locator('aside nav').getByRole('button', { name: 'Установка', exact: true }).click();
    await page.getByRole('button', { name: 'План', exact: true }).click();
    await page.getByLabel('Область плана').selectOption(source);
    await page.getByRole('button', { name: 'Сформировать свежий план' }).click();
    await page.getByText('Свежий DeploymentPlan').waitFor({ timeout: 600000 });
    const state = await page.evaluate(() => window.go.main.App.GetInstallationState());
    const planID = state.plan?.planId;
    if (!planID) throw new Error('QA_PLAN_MISSING');
    const operation = await page.evaluate((id) => window.go.main.App.GetInstallationPlan(id), planID);
    const plan = operation.plan;
    if (operation.status !== 'PLAN_REVIEW' || plan?.status !== 'EXECUTABLE' || plan.selectedSourceDeployment !== source) {
      throw new Error(`QA_SELECTED_PLAN_INVALID:${operation.status}:${operation.error?.code || plan?.status}`);
    }
    if (!plan.targetScope?.providerEffects?.length) throw new Error('QA_PROVIDER_EFFECTS_MISSING');
    const displayed = await page.getByRole('region', { name: 'Затронутые provider deployments' }).innerText();
    for (const effect of plan.targetScope.providerEffects) {
      if (!displayed.includes(effect.providerDeployment) || !displayed.includes(effect.providerType) ||
          !displayed.includes(effect.mode) || !displayed.includes(effect.hosts.join(', ')) ||
          !displayed.includes(`перезапись: ${effect.overwrite ? 'да' : 'нет'}`)) {
        throw new Error('QA_PROVIDER_EFFECT_NOT_DISPLAYED');
      }
    }
    console.log(`QA_PLAN=${planID} REVISION=${plan.projectRevision} SOURCE=${source} EFFECTS=${JSON.stringify(plan.targetScope.providerEffects)}`);
    if (!startRequested) {
      console.log('QA_START=HELD');
      console.log('QA_WAILS_DEV_BOOTSTRAP_WARNINGS=' + wailsDevBootstrapWarnings.length);
      if (errors.length) throw new Error('QA_RENDER_ERRORS:' + errors.join('|'));
      return;
    }

    if (plan.secretOutputEncryptionRequired && !plan.secretOutputEncryptionPasswordPresent) {
      if (!outputPasswordFile || !path.isAbsolute(outputPasswordFile)) throw new Error('QA_OUTPUT_PASSWORD_PATH_REQUIRED');
      const outputPassword = fs.readFileSync(outputPasswordFile, 'utf8').replace(/\r?\n$/, '');
      if (!outputPassword) throw new Error('QA_OUTPUT_PASSWORD_EMPTY');
      const outputSetup = page.locator('article.secret-output-setup');
      await outputSetup.getByLabel('Пароль шифрования', { exact: true }).fill(outputPassword);
      await outputSetup.getByLabel('Повторите пароль').fill(outputPassword);
      await outputSetup.getByRole('button', { name: 'Сохранить пароль в сеансе' }).click();
      await outputSetup.getByText('Пароль шифрования задан для текущего сеанса.').waitFor({ timeout: 15000 });
      console.log('QA_OUTPUT_PASSWORD=SESSION_ONLY');
    }

    const approval = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'Подтверждение' }) });
    const checks = approval.locator('input[type=checkbox]');
    for (let index = 0, count = await checks.count(); index < count; index++) await checks.nth(index).check();
    await approval.getByRole('button', { name: 'Одобрить план' }).click();
    await page.getByRole('heading', { name: 'План одобрен' }).waitFor({ timeout: 15000 });
    console.log('QA_APPROVAL=PASS');

    await page.locator('aside nav').getByRole('button', { name: 'Серверы', exact: true }).click();
    const credentials = page.locator('.session-credentials');
    await credentials.getByLabel('Технический пользователь').fill('platform-automation');
    await credentials.getByLabel('SSH-аутентификация').selectOption('SSH_PRIVATE_KEY');
    await credentials.getByLabel('Абсолютный путь к приватному ключу').fill(sshKey);
    await credentials.getByRole('button', { name: 'Сохранить в сеансе' }).click();
    await page.waitForFunction(async () => (await window.go.main.App.GetSessionCredentialStatus()).status === 'PRESENT', undefined, { timeout: 15000 });
    console.log('QA_CREDENTIAL_AFTER_SAVE=' + (await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus())).status);
    console.log('QA_CREDENTIAL_UI_ERRORS=' + JSON.stringify(await credentials.locator('[role=alert]').allTextContents()));
    console.log('QA_CALLS=' + JSON.stringify(await page.evaluate(() => window.__qaCalls)));
    await page.locator('aside nav').getByRole('button', { name: 'Установка', exact: true }).click();
    console.log('QA_CREDENTIAL_AFTER_NAV=' + (await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus())).status);
    await page.getByRole('button', { name: 'План', exact: true }).click();
    const start = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'План одобрен' }) });
    if (plan.pkiStorePasswordRequired) {
      const pkiPassword = fs.readFileSync(pkiPasswordFile, 'utf8').replace(/\r?\n$/, '');
      if (!pkiPassword) throw new Error('QA_PKI_PASSWORD_EMPTY');
      await start.getByLabel('Пароль хранилища PKI').fill(pkiPassword);
      await start.getByRole('button', { name: 'Добавить пароль в сеанс' }).click();
    }
    const readiness = await page.evaluate((id) => window.go.main.App.GetInstallationPlan(id), planID);
    const credentialReadiness = await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus());
    console.log(`QA_START_READINESS=${JSON.stringify({ status: readiness.status, outputRequired: readiness.plan?.secretOutputEncryptionRequired, outputPresent: readiness.plan?.secretOutputEncryptionPasswordPresent, pkiRequired: readiness.plan?.pkiStorePasswordRequired, credentialStatus: credentialReadiness.status, pkiStatus: credentialReadiness.pkiStorePasswordStatus, uiError: await start.locator('[role=alert]').allTextContents(), startDisabled: await start.getByRole('button', { name: 'Начать выполнение' }).isDisabled() })}`);
    await page.evaluate(() => {
      const app = window.go.main.App;
      const original = app.StartApprovedInstallation.bind(app);
      app.StartApprovedInstallation = async (id) => {
        const result = await original(id);
        window.__qaStarted = { status: result.status, runId: result.run?.runId, error: result.error?.code };
        return result;
      };
    });
    await start.getByRole('button', { name: 'Начать выполнение' }).click();
    await page.waitForFunction(() => window.__qaStarted !== undefined, undefined, { timeout: 120000 });
    const started = await page.evaluate(() => window.__qaStarted);
    console.log(`QA_START=${JSON.stringify(started)}`);
    if (started.status !== 'STARTED' || !started.runId) throw new Error('QA_START_BLOCKED');
    const deadline = Date.now() + 60 * 60 * 1000;
    while (Date.now() < deadline) {
      const current = await page.evaluate((id) => window.go.main.App.GetInstallationRun(id), started.runId);
      if (current.status === 'READY' && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(current.run?.state)) {
        console.log(`QA_TERMINAL=${current.run.state} RUN=${started.runId} SEQUENCE=${current.run.sequence}`);
        if (current.run.state !== 'SUCCEEDED') throw new Error('QA_RUN_NOT_SUCCEEDED');
        break;
      }
      await pause(30000);
    }
    if (Date.now() >= deadline) throw new Error('QA_RUN_TIMEOUT');
    console.log('QA_WAILS_DEV_BOOTSTRAP_WARNINGS=' + wailsDevBootstrapWarnings.length);
    if (errors.length) throw new Error('QA_RENDER_ERRORS:' + errors.join('|'));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error('QA_EXEC_PLAN_SCOPE_FAILED:' + error.message.slice(0, 300));
  process.exitCode = 1;
});

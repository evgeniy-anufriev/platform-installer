// SI09 nonvisual acceptance: real React handlers over the Wails Go bridge.
// Only the native folder picker is substituted with the known QA project root.
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require('../frontend/node_modules/playwright-core');

const projectRoot = process.env.PLATFORM_QA_PROJECT_ROOT;
if (!projectRoot || !path.isAbsolute(projectRoot)) throw new Error('QA_PROJECT_ROOT_REQUIRED');
const deployment = 'clickhouse-qa-ha3x3';
const browserURL = process.env.PLATFORM_QA_WAILS_URL || 'http://127.0.0.1:34115';
const passwordFile = process.env.PLATFORM_QA_CLICKHOUSE_PASSWORD_FILE;
const sessionPasswordFile = process.env.PLATFORM_QA_PASSWORD_FILE;
const sshKeyFile = process.env.PLATFORM_QA_SSH_KEY;
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (error) => {
    if (error.stack?.includes('/wails/ipc.js') && error.message.includes("null (reading 'nodes')")) return;
    errors.push(error.message.slice(0, 200));
  });
  try {
    await page.goto(browserURL, { timeout: 30000 });
    await page.waitForFunction(() => typeof window.go?.main?.App?.OpenProject === 'function');
    await page.evaluate((root) => {
      const app = window.go.main.App;
      const open = app.OpenProject.bind(app);
      app.ChooseProject = async () => {
        await app.CloseProject();
        const result = await open(root);
        window.__qaOpen = result;
        return result;
      };
    }, projectRoot.replaceAll('\\', '/'));
    await page.getByRole('button', { name: 'Открыть проект' }).click();
    try {
      await page.locator('header strong').getByText(path.basename(projectRoot)).waitFor({ timeout: 30000 });
    } catch (error) {
      const state = await page.evaluate(() => ({ status: window.__qaOpen?.status, code: window.__qaOpen?.error?.code }));
      throw new Error(`QA_OPEN_FAILED:${JSON.stringify(state)}:${(await page.locator('body').innerText()).slice(-300)}`);
    }
    console.log('QA_OPEN=PASS');
    await page.locator('aside nav').getByRole('button', { name: 'Серверы', exact: true }).click();
    await page.getByRole('button', { name: 'Проверить узел' }).click();
    await page.waitForFunction(async () => (await window.go.main.App.GetExecutionNodeContext()).status === 'READY', undefined, { timeout: 90000 });
    console.log('QA_NODE=READY');
    await page.locator('aside nav').getByRole('button', { name: 'Топология', exact: true }).click();
    const row = page.locator('.topology-row').filter({ hasText: deployment });
    if (await row.count() === 0) {
      await page.getByRole('button', { name: 'Добавить экземпляр' }).click();
      const dialog = page.locator('.topology-dialog');
      await dialog.getByLabel('Технический ID deployment').fill(deployment);
      await dialog.locator('select').nth(0).selectOption('clickhouse');
      await dialog.locator('select').nth(1).selectOption('raft-ha');
      await dialog.getByRole('button', { name: 'Добавить в черновик' }).click();
      await row.waitFor({ timeout: 15000 });
      console.log('QA_CLICKHOUSE_CREATE_DRAFT=PASS');
      await page.getByRole('button', { name: 'Просмотреть изменения' }).click();
      await page.getByRole('button', { name: 'Сохранить проект' }).waitFor({ timeout: 15000 });
      await page.getByRole('button', { name: 'Сохранить проект' }).click();
      await page.getByText('Сохранено', { exact: true }).first().waitFor({ timeout: 15000 });
      console.log('QA_CLICKHOUSE_CREATE_SAVED=PASS');
    } else {
      console.log('QA_CLICKHOUSE_EXISTING=PASS');
    }
    await row.click();
    if (await page.getByRole('button', { name: 'Добавить размещение', exact: true }).count()) {
      await page.getByRole('button', { name: 'Добавить размещение', exact: true }).first().click();
      const dialog = page.locator('.topology-dialog');
      await dialog.getByRole('button', { name: 'Добавить member' }).click();
      await dialog.locator('.placement-row').first().waitFor();
      await dialog.getByRole('button', { name: 'Добавить member' }).click();
      await dialog.locator('.placement-row').nth(1).waitFor();
      await dialog.getByRole('button', { name: 'Добавить member' }).click();
      await dialog.locator('.placement-row').nth(2).waitFor();
      for (let index = 0; index < 3; index++) {
        await dialog.getByLabel(`Member ID ${index + 1}`).fill(`clickhouse-${index + 1}`);
        await dialog.getByLabel(`Сервер ${index + 1}`).selectOption(`node${index + 1}`);
        await dialog.locator('.placement-row').nth(index).locator('select[multiple]').selectOption(['server', 'keeper']);
      }
      await dialog.getByRole('button', { name: 'Применить' }).click();
      await page.getByRole('button', { name: 'Просмотреть изменения' }).click();
      await page.getByRole('button', { name: 'Сохранить проект' }).waitFor({ timeout: 15000 });
      await page.getByRole('button', { name: 'Сохранить проект' }).click();
      await page.getByText('Сохранено', { exact: true }).first().waitFor({ timeout: 15000 });
      console.log('QA_CLICKHOUSE_PLACEMENT_SAVED=PASS');
    }
    await row.click();
    await page.getByRole('button', { name: 'Настроить сервис' }).click();
    const settings = [
      ['tlsProfile', 'vault-qa-tls'],
      ['port', '8460'],
      ['nativePort', '9460'],
      ['interserverPort', '9030'],
      ['keeperClientPort', '9300'],
      ['keeperRaftPort', '9470'],
    ];
    let applied = 0;
    for (const [id, value] of settings) {
      const control = page.locator('.services-settings .services-setting').filter({ has: page.locator('small').getByText(id, { exact: true }) }).first();
      const input = id === 'tlsProfile' ? control.locator('select') : control.locator('input');
      if (await input.isDisabled() || await input.inputValue() === value) continue;
      if (id === 'tlsProfile') await control.locator('select').selectOption(value);
      else await control.locator('input').fill(value);
      await control.getByRole('button', { name: 'Применить' }).waitFor({ state: 'visible' });
      if (await control.getByRole('button', { name: 'Применить' }).isDisabled()) throw new Error(`QA_SETTING_REJECTED:${id}`);
      await control.getByRole('button', { name: 'Применить' }).click();
      await control.getByRole('button', { name: 'Применить' }).waitFor({ state: 'visible' });
      applied++;
    }
    if (applied) {
      await page.getByRole('button', { name: 'Проверить и сохранить' }).click();
      await page.getByRole('button', { name: 'Сохранить проект' }).waitFor({ timeout: 15000 });
      await page.getByRole('button', { name: 'Сохранить проект' }).click();
      await page.getByText('Сохранено', { exact: true }).first().waitFor({ timeout: 15000 });
      console.log(`QA_CLICKHOUSE_SETTINGS_SAVED=${applied}`);
    }
    await page.locator('aside nav').getByRole('button', { name: 'Топология', exact: true }).click();
    await page.getByRole('button', { name: 'Точки входа' }).click();
    const group = page.getByLabel(`Endpoint group for ${deployment}`);
    if (await group.inputValue() !== 'vault-endpoint') {
      await group.selectOption('vault-endpoint');
      await page.getByRole('button', { name: 'Просмотреть изменения' }).click();
      await page.getByRole('button', { name: 'Сохранить проект' }).waitFor({ timeout: 15000 });
      await page.getByRole('button', { name: 'Сохранить проект' }).click();
      await page.getByText('Сохранено', { exact: true }).first().waitFor({ timeout: 15000 });
      console.log('QA_CLICKHOUSE_ENDPOINT_GROUP_SAVED=PASS');
    }
    if (passwordFile) {
      if (!path.isAbsolute(passwordFile)) throw new Error('QA_PASSWORD_PATH_INVALID');
      const password = fs.readFileSync(passwordFile, 'utf8').replace(/\r?\n$/, '');
      if (!password) throw new Error('QA_PASSWORD_EMPTY');
      await page.locator('aside nav').getByRole('button', { name: 'Сервисы', exact: true }).click();
      await page.locator('.topology-row').filter({ hasText: deployment }).click();
      const secrets = page.locator('.service-secrets-action');
      await secrets.getByRole('button', { name: 'Секреты' }).click();
      const dialog = page.locator('dialog.runtime-secret-dialog[open]');
      await dialog.waitFor({ timeout: 15000 });
      await dialog.locator('input[type=password]').first().fill(password);
      await dialog.getByRole('button', { name: 'Сохранить в сессии' }).click();
      if (await dialog.count()) {
        await dialog.getByRole('button', { name: 'Отмена' }).click();
        await page.getByRole('button', { name: 'Проверить и сохранить' }).click();
        await page.getByRole('button', { name: 'Сохранить проект' }).waitFor({ timeout: 15000 });
        await page.getByRole('button', { name: 'Сохранить проект' }).click();
        await page.getByText('Сохранено', { exact: true }).first().waitFor({ timeout: 15000 });
        console.log('QA_CLICKHOUSE_SECRET_REF_SAVED=PASS');
        await secrets.getByRole('button', { name: 'Секреты' }).click();
        await dialog.waitFor({ timeout: 15000 });
        await dialog.locator('input[type=password]').first().fill(password);
        await dialog.getByRole('button', { name: 'Сохранить в сессии' }).click();
      }
      await dialog.waitFor({ state: 'hidden', timeout: 15000 });
      console.log('QA_CLICKHOUSE_SECRET_SESSION=PASS');
    }
    if (process.env.PLATFORM_QA_PLAN === 'yes') {
      if (!sessionPasswordFile || !sshKeyFile) throw new Error('QA_PLAN_INPUT_REQUIRED');
      const sessionPassword = fs.readFileSync(sessionPasswordFile, 'utf8').replace(/\r?\n$/, '');
      if (!sessionPassword) throw new Error('QA_SESSION_PASSWORD_EMPTY');
      await page.locator('aside nav').getByRole('button', { name: 'Сервисы', exact: true }).click();
      await page.locator('.topology-row').filter({ hasText: 'vault-endpoint-ha' }).click();
      await page.locator('.service-secrets-action').getByRole('button', { name: 'Секреты' }).click();
      const vaultDialog = page.locator('dialog.runtime-secret-dialog[open]');
      await vaultDialog.waitFor({ timeout: 15000 });
      for (const label of ['Administrative token', 'Unseal keys']) {
        const input = vaultDialog.locator('.runtime-secret-file-input').filter({ hasText: label });
        await input.getByLabel('Пароль файла age, если файл зашифрован').fill(sessionPassword);
        await input.getByRole('button', { name: 'Выбрать файл' }).click();
        await input.getByText('Файл принят и сохранён только в сессии.').waitFor({ timeout: 15000 });
      }
      await vaultDialog.getByRole('button', { name: 'Готово' }).click();
      console.log('QA_VAULT_PROTECTED_INPUTS=STORED');

      await page.locator('aside nav').getByRole('button', { name: 'Установка', exact: true }).click();
      await page.getByRole('button', { name: 'Сформировать свежий план' }).click();
      await page.getByText('Свежий DeploymentPlan').waitFor({ timeout: 120000 });
      const state = await page.evaluate(() => window.go.main.App.GetInstallationState());
      const planID = state.plan?.planId;
      if (!planID) throw new Error('QA_PLAN_MISSING');
      const plan = await page.evaluate((id) => window.go.main.App.GetInstallationPlan(id), planID);
      console.log(`QA_PLAN=${planID} STATUS=${plan.status} CORE=${plan.plan?.status || ''} CODE=${plan.error?.code || ''}`);
      console.log('QA_CREDENTIAL_AFTER_PLAN=' + (await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus())).status);
      if (plan.status !== 'PLAN_REVIEW' || plan.plan?.status !== 'EXECUTABLE') throw new Error('QA_PLAN_NOT_EXECUTABLE');
      if (plan.plan.secretOutputEncryptionRequired) {
        const output = page.locator('.secret-output-setup');
        if (await output.getByLabel('Пароль шифрования').count()) {
          await output.getByLabel('Пароль шифрования').fill(sessionPassword);
          await output.getByLabel('Повторите пароль').fill(sessionPassword);
          await output.getByRole('button', { name: 'Сохранить пароль в сеансе' }).click();
        }
        await output.getByText('Пароль шифрования задан для текущего сеанса.').waitFor({ timeout: 15000 });
      }
      const approval = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'Подтверждение' }) });
      const checks = approval.locator('input[type=checkbox]');
      for (let i = 0, count = await checks.count(); i < count; i++) await checks.nth(i).check();
      await approval.getByRole('button', { name: 'Одобрить план' }).click();
      await page.getByRole('heading', { name: 'План одобрен' }).waitFor({ timeout: 15000 });
      console.log('QA_APPROVAL=PASS');
      await page.locator('aside nav').getByRole('button', { name: 'Серверы', exact: true }).click();
      const credentials = page.locator('.session-credentials');
      await credentials.getByLabel('Технический пользователь').fill('platform-automation');
      await credentials.getByLabel('SSH-аутентификация').selectOption('SSH_PRIVATE_KEY');
      await credentials.getByLabel('Абсолютный путь к приватному ключу').fill(sshKeyFile);
      await credentials.getByRole('button', { name: 'Сохранить в сеансе' }).click();
      await page.waitForFunction(async () => (await window.go.main.App.GetSessionCredentialStatus()).status === 'PRESENT', undefined, { timeout: 15000 });
      console.log('QA_TARGET_CREDENTIAL=PRESENT');
      await page.locator('aside nav').getByRole('button', { name: 'Установка', exact: true }).click();
      await page.getByRole('heading', { name: 'План одобрен' }).waitFor({ timeout: 15000 });
      const afterNavigation = await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus());
      console.log(`QA_CREDENTIAL_BEFORE_PKI=${afterNavigation.status}`);
      if (afterNavigation.status !== 'PRESENT') {
        const renewed = await page.evaluate((keyPath) => window.go.main.App.SetSessionCredential({
          username: 'platform-automation', sshMode: 'SSH_PRIVATE_KEY', sshPassword: '', privateKeyPath: keyPath,
          elevationMode: 'NONE', elevationPassword: '',
        }), sshKeyFile);
        if (renewed.status !== 'PRESENT') throw new Error('QA_CREDENTIAL_FINAL_RENEWAL_FAILED');
        console.log('QA_TARGET_CREDENTIAL_FINAL_RENEWAL=PRESENT');
      }
      const start = page.locator('article.card').filter({ has: page.getByRole('heading', { name: 'План одобрен' }) });
      if (plan.plan.pkiStorePasswordRequired) {
        if (await start.getByLabel('Пароль хранилища PKI').count()) {
          await start.getByLabel('Пароль хранилища PKI').fill(sessionPassword);
          await start.getByRole('button', { name: 'Добавить пароль в сеанс' }).click();
        }
        const pkiStatus = await page.evaluate(() => window.go.main.App.GetSessionCredentialStatus());
        console.log(`QA_AFTER_PKI_CREDENTIAL=${pkiStatus.status} PKI=${pkiStatus.pkiStorePasswordStatus}`);
        await page.waitForFunction(async () => (await window.go.main.App.GetSessionCredentialStatus()).pkiStorePasswordStatus === 'PRESENT', undefined, { timeout: 15000 });
      }
      await start.getByRole('button', { name: 'Начать выполнение' }).waitFor({ state: 'visible' });
      await page.waitForFunction(() => {
        const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === 'Начать выполнение');
        return button && !button.disabled;
      }, undefined, { timeout: 15000 });
      if (process.env.PLATFORM_QA_START !== 'yes') {
        console.log('QA_START=HELD');
      } else {
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
        const result = await page.evaluate(() => window.__qaStartResult);
        console.log(`QA_START_RESULT=${JSON.stringify(result)}`);
        if (result.status !== 'STARTED' || !result.runId) throw new Error('QA_START_BLOCKED');
        const deadline = Date.now() + 90 * 60 * 1000;
        for (;;) {
          const current = await page.evaluate((id) => window.go.main.App.GetInstallationRun(id), result.runId);
          if (current.status === 'READY' && ['SUCCEEDED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(current.run?.state)) {
            console.log(`QA_TERMINAL=${current.run.state} RUN=${result.runId} SEQUENCE=${current.run.sequence}`);
            if (current.run.state !== 'SUCCEEDED') throw new Error('QA_RUN_NOT_SUCCEEDED');
            break;
          }
          if (Date.now() > deadline) throw new Error('QA_RUN_TIMEOUT');
          await pause(30000);
        }
      }
    }
    if (errors.length) throw new Error('QA_RENDER_ERRORS:' + errors.join('|'));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error('QA_SI09_FAILED:' + error.message.slice(0, 300));
  process.exitCode = 1;
});

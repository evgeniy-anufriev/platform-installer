// Disposable, nonvisual acceptance through React handlers and real Wails Go.
// Only the native folder picker is replaced with the exact QA project root.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('../frontend/node_modules/playwright-core');

const projectRoot = process.env.PLATFORM_QA_REBIND_PROJECT_ROOT;
const endpoint = process.env.PLATFORM_QA_WAILS_URL || 'http://127.0.0.1:34115';
if (!projectRoot || !path.isAbsolute(projectRoot)) throw new Error('QA_PROJECT_ROOT_REQUIRED');
const url = new URL(endpoint);
if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password) throw new Error('QA_WAILS_LOOPBACK_REQUIRED');
const projectFile = path.join(projectRoot, 'project.yml');
const manifestFile = path.join(projectRoot, 'bundle', 'manifest.yaml');
const inventoryFile = path.join(projectRoot, 'inventory', 'hosts.yml');
const before = fs.readFileSync(projectFile, 'utf8');
const inventoryBefore = fs.readFileSync(inventoryFile, 'utf8');
const candidate = `sha256:${crypto.createHash('sha256').update(fs.readFileSync(manifestFile)).digest('hex')}`;
const oldDigest = before.split('artifactLock:')[1]?.match(/digest: (sha256:[0-9a-f]{64})/)?.[1];
if (!oldDigest) throw new Error('QA_OLD_DIGEST_UNAVAILABLE');
if (before.includes(candidate)) throw new Error('QA_CANDIDATE_ALREADY_BOUND');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(endpoint, { timeout: 30000 });
    await page.waitForFunction(() => typeof window.go?.main?.App?.OpenProject === 'function');
    await page.evaluate((root) => {
      const app = window.go.main.App;
      const open = app.OpenProject.bind(app);
      app.ChooseProject = async () => {
        const result = await open(root);
        window.__qaRebindOpen = { status: result.status, code: result.error?.code, catalogStatus: result.catalog?.status };
        return result;
      };
    }, projectRoot.replaceAll('\\', '/'));
    await page.getByRole('button', { name: 'Открыть папку проекта' }).click();
    try {
      await page.getByRole('heading', { name: 'Набор установки' }).waitFor({ timeout: 10000 });
    } catch (error) {
      const state = await page.evaluate(() => window.__qaRebindOpen);
      throw new Error(`QA_OPEN_FAILED:${JSON.stringify(state)}:${error.message}`);
    }
    await page.getByText(candidate, { exact: true }).waitFor();
    if (fs.readFileSync(projectFile, 'utf8') !== before) throw new Error('QA_PREVIEW_MUTATED_PROJECT');
    await page.getByRole('button', { name: 'Привязать' }).click();
    for (let i = 0; i < 60 && !fs.readFileSync(projectFile, 'utf8').includes(candidate); i++) {
      await page.waitForTimeout(250);
    }
    const after = fs.readFileSync(projectFile, 'utf8');
    if (!after.includes(candidate)) throw new Error('QA_BIND_DID_NOT_UPDATE_PROJECT');
    if (after !== before.replace(oldDigest, candidate)) throw new Error('QA_NON_LOCK_PROJECT_CHANGE');
    if (fs.readFileSync(inventoryFile, 'utf8') !== inventoryBefore) throw new Error('QA_INVENTORY_CHANGED');
    console.log(JSON.stringify({ flow: 'React→Wails→Go', status: 'PASS', candidateDigest: candidate, projectChanged: before !== after }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(`QA_RUNTIME_REBIND_FAILED:${error.message}`);
  process.exitCode = 1;
});

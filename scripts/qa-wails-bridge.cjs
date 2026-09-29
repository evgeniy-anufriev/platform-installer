// Read-only preflight for the standard, loopback-only Wails development bridge.
// Does not substitute frontend mocks or launch an installation.
const { chromium } = require('../frontend/node_modules/playwright-core');

(async () => {
  const endpoint = process.env.PLATFORM_QA_WAILS_URL || 'http://127.0.0.1:34115';
  const url = new URL(endpoint);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password) {
    throw new Error('QA_WAILS_LOOPBACK_REQUIRED');
  }
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(endpoint, { timeout: 30000 });
    await page.waitForFunction(() => typeof window.go?.main?.App?.GetApplicationConfig === 'function');
    const status = await page.evaluate(async () => {
      const app = window.go.main.App;
      await app.GetApplicationConfig();
      const node = await app.GetExecutionNodeContext();
      return { bridge: 'REAL_WAILS', node: node.status };
    });
    console.log(JSON.stringify(status));
  } finally {
    await browser.close();
  }
})().catch(() => {
  console.error('QA_WAILS_BRIDGE_PREFLIGHT_FAILED');
  process.exitCode = 1;
});

// B4 nonvisual React handlers -> real Wails bindings. No target operation.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("../frontend/node_modules/playwright-core");
const endpoint = process.env.PLATFORM_QA_WAILS_URL || "http://127.0.0.1:34115";
const root = process.env.PLATFORM_QA_B4_PROJECT_ROOT;
const evidence = process.env.PLATFORM_QA_B4_EVIDENCE;
const url = new URL(endpoint);
if (
  url.protocol !== "http:" ||
  url.hostname !== "127.0.0.1" ||
  url.username ||
  url.password
)
  throw new Error("QA_LOOPBACK_REQUIRED");
if (
  !root ||
  !path.isAbsolute(root) ||
  fs.existsSync(root) ||
  !evidence ||
  !path.isAbsolute(evidence)
)
  throw new Error("QA_FRESH_PROJECT_AND_EVIDENCE_REQUIRED");
(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(endpoint);
    await page.waitForFunction(
      () =>
        typeof window.go?.main?.App?.CreateInstallationPlanForMode ===
        "function",
    );
    await page.evaluate(() => {
      window.__b4Calls = [];
      const app = window.go.main.App;
      const build = app.CreateInstallationPlanForMode.bind(app);
      app.CreateInstallationPlanForMode = async (request) => {
        const result = await build(request);
        window.__b4Calls.push({
          mode: request.executionMode,
          status: result.status,
          code: result.error?.code,
        });
        return result;
      };
    });
    await page
      .getByRole("button", { name: "Создать проект", exact: true })
      .first()
      .click();
    await page
      .getByLabel("Название проекта", { exact: true })
      .fill(path.basename(root));
    await page.getByLabel("Новая папка проекта", { exact: true }).fill(root);
    await page
      .locator("form.dialog")
      .getByRole("button", { name: "Создать проект", exact: true })
      .click();
    await page
      .locator("header strong")
      .getByText(path.basename(root), { exact: true })
      .waitFor({ timeout: 30000 });
    await page
      .locator("aside nav")
      .getByRole("button", { name: "Установка", exact: true })
      .click();
    await page.getByRole("tab", { name: "План", exact: true }).click();
    if (
      (await page
        .getByRole("checkbox", { name: "Устанавливать инфраструктуру" })
        .count()) !== 0
    )
      throw new Error("QA_SCOPE_CONTROL_BEFORE_PLAN");
    await page
      .getByRole("button", { name: "Сформировать свежий план", exact: true })
      .click();
    await page.waitForFunction(() => window.__b4Calls.length === 1);
    const reactCalls = await page.evaluate(() => window.__b4Calls.slice());
    if (
      reactCalls[0].mode !== "FULL_PROJECT" ||
      reactCalls[0].code !== "EXECUTION_NODE_READY_REQUIRED"
    )
      throw new Error("QA_PREREQUISITE_MISMATCH");
    await page.screenshot({
      path: path.join(evidence, "initial-plan-prerequisite.png"),
      fullPage: true,
    });
    // Supplementary direct binding refusal: the new services control is only
    // available after a real Core plan; no plan/READY state is fabricated here.
    const direct = await page.evaluate(() =>
      window.go.main.App.CreateInstallationPlanForMode({
        executionMode: "APPLICATION_LIBRARIES_ONLY",
        deploymentOrder: [],
        applicationVaultSources: {},
      }),
    );
    if (direct.error?.code !== "EXECUTION_NODE_READY_REQUIRED")
      throw new Error("QA_BINDING_PREREQUISITE_MISMATCH");
    const calls = reactCalls;
    const state = await page.evaluate(() =>
      window.go.main.App.GetInstallationState(),
    );
    const result = {
      project: { id: state.project?.id, revision: state.project?.revision },
      bridge: "REAL_WAILS",
      handlers: "REAL_REACT",
      scope: "INITIAL_PLAN_PREREQUISITE_ONLY",
      supplementaryLibraryBindingCode: direct.error?.code,
      calls,
      targetOperations: 0,
    };
    fs.writeFileSync(
      path.join(evidence, "react-wails.json"),
      JSON.stringify(result, null, 2),
    );
    console.log(JSON.stringify(result));
    await page
      .locator("aside nav")
      .getByRole("button", { name: "Проект", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Закрыть проект", exact: true })
      .click();
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error("QA_B4_REACT_WAILS_FAILED:" + e.message.slice(0, 200));
  process.exitCode = 1;
});

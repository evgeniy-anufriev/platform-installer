// Headless Wails QA only. The production native dialog and bound Go method
// remain unchanged. Never direct Computer Use input to a disabled owner window.
async function withNativeDialog(page, action) {
  const supported = await page.evaluate(() =>
    typeof window.runtime?.WindowHide === 'function' &&
    typeof window.runtime?.WindowShow === 'function');
  if (!supported) throw new Error('QA_NATIVE_DIALOG_RUNTIME_UNAVAILABLE');
  try {
    await page.evaluate(() => window.runtime.WindowHide());
    // Wails runtime window messages are asynchronous. Modal targeting still
    // requires observing an actual independently returned Computer Use Window.
    await page.waitForTimeout(1000);
    return await action();
  } finally {
    await page.evaluate(() => window.runtime.WindowShow());
  }
}
module.exports = {withNativeDialog};

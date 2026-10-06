(() => {
  const root = document.getElementById("root");
  const fail = (message) => {
    if (root) root.textContent = message;
    throw new Error("BROWSER_TAB_LEASE_UNAVAILABLE");
  };
  window.__PI_BROWSER_READY__ = (async () => {
    if (!window.__PI_BROWSER_REMOTE__) {
      const fragment = new URLSearchParams(location.hash.slice(1));
      const token = fragment.get("bootstrap");
      if (token) {
        history.replaceState(null, "", location.pathname + location.search);
        const response = await fetch("/api/bootstrap", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (!response.ok)
          fail(
            "Не удалось подключиться к приложению. Закройте вкладку и запустите его снова.",
          );
      }
    }
    let lease = sessionStorage.getItem("platform-installer-tab-lease");
    if (!lease) {
      const bytes = crypto.getRandomValues(new Uint8Array(32));
      lease = Array.from(bytes, (value) =>
        value.toString(16).padStart(2, "0"),
      ).join("");
      sessionStorage.setItem("platform-installer-tab-lease", lease);
    }
    if (!navigator.locks)
      fail(
        "Этот браузер не поддерживает безопасную работу в одной вкладке. Используйте актуальную версию Edge, Chrome или Firefox.",
      );
    let lockReady;
    let rejectLock;
    const acquired = new Promise((resolve, reject) => {
      lockReady = resolve;
      rejectLock = reject;
    });
    const holdLock = new Promise(() => {});
    void navigator.locks
      .request(
        `platform-installer-ui-${lease}`,
        { mode: "exclusive", ifAvailable: true },
        (lock) => {
          if (!lock) {
            rejectLock(new Error("BROWSER_TAB_ALREADY_ACTIVE"));
            return;
          }
          lockReady();
          return holdLock;
        },
      )
      .catch(rejectLock);
    try {
      await acquired;
    } catch {
      fail("Установщик уже открыт в другой вкладке. Продолжайте работу в ней.");
    }
    const response = await fetch("/api/lease/acquire", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leaseId: lease }),
    });
    if (response.status === 409)
      fail("Установщик уже открыт в другой вкладке. Продолжайте работу в ней.");
    if (!response.ok)
      fail("Приложение недоступно. Проверьте адрес и запущенный backend.");
    window.__PI_BROWSER_LEASE__ = lease;
  })().catch((error) => {
    if (root && !root.textContent)
      root.textContent = "Не удалось подключиться к локальному приложению.";
    throw error;
  });
})();

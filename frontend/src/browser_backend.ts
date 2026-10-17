import type { InstallationEventView, ProjectBackend } from "./backend";

declare global {
  interface Window {
    __PI_BROWSER_READY__?: Promise<void>;
    __PI_BROWSER_LEASE__?: string;
  }
}

async function browserReady(): Promise<string> {
  if (!window.__PI_BROWSER_READY__) throw new Error("BROWSER_HOST_UNAVAILABLE");
  await window.__PI_BROWSER_READY__;
  const lease = window.__PI_BROWSER_LEASE__;
  if (!lease) throw new Error("BROWSER_TAB_LEASE_UNAVAILABLE");
  return lease;
}

async function invoke<T>(operation: string, args: unknown[] = []): Promise<T> {
  const lease = await browserReady();
  const response = await fetch(`/api/call/${encodeURIComponent(operation)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Platform-UI-Lease": lease,
    },
    body: JSON.stringify(args),
  });
  const payload = (await response.json().catch(() => ({}))) as {
    result?: T;
    error?: { code?: string };
  };
  if (!response.ok)
    throw new Error(payload.error?.code || "BROWSER_API_REQUEST_FAILED");
  return payload.result as T;
}

function promptExecutionNodePath(purpose: string): string {
  return (
    window.prompt(
      `${purpose}\nУкажите абсолютный путь на Linux Execution Node.`,
    ) || ""
  ).trim();
}

function chooseBrowserFile(): Promise<File | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,.age,application/json";
    input.onchange = () => resolve(input.files?.[0] || null);
    input.addEventListener("cancel", () => resolve(null), { once: true });
    input.click();
  });
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }
  return btoa(binary);
}

async function choosePendingRuntimeSecretFile(
  input: Parameters<
    NonNullable<ProjectBackend["choosePendingDeploymentRuntimeSecretFile"]>
  >[0],
): Promise<string> {
  const file = await chooseBrowserFile();
  if (!file) return "CANCELLED";
  if (file.size === 0 || file.size > 131_072)
    throw new Error("SECRET_FILE_INVALID");
  const bytes = new Uint8Array(await file.arrayBuffer());
  try {
    return await invoke("choosePendingDeploymentRuntimeSecretFile", [
      input,
      toBase64(bytes),
    ]);
  } finally {
    bytes.fill(0);
  }
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function subscribeEvents(
  handler: (value: {
    subscriptionId?: string;
    event?: InstallationEventView;
    errorCode?: string;
  }) => void,
): () => void {
  let stopped = false;
  let lastEventID = "";
  let controller: AbortController | undefined;
  const readStream = async (response: Response) => {
    if (!response.body) throw new Error("BROWSER_EVENT_STREAM_UNAVAILABLE");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let frame: { id?: string; data: string[] } = { data: [] };
    const dispatch = () => {
      if (frame.id) lastEventID = frame.id;
      if (frame.data.length) {
        try {
          const message = JSON.parse(frame.data.join("\n")) as {
            name?: string;
            payload?: {
              subscriptionId?: string;
              event?: InstallationEventView;
              errorCode?: string;
            };
          };
          if (message.name === "installation-run-event" && message.payload)
            handler(message.payload);
        } catch {
          // Ignore malformed event frames; the next frame remains usable.
        }
      }
      frame = { data: [] };
    };
    while (!stopped) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n");
      while (boundary >= 0) {
        const line = buffer.slice(0, boundary).replace(/\r$/, "");
        buffer = buffer.slice(boundary + 1);
        if (line === "") dispatch();
        else if (!line.startsWith(":")) {
          const separator = line.indexOf(":");
          const field = separator < 0 ? line : line.slice(0, separator);
          const valueText =
            separator < 0 ? "" : line.slice(separator + 1).replace(/^ /, "");
          if (field === "id") frame.id = valueText;
          else if (field === "data") frame.data.push(valueText);
        }
        boundary = buffer.indexOf("\n");
      }
    }
    try {
      await reader.cancel();
    } catch {
      // Stream already closed.
    }
  };
  const connect = async () => {
    const lease = await browserReady();
    controller = new AbortController();
    const headers = new Headers({ "X-Platform-UI-Lease": lease });
    if (lastEventID) headers.set("Last-Event-ID", lastEventID);
    const response = await fetch("/api/events", {
      method: "GET",
      credentials: "same-origin",
      headers,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("BROWSER_EVENT_STREAM_UNAVAILABLE");
    await readStream(response);
  };
  void (async () => {
    let delay = 250;
    while (!stopped) {
      try {
        await connect();
        delay = 250;
      } catch {
        if (stopped) return;
      }
      if (!stopped) {
        await sleep(delay);
        delay = Math.min(delay * 2, 5000);
      }
    }
  })();
  return () => {
    stopped = true;
    controller?.abort();
  };
}

async function requestExit(): Promise<{
  status: "EXITING" | "EXIT_AFTER_RUN";
}> {
  const lease = await browserReady();
  const response = await fetch("/api/exit", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Platform-UI-Lease": lease },
  });
  const result = (await response.json().catch(() => ({}))) as {
    status?: "EXITING" | "EXIT_AFTER_RUN";
    error?: { code?: string };
  };
  if (!response.ok)
    throw new Error(result.error?.code || "BROWSER_EXIT_FAILED");
  return { status: result.status || "EXITING" };
}

export function startBrowserActivityKeepAlive(): () => void {
  const touchInterval = 10_000;
  let lastTouch = 0;
  let timer = 0;
  let stopped = false;
  const touch = async () => {
    timer = 0;
    if (stopped || document.visibilityState !== "visible") return;
    lastTouch = Date.now();
    const lease = await browserReady().catch(() => "");
    if (!lease || stopped) return;
    void fetch("/api/heartbeat", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Platform-UI-Lease": lease },
    }).catch(() => undefined);
  };
  const schedule = () => {
    if (stopped || timer) return;
    const delay = Math.max(0, touchInterval - (Date.now() - lastTouch));
    timer = window.setTimeout(() => void touch(), delay);
  };
  const activity = () => schedule();
  const visibility = () => {
    if (document.visibilityState === "visible") {
      lastTouch = 0;
      schedule();
    }
  };
  for (const eventName of [
    "pointerdown",
    "keydown",
    "input",
    "change",
    "focusin",
  ])
    document.addEventListener(eventName, activity, true);
  document.addEventListener("visibilitychange", visibility);
  return () => {
    stopped = true;
    if (timer) window.clearTimeout(timer);
    for (const eventName of [
      "pointerdown",
      "keydown",
      "input",
      "change",
      "focusin",
    ])
      document.removeEventListener(eventName, activity, true);
    document.removeEventListener("visibilitychange", visibility);
  };
}

export const browserBackend: ProjectBackend = {
  exitApplication: requestExit,
  subscribeInstallationRunEvents: subscribeEvents,
  chooseRuntimeBundleUpdate: () => invoke("chooseRuntimeBundleUpdate"),
  confirmRuntimeBundleUpdate: (previewId) =>
    invoke("confirmRuntimeBundleUpdate", [previewId]),
  inspectOrphanRun: () => invoke("inspectOrphanRun"),
  attachOrphanRun: (recoveryId) => invoke("attachOrphanRun", [recoveryId]),
  cancelOrphanRun: (recoveryId) => invoke("cancelOrphanRun", [recoveryId]),
  getApplicationConfig: () => invoke("getApplicationConfig"),
  chooseProject: async () => {
    const root = promptExecutionNodePath("Открыть существующий проект");
    return root ? invoke("openProject", [root]) : invoke("currentProject");
  },
  openProject: (root) => invoke("openProject", [root]),
  getCurrentProject: () => invoke("currentProject"),
  chooseProjectParent: async () =>
    promptExecutionNodePath("Папка, в которой будет создан новый проект"),
  chooseProjectExportParent: async () =>
    promptExecutionNodePath("Папка для экспорта проекта"),
  createProject: (input) => invoke("createProject", [input]),
  closeProject: () => invoke("closeProject"),
  chooseApplicationPackageDirectory: () =>
    invoke("chooseApplicationPackageDirectory", []),
  reviewApplicationPackageImport: (...args) =>
    invoke("reviewApplicationPackageImport", args),
  startEditSession: () => invoke("startEditSession"),
  appendEditCommand: (sessionID, command) =>
    invoke("appendEditCommand", [sessionID, command]),
  amendApplicationLibraryDraft: (sessionID, index, expected, replacement) =>
    invoke("amendApplicationLibraryDraft", [
      sessionID,
      index,
      expected,
      replacement,
    ]),
  amendServiceConfigurationDraft: (sessionID, index, expected, replacement) =>
    invoke("amendServiceConfigurationDraft", [
      sessionID,
      index,
      expected,
      replacement,
    ]),
  reviewEditSession: (sessionID) => invoke("reviewEditSession", [sessionID]),
  commitEditPlan: (sessionID, planID) =>
    invoke("commitEditPlan", [sessionID, planID]),
  discardEditSession: (sessionID) => invoke("discardEditSession", [sessionID]),
  getSessionCredentialStatus: () => invoke("getSessionCredentialStatus"),
  setSessionCredential: (input) => invoke("setSessionCredential", [input]),
  setPKIStorePassword: (value) => invoke("setPKIStorePassword", [value]),
  getRuntimeSecretDescriptors: () => invoke("getRuntimeSecretDescriptors"),
  setDeploymentRuntimeSecretValues: (input) =>
    invoke("setDeploymentRuntimeSecretValues", [input]),
  getPendingRuntimeSecretDescriptors: (serviceDeployment) =>
    invoke("getPendingRuntimeSecretDescriptors", [serviceDeployment]),
  setPendingDeploymentRuntimeSecretValues: (input) =>
    invoke("setPendingDeploymentRuntimeSecretValues", [input]),
  choosePendingDeploymentRuntimeSecretFile: choosePendingRuntimeSecretFile,
  listPendingSecretOutputs: (cursor = null) =>
    invoke("listPendingSecretOutputs", [cursor]),
  setSecretOutputEncryptionPassword: async (password, confirm) => {
    await invoke("setSecretOutputEncryptionPassword", [{ password, confirm }]);
  },
  deliverPendingSecretOutput: (packageId) =>
    invoke("deliverPendingSecretOutput", [{ packageId }]),
  clearSessionCredential: () => invoke("clearSessionCredential"),
  getExecutionNodeContext: () => invoke("getExecutionNodeContext"),
  getServiceConfigurationPreview: () =>
    invoke("getServiceConfigurationPreview"),
  probeExecutionNodeHostKey: () => invoke("probeExecutionNodeHostKey"),
  approveExecutionNodeHostKey: (probeId) =>
    invoke("approveExecutionNodeHostKey", [probeId]),
  declineExecutionNodeHostKey: () => invoke("declineExecutionNodeHostKey"),
  probeTargetHostKey: (hostId) => invoke("probeTargetHostKey", [hostId]),
  probeServerInformation: (hostId) =>
    invoke("probeServerInformation", [hostId]),
  checkServerInformation: (probeId) =>
    invoke("checkServerInformation", [probeId]),
  approveTargetHostKey: (probeId) => invoke("approveTargetHostKey", [probeId]),
  declineTargetHostKey: () => invoke("declineTargetHostKey"),
  getInstallationState: () => invoke("getInstallationState"),
  createInstallationPlan: (deploymentOrder) =>
    invoke("createInstallationPlan", [deploymentOrder]),
  createInstallationPlanForMode: (request) =>
    invoke("createInstallationPlanForMode", [request]),
  getInfrastructureVerification: () =>
    invoke("getInfrastructureVerification", []),
  getInstallationPlan: (planId) => invoke("getInstallationPlan", [planId]),
  approveInstallationPlan: (planId, acknowledgements) =>
    invoke("approveInstallationPlan", [planId, acknowledgements]),
  startApprovedInstallation: (planId) =>
    invoke("startApprovedInstallation", [planId]),
  getInstallationRun: (runId) => invoke("getInstallationRun", [runId]),
  subscribeInstallationRun: (runId, afterSequence) =>
    invoke("subscribeInstallationRun", [runId, afterSequence]),
  unsubscribeInstallationRun: async (subscriptionId) => {
    await invoke("unsubscribeInstallationRun", [subscriptionId]);
  },
  cancelInstallationRun: (runId) => invoke("cancelInstallationRun", [runId]),
  getEndpointPreview: () => invoke("getEndpointPreview"),
  getVerifiedPKIView: () => invoke("getVerifiedPKIView"),
  selectExecutionNode: (hostId) => invoke("selectExecutionNode", [hostId]),
  checkExecutionNode: () => invoke("checkExecutionNode"),
  planExecutionNodePreparation: () => invoke("planExecutionNodePreparation"),
  prepareExecutionNode: (planId) => invoke("prepareExecutionNode", [planId]),
  verifyProject: () => invoke("verifyProject"),
  planProjectExport: (parent, name) =>
    invoke("planProjectExport", [parent, name]),
  commitProjectExport: (planDigest) =>
    invoke("commitProjectExport", [planDigest]),
};

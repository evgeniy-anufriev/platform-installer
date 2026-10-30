import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type {
  InstallationEventView,
  OpenResult,
  ProjectBackend,
} from "./backend";

const sessionID = "0123456789abcdef0123456789abcdef";

it("passes the selected current-run Vault source through the real plan handler and clears the old plan", async () => {
  const create = vi.fn().mockResolvedValue({ status: "BLOCKED" });
  const value = api({
    createInstallationPlanForMode: create,
    getApplicationConfig: vi.fn().mockResolvedValue({
      status: "READY",
      config: {
        schemaVersion: 1,
        serverTypes: [],
        serviceExecutionPriorities: [{ serviceType: "vault", priority: 1 }],
        libraryExecutionPriorities: [{ libraryName: "szi", priority: 1 }],
      },
    }),
    getInstallationState: vi.fn().mockResolvedValue({
      status: "READY_TO_PLAN",
      project: { id: "p", hasUnsavedChanges: false },
      executionNode: { status: "READY" },
      plan: { status: "NONE" },
      prerequisites: [],
    }),
  });
  value.chooseProject.mockResolvedValue({
    ...project,
    managed: {
      ...project.managed,
      deployments: {
        "vault-main": {
          deploymentId: "vault-main",
          serviceType: "vault",
          mode: "raft-ha",
        },
      },
      applicationLibraries: { szi: { libraryRef: "szi@1.0.0" } },
    },
  } as unknown as OpenResult);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Установка" })).toHaveProperty(
      "disabled",
      false,
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Установка" }));
  await userEvent.click(await screen.findByRole("tab", { name: "План" }));
  const selector = await screen.findByRole("combobox", {
    name: "Источник токена Vault · vault-main",
  });
  expect(selector).toHaveProperty("value", "RUNTIME_INPUT");
  await userEvent.selectOptions(selector, "CURRENT_RUN_BOOTSTRAP");
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  await waitFor(() =>
    expect(create).toHaveBeenLastCalledWith(
      expect.objectContaining({
        executionMode: "FULL_PROJECT",
        applicationVaultSources: { "vault-main": "CURRENT_RUN_BOOTSTRAP" },
      }),
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Установка" })).toHaveProperty(
      "disabled",
      false,
    ),
  );
  await userEvent.click(screen.getByRole("button", { name: "Установка" }));
  await userEvent.click(await screen.findByRole("tab", { name: "План" }));
  expect(
    screen.getByRole("combobox", {
      name: "Источник токена Vault · vault-main",
    }),
  ).toHaveProperty("value", "CURRENT_RUN_BOOTSTRAP");
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  );
  expect(
    screen.queryByRole("combobox", {
      name: "Источник токена Vault · vault-main",
    }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  await waitFor(() =>
    expect(create).toHaveBeenLastCalledWith(
      expect.objectContaining({
        executionMode: "APPLICATION_LIBRARIES_ONLY",
        applicationVaultSources: {},
      }),
    ),
  );
});
const project = {
  status: "OPEN",
  root: "C:/Projects/test",
  classification: "MANAGED_PROJECT",
  managed: {
    projectRevision: "sha256:old",
    servers: {
      node1: {
        hostId: "node1",
        type: "infra",
        desiredHostname: "node1.example.internal",
        address: "192.0.2.10",
        sshPort: 2222,
      },
    },
    deployments: {
      "kafka-main": {
        deploymentId: "kafka-main",
        serviceType: "kafka",
        mode: "kraft",
      },
    },
  },
  catalog: {
    status: "READY",
    expectedBundleDigest: "sha256:bundle",
    expectedCatalogDigest: "sha256:catalog",
    services: [
      {
        id: "kafka",
        definitionVersion: "1",
        displayName: "Apache Kafka",
        category: "Messaging",
        ui: {},
        endpointConsumer: false,
        endpointProvider: false,
        modes: [
          {
            id: "kraft",
            displayName: "KRaft",
            placementKind: "MEMBER_SCOPED",
            roles: ["broker", "controller"],
            guidance: {
              minParticipants: 1,
              distinctHosts: false,
              roleCardinality: [],
            },
          },
          {
            id: "single",
            displayName: "Single node",
            placementKind: "MEMBER_SCOPED",
            roles: ["broker"],
            guidance: {
              minParticipants: 1,
              maxParticipants: 1,
              distinctHosts: false,
              roleCardinality: [],
            },
          },
        ],
        configurationSettings: [
          {
            id: "replicaCount",
            kind: "MANAGED",
            scopes: ["deployment"],
            label: "Количество реплик",
            editorShape: "INTEGER",
            minimum: 1,
            maximum: 9,
          },
          {
            id: "advancedConfig",
            kind: "MANAGED",
            scopes: ["deployment"],
            label: "Расширенная конфигурация",
            editorShape: "UNSUPPORTED",
          },
        ],
      },
    ],
  },
  verification: { status: "NOT_VERIFIED" },
  snapshot: {
    status: "PASS",
    project: { name: "Test" },
    projectRevision: "sha256:old",
    snapshotFingerprint: "sha256:snapshot",
    hosts: {
      node1: {
        type: "infra",
        desiredHostname: "node1.example.internal",
        ansibleHost: "192.0.2.10",
        ansiblePort: 2222,
      },
    },
    serviceDeployments: {},
    pki: {},
    findings: [],
    documents: [],
  },
};
const emptyProject = {
  status: "OPEN",
  root: "C:/Projects/test",
  classification: "EMPTY_MANAGED_PROJECT",
  project: {
    id: "project-0123456789abcdef",
    name: "Test",
    source: { bundleDigest: "sha256:bundle" },
  },
  catalog: project.catalog,
  counts: { servers: 0, deployments: 0, runs: 0 },
};
const h3Project = {
  ...project,
  managed: {
    ...project.managed,
    memberPlacements: [
      {
        deploymentId: "kafka-main",
        memberId: "kafka-kafka-1",
        hostId: "node1",
        roles: ["broker"],
        configuration: [],
      },
      {
        deploymentId: "kafka-main",
        memberId: "kafka-kafka-2",
        hostId: "node1",
        roles: ["broker"],
        configuration: [],
      },
    ],
    pki: {
      authorities: {},
      profiles: {},
      tlsProfiles: { "infrastructure-tls": {} },
      scopes: {},
    },
  },
  catalog: {
    ...project.catalog,
    services: project.catalog.services.map((service) =>
      service.id === "kafka"
        ? {
            ...service,
            configurationSettings: [
              ...(service.configurationSettings || []),
              {
                id: "tlsProfile",
                kind: "MANAGED",
                scopes: ["deployment", "member"],
                label: "TLS profile",
                editorShape: "TLS_PROFILE",
                referenceKind: "TLS_PROFILE",
              },
            ],
          }
        : service,
    ),
  },
};

const dnsClientReferenceProject = {
  ...project,
  managed: {
    ...project.managed,
    deployments: {
      ...project.managed.deployments,
      "bind-main": {
        deploymentId: "bind-main",
        serviceType: "bind",
        mode: "primary-secondary",
      },
      "dns-client-main": {
        deploymentId: "dns-client-main",
        serviceType: "dns-client",
        mode: "host-resolver",
      },
    },
  },
  catalog: {
    ...project.catalog,
    services: [
      ...project.catalog.services,
      {
        id: "dns-client",
        definitionVersion: "1",
        displayName: "DNS client",
        category: "Network",
        ui: {},
        endpointConsumer: false,
        endpointProvider: false,
        modes: [
          {
            id: "host-resolver",
            displayName: "Host resolver",
            placementKind: "HOST_SCOPED",
            roles: [],
            guidance: { minParticipants: 1, distinctHosts: false },
          },
        ],
        configurationSettings: [
          {
            id: "dnsServerRef",
            kind: "MANAGED",
            scopes: ["deployment"],
            label: "Authoritative DNS deployment",
            editorShape: "SERVICE_DEPLOYMENT",
            referenceKind: "SERVICE_DEPLOYMENT",
          },
        ],
      },
    ],
  },
};

type MockApi = ProjectBackend & {
  chooseProject: ReturnType<typeof vi.fn>;
  openProject: ReturnType<typeof vi.fn>;
  startEditSession: ReturnType<typeof vi.fn>;
  appendEditCommand: ReturnType<typeof vi.fn>;
  reviewEditSession: ReturnType<typeof vi.fn>;
  commitEditPlan: ReturnType<typeof vi.fn>;
  discardEditSession: ReturnType<typeof vi.fn>;
  verifyProject: ReturnType<typeof vi.fn>;
};

it("shows a verified incoming bundle but binds only after explicit confirmation", async () => {
  const preview = {
    status: "PREVIEW",
    previewId: "one-use-token",
    currentArtifactDigest: "sha256:old",
    newArtifactDigest: "sha256:new",
    newCatalogDigest: "sha256:catalog",
    bundleVersion: "2",
    coreVersion: "2",
  };
  const chooseRuntimeBundleUpdate = vi.fn().mockResolvedValue(preview);
  const confirmRuntimeBundleUpdate = vi
    .fn()
    .mockResolvedValue({ status: "UPDATED" });
  const value = api({ chooseRuntimeBundleUpdate, confirmRuntimeBundleUpdate });
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  value.openProject.mockResolvedValue(project as unknown as OpenResult);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  expect(await screen.findByText("sha256:new")).toBeTruthy();
  expect(confirmRuntimeBundleUpdate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Привязать" }));
  await waitFor(() =>
    expect(confirmRuntimeBundleUpdate).toHaveBeenCalledWith("one-use-token"),
  );
});

it("shows the previous-run failure and retries bundle detection after confirming terminal state", async () => {
  const preview = {
    status: "PREVIEW",
    previewId: "one-use-token",
    currentArtifactDigest: "sha256:old",
    newArtifactDigest: "sha256:new",
    newCatalogDigest: "sha256:catalog",
    bundleVersion: "2",
    coreVersion: "2",
  };
  const chooseRuntimeBundleUpdate = vi
    .fn()
    .mockResolvedValueOnce({
      status: "BLOCKED",
      error: {
        code: "INSTALLATION_RUN_ACTIVE",
        message:
          "Новый набор пока нельзя проверить: прежний запуск не подтверждён как завершённый.",
      },
    })
    .mockResolvedValueOnce(preview);
  const inspectOrphanRun = vi.fn().mockResolvedValue({
    status: "RESOLVED",
    runId: "installer-prior-run",
    runState: "FAILED",
  });
  const checkExecutionNode = vi.fn().mockResolvedValue({ status: "READY" });
  const value = api({
    chooseRuntimeBundleUpdate,
    inspectOrphanRun,
    checkExecutionNode,
    getServiceConfigurationPreview: vi.fn().mockResolvedValue({
      projectRevision: "sha256:old", runtimeDigest: "sha256:runtime", services: {},
    }),
    getExecutionNodeContext: vi.fn().mockResolvedValue({
      status: "READY",
      selectionKind: "PROJECT_SERVER",
      selectionSource: "EXPLICIT",
      selectedHostId: "node1",
      safeLabel: "node1",
      runtimeDigest: "sha256:runtime",
    }),
  });
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  expect(
    await screen.findByText(
      /Прежний запуск установки не подтверждён как завершённый/i,
    ),
  ).toBeTruthy();
  expect(screen.queryByText(/Код: INSTALLATION_RUN_ACTIVE/)).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Проверить прежний запуск" }),
  ).toBeNull();
  await userEvent.click(
    screen.getByRole("button", { name: "Перейти к серверам" }),
  );

  await userEvent.click(screen.getByRole("button", { name: "Проверить узел" }));
  expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();

  await userEvent.click(
    screen.getByRole("button", { name: "Проверить прежний запуск" }),
  );

  await waitFor(() => expect(inspectOrphanRun).toHaveBeenCalledTimes(1));
  expect(screen.getByText("Проверен: Подготовлен")).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Проект" }));
  expect(await screen.findByText("sha256:new")).toBeTruthy();
  expect(chooseRuntimeBundleUpdate).toHaveBeenCalledTimes(2);
  expect(inspectOrphanRun).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
  expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();
  expect(checkExecutionNode).toHaveBeenCalledTimes(1);
});

it("explains when the previous run cannot be checked and keeps the safety block visible", async () => {
  const chooseRuntimeBundleUpdate = vi.fn().mockResolvedValue({
    status: "BLOCKED",
    error: {
      code: "INSTALLATION_RUN_ACTIVE",
      message:
        "Новый набор пока нельзя проверить: прежний запуск не подтверждён как завершённый.",
    },
  });
  const inspectOrphanRun = vi.fn().mockResolvedValue({ status: "UNAVAILABLE" });
  const value = api({ chooseRuntimeBundleUpdate, inspectOrphanRun });
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Перейти к серверам" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Проверить прежний запуск" }),
  );

  await waitFor(() => expect(inspectOrphanRun).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("heading", { name: "Серверы" })).toBeTruthy();
  expect(chooseRuntimeBundleUpdate).toHaveBeenCalledTimes(1);
});

function api(overrides: Record<string, unknown> = {}): MockApi {
  return {
    getExecutionNodeContext: vi.fn().mockResolvedValue({
      status: "READY",
      selectionKind: "PROJECT_SERVER",
      selectedHostId: "node1",
      runtimeDigest: "sha256:runtime-a",
    }),
    getServiceConfigurationPreview: vi.fn().mockResolvedValue({
      projectRevision: "sha256:old",
      runtimeDigest: "sha256:runtime-a",
      services: {},
    }),
    getApplicationConfig: vi.fn().mockResolvedValue({
      status: "READY",
      config: {
        schemaVersion: 1,
        serverTypes: [{ id: "infra", displayName: "Инфраструктура" }],
      },
    }),
    chooseProject: vi.fn(),
    openProject: vi.fn(),
    chooseProjectParent: vi.fn(),
    createProject: vi.fn(),
    closeProject: vi.fn().mockResolvedValue({ status: "NO_PROJECT" }),
    startEditSession: vi.fn().mockResolvedValue({
      status: "EDITING",
      session: { sessionId: sessionID, commandCount: 0 },
    }),
    appendEditCommand: vi.fn().mockResolvedValue({
      status: "EDITING",
      session: { sessionId: sessionID, commandCount: 1 },
    }),
    amendServiceConfigurationDraft: vi.fn().mockResolvedValue({
      status: "EDITING",
      session: { sessionId: sessionID, commandCount: 1 },
    }),
    reviewEditSession: vi.fn(),
    commitEditPlan: vi.fn(),
    discardEditSession: vi.fn().mockResolvedValue({ status: "DISCARDED" }),
    verifyProject: vi
      .fn()
      .mockResolvedValue({ status: "VERIFIED", projectRevision: "sha256:old" }),
    getSessionCredentialStatus: vi.fn().mockResolvedValue({
      status: "MISSING",
      sudoPasswordStatus: "NOT_PROVIDED",
    }),
    setSessionCredential: vi.fn().mockResolvedValue({
      status: "PRESENT",
      username: "installer",
      sshMode: "SSH_PASSWORD",
      sudoPasswordStatus: "PRESENT",
      expiresAt: "2026-09-14T14:00:00Z",
    }),
    clearSessionCredential: vi.fn().mockResolvedValue({
      status: "MISSING",
      sudoPasswordStatus: "NOT_PROVIDED",
    }),
    ...overrides,
  } as unknown as MockApi;
}

it("restores a CURRENT run and its plan after a React reload without another Start", async () => {
  const runId = "installer-current-run";
  const getInstallationRun = vi.fn().mockResolvedValue({
    status: "READY",
    projectRevision: "sha256:run-revision",
    run: { runId, state: "RUNNING", sequence: 0 },
    plan: {
      id: "current-plan",
      projectRevision: "sha256:run-revision",
      phases: [
        {
          id: "applications",
          order: 0,
          actions: [
            {
              id: "apply",
              type: "APPLICATION_LIBRARIES_APPLY",
              summary: "Apply libraries",
              targets: ["node1"],
              dependsOn: [],
            },
          ],
        },
      ],
    },
  });
  const attachOrphanRun = vi.fn();
  const startApprovedInstallation = vi.fn();
  const subscribeInstallationRun = vi
    .fn()
    .mockResolvedValue({ status: "READY", subscriptionId: "current-sub" });
  const value = api({
    inspectOrphanRun: vi.fn().mockResolvedValue({ status: "CURRENT", runId }),
    getInstallationRun,
    attachOrphanRun,
    startApprovedInstallation,
    subscribeInstallationRun,
  });
  await openServers(value);
  await userEvent.click(
    screen.getByRole("button", { name: "Проверить прежний запуск" }),
  );
  expect(
    await screen.findByText(/Запуск уже известен этому Installer/),
  ).toBeTruthy();
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть выполнение" }),
  );
  await waitFor(() =>
    expect(subscribeInstallationRun).toHaveBeenCalledWith(runId, 0),
  );
  expect(screen.queryByText("В этом сеансе запуск ещё не начат.")).toBeNull();
  expect(
    screen.getAllByText("Установить библиотеки приложений").length,
  ).toBeGreaterThan(0);
  expect(attachOrphanRun).not.toHaveBeenCalled();
  expect(startApprovedInstallation).not.toHaveBeenCalled();
});

it("attaches the previous run and reuses execution, events and cancellation without another Start", async () => {
  const runId = "installer-prior-run";
  let onRunEvent:
    | Parameters<
        NonNullable<ProjectBackend["subscribeInstallationRunEvents"]>
      >[0]
    | undefined;
  const recoveredPlan = {
    id: "prior-plan",
    projectRevision: "sha256:previous-revision",
    phases: [
      {
        id: "applications",
        order: 0,
        actions: [
          {
            id: "apply",
            type: "APPLICATION_LIBRARIES_APPLY",
            targets: ["node1"],
            dependsOn: [],
            summary: "Apply recovered libraries",
          },
          {
            id: "verify",
            type: "APPLICATION_LIBRARIES_VERIFY",
            targets: ["node1"],
            dependsOn: ["apply"],
            summary: "Verify recovered libraries",
          },
        ],
      },
    ],
  };
  const inspectOrphanRun = vi.fn().mockResolvedValue({
    status: "FOUND",
    recoveryId: "recovery-token",
    runId,
    runState: "RUNNING",
    projectRevision: "sha256:previous-revision",
  });
  const attachOrphanRun = vi.fn().mockResolvedValue({
    status: "READY",
    reconnected: true,
    projectRevision: "sha256:previous-revision",
    plan: recoveredPlan,
    run: { runId, state: "RUNNING", sequence: 0 },
  });
  const subscribeInstallationRun = vi.fn().mockResolvedValue({
    status: "SUBSCRIBED",
    subscriptionId: "recovered-sub",
  });
  const cancelInstallationRun = vi.fn().mockResolvedValue({
    status: "CANCELLING",
    reconnected: true,
    run: { runId, state: "CANCELLING", sequence: 0 },
  });
  const startApprovedInstallation = vi.fn();
  const value = api({
    inspectOrphanRun,
    attachOrphanRun,
    subscribeInstallationRun,
    cancelInstallationRun,
    startApprovedInstallation,
    subscribeInstallationRunEvents: vi.fn((handler) => {
      onRunEvent = handler;
      return vi.fn();
    }),
  });
  await openServers(value);
  await userEvent.click(
    screen.getByRole("button", { name: "Проверить прежний запуск" }),
  );
  expect(await screen.findByText(/sha256:previous-revision/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: "Подключиться" }));
  await waitFor(() =>
    expect(subscribeInstallationRun).toHaveBeenCalledWith(runId, 0),
  );
  expect(attachOrphanRun).toHaveBeenCalledWith("recovery-token");
  expect(
    await screen.findByText(/Переподключено к прежнему запуску/),
  ).toBeTruthy();
  expect(
    screen.getAllByText("Установить библиотеки приложений").length,
  ).toBeGreaterThan(0);
  expect(
    screen.queryByText("Действия плана для этого запуска недоступны."),
  ).toBeNull();
  await act(async () => {
    for (const [sequence, actionId, eventType, status] of [
      [1, "apply", "ACTION_STARTED", "RUNNING"],
      [2, "apply", "ACTION_COMPLETED", "SUCCESS"],
      [3, "verify", "ACTION_STARTED", "RUNNING"],
    ] as const)
      onRunEvent?.({
        subscriptionId: "recovered-sub",
        event: {
          runId,
          sequence,
          actionId,
          eventType,
          status,
          timestamp: "2026-10-25T12:00:00Z",
          safeMessage: "safe",
          redacted: true,
        } as InstallationEventView,
      });
  });
  expect(screen.getAllByText(/50%/).length).toBeGreaterThan(0);
  expect(screen.getByText("1 из 2 завершено")).toBeTruthy();
  await userEvent.click(
    screen.getByRole("button", { name: "Отменить выполнение" }),
  );
  await waitFor(() =>
    expect(cancelInstallationRun).toHaveBeenCalledWith(runId),
  );
  expect(startApprovedInstallation).not.toHaveBeenCalled();
});

async function openServers(
  value: MockApi,
  open: OpenResult = project as unknown as OpenResult,
) {
  value.chooseProject.mockResolvedValue(open);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
}

async function openTopology(
  value: MockApi,
  open: OpenResult = project as unknown as OpenResult,
) {
  value.chooseProject.mockResolvedValue(open);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Топология" }));
}

async function openCertificates(
  value: MockApi,
  open: OpenResult = project as unknown as OpenResult,
) {
  value.chooseProject.mockResolvedValue(open);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Сертификаты" }));
}

it("restores Logs, Help, About and Settings navigation without requiring an open project", async () => {
  render(<App api={api()} />);

  await userEvent.click(await screen.findByRole("button", { name: "Журналы" }));
  expect(screen.getByRole("heading", { name: "Журналы" })).toBeTruthy();
  expect(
    screen.getByText("События появятся здесь после запуска плана."),
  ).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Справка" }));
  expect(screen.getByRole("heading", { name: "Справка" })).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: /Ошибки/ }));
  await userEvent.click(
    screen.getByRole("button", {
      name: "Как обновить привязку существующего проекта?",
    }),
  );
  expect(
    screen.getByText(/На странице «Проект» нажмите «Проверить новый набор»/),
  ).toBeTruthy();
  expect(screen.getByText(/Не редактируйте digest вручную/)).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "О программе" }));
  expect(screen.getByRole("heading", { name: "О программе" })).toBeTruthy();
  expect(screen.getAllByText("Platform Installer V2").length).toBeGreaterThan(
    0,
  );
  expect(screen.getByText("v1")).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Настройки" }));
  expect(screen.getByRole("heading", { name: "Настройки" })).toBeTruthy();
  expect(
    screen.getByText(/Учётные данные сеанса и секреты не сохраняются/),
  ).toBeTruthy();
});

it("highlights project settings staged in the shared draft and keeps them visible across navigation", async () => {
  const value = api();
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Настройки" }));
  const dataRoot = screen.getByRole("textbox", {
    name: "Корневой каталог данных сервисов",
  });
  await userEvent.clear(dataRoot);
  await userEvent.type(dataRoot, "/data");
  await userEvent.click(
    screen.getByRole("button", { name: "Добавить каталог в черновик" }),
  );

  const draftStatus = () =>
    screen.findByText((_, element) =>
      Boolean(
        element?.classList.contains("project-setting-draft-status") &&
        element.textContent?.includes("/data"),
      ),
    );
  expect(await draftStatus()).toBeTruthy();
  expect(screen.getByText("Есть несохранённые изменения")).toBeTruthy();
  expect(dataRoot.closest(".project-setting-field")?.className).toContain(
    "project-setting-field--changed",
  );

  await userEvent.click(screen.getByRole("button", { name: "Проект" }));
  await userEvent.click(screen.getByRole("button", { name: "Настройки" }));
  expect(
    screen.getByRole("textbox", { name: "Корневой каталог данных сервисов" }),
  ).toHaveProperty("value", "/data");
  expect(await draftStatus()).toBeTruthy();
});

it("shows the error when adding the first project setting to the shared draft fails", async () => {
  const value = api();
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  value.appendEditCommand.mockResolvedValue({
    status: "BLOCKED",
    error: {
      code: "EDIT_OPERATION_NOT_AVAILABLE",
      message: "Операция недоступна.",
    },
  });
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Настройки" }));
  const dataRoot = screen.getByRole("textbox", {
    name: "Корневой каталог данных сервисов",
  });
  await userEvent.clear(dataRoot);
  await userEvent.type(dataRoot, "/data");
  await userEvent.click(
    screen.getByRole("button", { name: "Добавить каталог в черновик" }),
  );

  const error = await screen.findByRole("alert");
  expect(error.textContent).toContain("EDIT_OPERATION_NOT_AVAILABLE");
  expect(error.textContent).toContain("Операция недоступна.");
  expect(screen.getByText("Сохранено")).toBeTruthy();
  expect(value.discardEditSession).toHaveBeenCalledWith(sessionID);
});

it("shows the read-only Installation state without requesting a deployment plan", async () => {
  const getInstallationState = vi.fn().mockResolvedValue({
    apiVersion: "platform.installer/installation-state/v1alpha1",
    kind: "InstallationState",
    status: "PREREQUISITES_REQUIRED",
    project: {
      id: "project-aaaaaaaaaaaaaaaa",
      revision: "sha256:old",
      verificationStatus: "UNVERIFIED",
      hasUnsavedChanges: false,
    },
    executionNode: { status: "READY", safeLabel: "node1 · 192.0.2.10" },
    plan: { status: "NOT_CREATED" },
    prerequisites: [
      {
        code: "EXECUTION_NODE_BINDING_REQUIRED",
        destination: "servers",
        safeMessage:
          "The selected Execution Node has no trusted runtime binding.",
      },
    ],
  });
  const value = api({
    getExecutionNodeContext: vi
      .fn()
      .mockResolvedValue({
        status: "READY",
        runtimeDigest: "sha256:runtime-a",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
      }),
    getInstallationState,
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Установка" }),
  );

  expect(screen.getByText(/План не сформирован/)).toBeTruthy();
  expect(screen.getByRole("tab", { name: "План" })).toBeTruthy();
  expect(getInstallationState).toHaveBeenCalled();
});

it("refreshes Installation verification after header Verify without checking the node again", async () => {
  let verificationStatus = "UNVERIFIED";
  const getInstallationState = vi.fn().mockImplementation(async () => ({
    status: "PREREQUISITES_REQUIRED",
    project: {
      revision: "sha256:old",
      verificationStatus,
      hasUnsavedChanges: false,
    },
    executionNode: { status: "READY", safeLabel: "node1" },
    plan: { status: "NOT_CREATED" },
    prerequisites: [],
  }));
  const value = api({
    getInstallationState,
    verifyProject: vi.fn().mockImplementation(async () => {
      verificationStatus = "VERIFIED";
      return { status: "VERIFIED", projectRevision: "sha256:old" };
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Установка" }));
  await waitFor(() => expect(getInstallationState).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  await waitFor(() => expect(screen.getAllByText("Проверено")).toHaveLength(2));
});

it("refreshes a running installation without navigation or a SUCCEEDED event", async () => {
  let onRunEvent:
    | Parameters<
        NonNullable<ProjectBackend["subscribeInstallationRunEvents"]>
      >[0]
    | undefined;
  const getInstallationRun = vi.fn().mockResolvedValue({
    status: "READY",
    run: { runId: "run-refresh", state: "RUNNING", sequence: 4 },
  });
  const value = api({
    getInstallationRun,
    subscribeInstallationRunEvents: vi.fn((handler) => {
      onRunEvent = handler;
      return vi.fn();
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  const view = render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  const event = (status: string, sequence: number): InstallationEventView =>
    ({
      runId: "run-refresh",
      sequence,
      timestamp: "2026-10-08T10:00:00Z",
      eventType: "DIAGNOSTIC",
      status,
      safeMessage: "Safe event",
      redacted: true,
    }) as InstallationEventView;
  // Seed the known active run through the existing refresh handler.
  await act(async () =>
    onRunEvent?.({ subscriptionId: "", event: event("SUCCEEDED", 4) }),
  );
  expect(screen.getByText("Идёт установка")).toBeTruthy();
  const calls = getInstallationRun.mock.calls.length;
  await act(async () =>
    onRunEvent?.({ subscriptionId: "", event: event("SUCCESS", 5) }),
  );
  expect(getInstallationRun).toHaveBeenCalledTimes(calls);
  expect(screen.getByText("Идёт установка")).toBeTruthy();
  getInstallationRun.mockResolvedValue({
    status: "READY",
    run: { runId: "run-refresh", state: "SUCCEEDED", sequence: 5 },
  });
  await waitFor(
    () => expect(screen.getByText(/Установка выполнена/)).toBeTruthy(),
    { timeout: 4000 },
  );
  expect(screen.getByText(/100%/)).toBeTruthy();
  view.unmount();
});

it("replays late failure events before closing a terminal subscription", async () => {
  let handler:
    | Parameters<
        NonNullable<ProjectBackend["subscribeInstallationRunEvents"]>
      >[0]
    | undefined;
  const unsubscribe = vi.fn().mockResolvedValue(undefined);
  const subscribe = vi
    .fn()
    .mockResolvedValue({ status: "SUBSCRIBED", subscriptionId: "original" });
  const state = {
    status: "PLAN_APPROVED",
    project: { revision: "sha256:old", hasUnsavedChanges: false },
    executionNode: { status: "READY" },
    plan: { status: "PLAN_APPROVED", planId: "plan-tail" },
    prerequisites: [],
  };
  const plan = {
    id: "plan-tail",
    status: "EXECUTABLE",
    approved: true,
    projectRevision: "sha256:old",
    phases: [],
    acknowledgements: [],
    runtime: {},
    expiresAt: "2099-01-01T00:00:00Z",
  };
  const getRun = vi.fn().mockResolvedValue({
    status: "READY",
    run: { runId: "run-tail", state: "RUNNING", sequence: 1 },
  });
  const value = api({
    getInstallationState: vi.fn().mockResolvedValue(state),
    createInstallationPlan: vi
      .fn()
      .mockResolvedValue({ status: "PLAN_APPROVED", plan }),
    startApprovedInstallation: vi.fn().mockResolvedValue({
      status: "READY",
      run: { runId: "run-tail", state: "RUNNING", sequence: 0 },
    }),
    subscribeInstallationRun: subscribe,
    unsubscribeInstallationRun: unsubscribe,
    getInstallationRun: getRun,
    subscribeInstallationRunEvents: vi.fn((callback) => {
      handler = callback;
      return vi.fn();
    }),
  });
  value.chooseProject.mockResolvedValue({
    ...project,
    managed: { ...project.managed, deployments: {} },
  });
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Установка" }),
  );
  await userEvent.click(screen.getByRole("tab", { name: "План" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Начать выполнение" }),
  );
  await waitFor(() => expect(subscribe).toHaveBeenCalledWith("run-tail", 0));
  const event = (sequence: number, status: string, message: string) =>
    ({
      runId: "run-tail",
      sequence,
      eventType: "DIAGNOSTIC",
      status,
      safeMessage: message,
      timestamp: "2026-10-09T09:30:31Z",
    }) as InstallationEventView;
  getRun.mockResolvedValue({
    status: "READY",
    run: { runId: "run-tail", state: "FAILED", sequence: 3 },
  });
  subscribe.mockResolvedValue({
    status: "SUBSCRIBED",
    subscriptionId: "replay",
  });
  await act(async () =>
    handler?.({
      subscriptionId: "original",
      event: event(1, "FAILED", "Первая ошибка"),
    }),
  );
  await waitFor(() => expect(subscribe).toHaveBeenCalledWith("run-tail", 1));
  expect(unsubscribe).not.toHaveBeenCalledWith("replay");
  await act(async () =>
    handler?.({
      subscriptionId: "replay",
      event: event(2, "FAILED", "Поздняя ошибка"),
    }),
  );
  expect(screen.getAllByText("Поздняя ошибка").length).toBeGreaterThan(0);
  expect(unsubscribe).not.toHaveBeenCalledWith("replay");
  await act(async () =>
    handler?.({
      subscriptionId: "replay",
      event: event(3, "FAILED", "Запуск остановлен"),
    }),
  );
  await waitFor(() => expect(unsubscribe).toHaveBeenCalledWith("replay"));
});

it("shows a safe listing error when automatic output collection rejects", async () => {
  let onRunEvent:
    | Parameters<
        NonNullable<ProjectBackend["subscribeInstallationRunEvents"]>
      >[0]
    | undefined;
  const value = api({
    subscribeInstallationRunEvents: vi.fn((handler) => {
      onRunEvent = handler;
      return vi.fn();
    }),
    listPendingSecretOutputs: vi
      .fn()
      .mockRejectedValue(new Error("raw transport detail with secret")),
    getInstallationRun: vi.fn().mockResolvedValue({
      status: "READY",
      run: { runId: "run-output", state: "SUCCEEDED", sequence: 4 },
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);

  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Установка" }),
  );
  await userEvent.click(screen.getByRole("tab", { name: "Результат" }));

  onRunEvent?.({
    subscriptionId: "",
    event: {
      runId: "run-output",
      sequence: 4,
      timestamp: "2026-10-08T10:00:00Z",
      eventType: "RUN_COMPLETED",
      status: "SUCCEEDED",
      safeMessage: "Run completed",
      redacted: true,
    } as InstallationEventView,
  });

  expect(
    await screen.findByText(
      "Не удалось проверить ожидающие защищённые файлы. Повторите проверку позже.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText("raw transport detail with secret")).toBeNull();
});

it("adds a certificate authority through the shared structural draft", async () => {
  const value = api();
  await openCertificates(value);
  await userEvent.click(screen.getAllByRole("button", { name: "Добавить" })[0]);
  await userEvent.type(screen.getByLabelText("ID"), "platform-ca");
  await userEvent.type(screen.getByLabelText("Общее имя (CN)"), "Platform CA");
  await userEvent.click(
    screen.getByRole("button", { name: "Добавить в черновик" }),
  );
  expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
    operation: "CreateCertificateAuthority",
    entityId: "platform-ca",
    entity: { mode: "MANAGED", commonName: "Platform CA" },
  });
  expect(screen.getByText("Есть несохранённые изменения")).toBeTruthy();
});

it("loads revision-bound PKI evidence only after an explicit Core verification", async () => {
  const getVerifiedPKIView = vi.fn().mockResolvedValue({
    status: "CURRENT",
    identities: [
      {
        id: "platform-tls--kafka-main",
        scope: "DEPLOYMENT",
        tlsProfileId: "platform-tls",
        dnsNames: ["kafka.example.test"],
        ipAddresses: ["192.0.2.44"],
        consumers: [
          {
            deploymentId: "kafka-main",
            memberId: "kafka-kafka-1",
            hostId: "node1",
          },
        ],
      },
    ],
  });
  const value = api({ getVerifiedPKIView });
  await openCertificates(value);
  await userEvent.click(
    screen.getAllByRole("button", { name: "Проверить" })[1],
  );
  expect(value.verifyProject).toHaveBeenCalledOnce();
  expect(getVerifiedPKIView).toHaveBeenCalledOnce();
  expect(screen.getByText("kafka.example.test")).toBeTruthy();
});

/**
 * Deterministic UI acceptance backend.  It deliberately models only the
 * public ProjectBackend edit/review/commit/reopen lifecycle: Core, an
 * Execution Node and targets are absent from this test seam.
 */
function f4AcceptanceBackend() {
  const appended: Array<Record<string, unknown>> = [];
  let pending: Array<Record<string, unknown>> = [];
  let revision = 0;
  let memberPlacements: Array<{
    deploymentId: string;
    memberId: string;
    hostId: string;
    roles: string[];
  }> = [];
  let hostPlacements: Array<{
    deploymentId: string;
    hostId: string;
    roles: string[];
    priority?: number;
  }> = [];
  const catalog = {
    ...project.catalog,
    services: [
      ...project.catalog.services,
      {
        id: "agent",
        definitionVersion: "1",
        displayName: "Node Agent",
        category: "Infrastructure",
        ui: {},
        endpointConsumer: false,
        endpointProvider: false,
        modes: [
          {
            id: "daemon",
            displayName: "Daemon",
            placementKind: "HOST_SCOPED",
            roles: [],
            guidance: {
              minParticipants: 1,
              distinctHosts: false,
              roleCardinality: [],
            },
          },
          {
            id: "observer",
            displayName: "Observer",
            placementKind: "HOST_SCOPED",
            roles: ["observer"],
            guidance: {
              minParticipants: 1,
              distinctHosts: false,
              roleCardinality: [],
            },
          },
        ],
      },
    ],
  };
  const open = () =>
    ({
      status: "OPEN",
      root: "C:/Projects/f4-acceptance",
      classification: "MANAGED_PROJECT",
      project: { name: "F4 acceptance" },
      catalog,
      managed: {
        projectRevision: `sha256:f4-${revision}`,
        servers: {
          node1: {
            hostId: "node1",
            type: "infra",
            desiredHostname: "node1.example.internal",
            address: "192.0.2.10",
          },
        },
        deployments: {
          "kafka-main": {
            deploymentId: "kafka-main",
            serviceType: "kafka",
            mode: "kraft",
          },
          "agent-main": {
            deploymentId: "agent-main",
            serviceType: "agent",
            mode: "daemon",
          },
          "agent-role-main": {
            deploymentId: "agent-role-main",
            serviceType: "agent",
            mode: "observer",
          },
        },
        memberPlacements,
        hostPlacements,
      },
      verification: { status: "UNVERIFIED" },
    }) as unknown as OpenResult;
  const value: ProjectBackend = {
    getApplicationConfig: async () =>
      ({
        status: "READY",
        config: {
          schemaVersion: 1,
          serverTypes: [{ id: "infra", displayName: "Инфраструктура" }],
        },
      }) as never,
    chooseProject: async () => open(),
    openProject: async () => open(),
    chooseProjectParent: async () => "",
    createProject: async () => open(),
    closeProject: async () => ({ status: "NO_PROJECT" }) as never,
    startEditSession: async () =>
      ({
        status: "EDITING",
        session: { sessionId: sessionID, commandCount: pending.length },
      }) as never,
    appendEditCommand: async (_sessionId, command) => {
      appended.push(command);
      pending.push(command);
      return {
        status: "EDITING",
        session: { sessionId: sessionID, commandCount: pending.length },
      } as never;
    },
    amendServiceConfigurationDraft: async () =>
      ({ status: "BLOCKED" }) as never,
    reviewEditSession: async () =>
      ({
        status: "READY",
        plan: {
          planId: "f4-plan",
          status: "READY",
          saveAllowed: true,
          semanticChanges: [],
          affectedDocuments: [],
        },
      }) as never,
    commitEditPlan: async () => {
      for (const command of pending) {
        if (command.operation === "ReconcileDeploymentPlacement") {
          const deploymentId = String(command.deploymentId);
          memberPlacements = [
            ...memberPlacements.filter(
              (item) => item.deploymentId !== deploymentId,
            ),
            ...(
              command.members as Array<{
                memberId: string;
                hostId: string;
                roles?: string[];
                priority: number;
              }>
            ).map((item) => ({
              deploymentId,
              memberId: item.memberId,
              hostId: item.hostId,
              roles: item.roles || [],
              priority: item.priority,
            })),
          ];
          hostPlacements = hostPlacements.filter(
            (item) => item.deploymentId !== deploymentId,
          );
        }
        if (command.operation === "ReconcileHostScopedDeploymentPlacement") {
          const deploymentId = String(command.deploymentId);
          hostPlacements = [
            ...hostPlacements.filter(
              (item) => item.deploymentId !== deploymentId,
            ),
            ...(
              command.hosts as Array<{
                hostId: string;
                roles?: string[];
              }>
            ).map((item) => ({
              deploymentId,
              hostId: item.hostId,
              roles: item.roles || [],
            })),
          ];
          memberPlacements = memberPlacements.filter(
            (item) => item.deploymentId !== deploymentId,
          );
        }
      }
      pending = [];
      revision += 1;
      return {
        status: "COMMITTED",
        commit: {
          status: "COMMITTED",
          newProjectRevision: `sha256:f4-${revision}`,
        },
        current: open(),
      } as never;
    },
    discardEditSession: async () => {
      pending = [];
      return { status: "DISCARDED" } as never;
    },
  };
  return { value, appended };
}

describe("UI-01E2 server editor", () => {
  it("shows saved and verification state separately before editing", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    expect(await screen.findByText("Сохранено")).toBeTruthy();
    expect(await screen.findAllByText("Не проверено")).not.toHaveLength(0);
    expect(
      (screen.getByRole("button", { name: "Топология" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
    expect(
      screen
        .getByRole("button", { name: "Топология" })
        .classList.contains("future"),
    ).toBe(false);
    await waitFor(() => expect(
      screen
        .getByRole("button", { name: "Установка" })
        .classList.contains("future"),
    ).toBe(false));
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
  });

  it("blocks Installation before readiness while preparation stays on Servers", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "UPDATE_REQUIRED",
        runtimeDigest: "sha256:old",
        selectionKind: "EXPLICIT_EXTERNAL",
        selectionSource: "EXPLICIT",
        safeLabel: "desktop-qa · 192.0.2.10",
        locked: true,
      }),
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
      planExecutionNodePreparation: vi.fn().mockResolvedValue({
        status: "CONFIRMATION_REQUIRED",
        planId: "prepare-plan",
      }),
      prepareExecutionNode: vi.fn().mockResolvedValue({
        status: "PREPARED",
        verification: { status: "VERIFIED" },
      }),
    });
    await openServers(value);
    expect(
      (await screen.findByRole("button", {
        name: "Установка",
      })) as HTMLButtonElement,
    ).toHaveProperty("disabled", true);
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить узел" }),
    );
    expect(value.checkExecutionNode).toHaveBeenCalledOnce();
    expect(
      (screen.getByRole("button", { name: "Установка" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(
      screen
        .getByRole("button", { name: "Установка" })
        .classList.contains("future"),
    ).toBe(true);
    await userEvent.click(
      screen.getByRole("button", { name: "Спланировать подготовку" }),
    );
    expect(
      await screen.findByRole("button", { name: "Подтвердить подготовку" }),
    ).toBeTruthy();
    vi.mocked(value.getExecutionNodeContext!).mockResolvedValue({
      status: "READY",
      runtimeDigest: "sha256:new",
      selectionKind: "EXPLICIT_EXTERNAL",
      selectionSource: "EXPLICIT",
      safeLabel: "desktop-qa · 192.0.2.10",
      locked: true,
    });
    vi.mocked(value.getServiceConfigurationPreview!).mockResolvedValue({
      apiVersion: "platform.installer/service-configuration-preview/v1alpha1", kind: "ServiceConfigurationPreview",
      projectRevision: "sha256:old", runtimeDigest: "sha256:new", services: {},
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await userEvent.click(
      screen.getByRole("button", { name: "Подтвердить подготовку" }),
    );
    expect(value.prepareExecutionNode).toHaveBeenCalledWith("prepare-plan");
    expect(value.checkExecutionNode).toHaveBeenCalledTimes(2);
    expect(await screen.findByText(/Проверен: Подготовлен/)).toBeTruthy();
  });

  it("moves the next-action hint from node check through preparation to project Verify", async () => {
    const initialNode = {
      status: "NOT_PREPARED",
      selectionKind: "EXPLICIT_EXTERNAL",
      selectionSource: "EXPLICIT",
      safeLabel: "execution-node · 192.0.2.10",
      locked: false,
    };
    const getExecutionNodeContext = vi.fn().mockResolvedValue(initialNode);
    const value = api({
      getExecutionNodeContext,
      checkExecutionNode: vi
        .fn()
        .mockResolvedValueOnce({ status: "PREPARATION_REQUIRED" })
        .mockResolvedValue({ status: "READY" }),
      planExecutionNodePreparation: vi.fn().mockResolvedValue({
        status: "CONFIRMATION_REQUIRED",
        planId: "prepare-plan",
        steps: [{ id: "activate-runtime", action: "INSTALL", mutates: true }],
      }),
      prepareExecutionNode: vi.fn().mockResolvedValue({ status: "PREPARED" }),
    });
    await openServers(value, {
      ...project,
      verification: { status: "UNVERIFIED" },
    } as unknown as OpenResult);
    const check = screen.getByRole("button", { name: "Проверить узел" });
    const plan = screen.getByRole("button", { name: "Спланировать подготовку" });
    const verify = screen.getByRole("button", { name: "Проверить" });
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Требуется проверка");
    expect(screen.getAllByText("Требуется проверка")).toHaveLength(2);
    expect(screen.queryByText("Проверен: Требуется подготовка")).toBeNull();
    await waitFor(() => expect(check.classList.contains("next-step-hint")).toBe(true));
    expect(plan.classList.contains("next-step-hint")).toBe(false);
    expect(verify.classList.contains("next-step-hint")).toBe(false);

    await userEvent.click(check);
    await waitFor(() => expect(plan.classList.contains("next-step-hint")).toBe(true));
    expect(await screen.findByText("Проверен: Требуется подготовка")).toBeTruthy();
    expect(screen.queryByText("Требуется проверка")).toBeNull();
    expect(check.classList.contains("next-step-hint")).toBe(false);

    await userEvent.click(plan);
    const confirm = await screen.findByRole("button", {
      name: "Подтвердить подготовку",
    });
    expect(confirm.classList.contains("next-step-hint")).toBe(true);
    expect(plan.classList.contains("next-step-hint")).toBe(false);

    getExecutionNodeContext.mockResolvedValue({
      ...initialNode,
      status: "READY",
      runtimeDigest: "sha256:runtime-ready",
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await userEvent.click(confirm);
    await waitFor(() => expect(value.checkExecutionNode).toHaveBeenCalledTimes(2));
    expect(check.classList.contains("next-step-hint")).toBe(false);
    expect(plan.classList.contains("next-step-hint")).toBe(false);
    await waitFor(() => expect(verify.classList.contains("next-step-hint")).toBe(true));
    await userEvent.click(verify);
    await waitFor(() => expect(verify.classList.contains("next-step-hint")).toBe(false));
  });

  it("keeps all node indicators synchronized during preparation and page navigation", async () => {
    let finish!: (result: { status: string }) => void;
    const context = { status: "PREPARATION_REQUIRED", selectionKind: "EXPLICIT_EXTERNAL", selectionSource: "EXPLICIT", safeLabel: "execution-node", locked: false };
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue(context),
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
      planExecutionNodePreparation: vi.fn().mockResolvedValue({ status: "CONFIRMATION_REQUIRED", planId: "prepare-1", steps: [{ id: "activate", action: "ACTIVATE", mutates: true }] }),
      prepareExecutionNode: vi.fn().mockImplementation(() => new Promise((resolve) => { finish = resolve; })),
    });
    await openServers(value);
    await userEvent.click(screen.getByRole("button", { name: "Спланировать подготовку" }));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await userEvent.click(await screen.findByRole("button", { name: "Подтвердить подготовку" }));
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Выполняется подготовка");
    expect(screen.getAllByText("Выполняется подготовка")).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Проект" }));
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    expect(screen.getAllByText("Выполняется подготовка")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Спланировать подготовку" })).toHaveProperty("disabled", true);
    vi.mocked(value.getExecutionNodeContext!).mockResolvedValue({ ...context, status: "READY", runtimeDigest: "sha256:runtime-a" });
    await act(async () => finish({ status: "PREPARED" }));
    expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();
    expect(screen.getByText("Подготовлен")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Подготовлен");
  });

  it("suggests the server check used by a selected project Execution Node", async () => {
    const checkExecutionNode = vi.fn().mockResolvedValue({
      status: "PREPARATION_REQUIRED",
    });
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "NOT_PREPARED",
        selectionKind: "PROJECT_SERVER",
        selectionSource: "EXPLICIT",
        selectedHostId: "node1",
        safeLabel: "node1 · 192.0.2.10",
        locked: false,
      }),
      getSessionCredentialStatus: vi.fn().mockResolvedValue({
        status: "PRESENT",
        sshMode: "SSH_PASSWORD",
        expiresAt: "2026-10-30T15:00:00Z",
      }),
      probeServerInformation: vi.fn().mockResolvedValue({
        status: "APPROVAL_REQUIRED",
        probeId: "probe-1",
        keyType: "ssh-ed25519",
        fingerprint: "SHA256:example",
      }),
      checkServerInformation: vi.fn().mockResolvedValue({
        status: "CHECKED",
        hostId: "node1",
      }),
      checkExecutionNode,
    });
    await openServers(value);
    const check = (await screen.findAllByRole("button", {
      name: "Проверить сервер",
    })).at(-1)!;
    const plan = screen.getByRole("button", { name: "Спланировать подготовку" });
    await waitFor(() => expect(check.classList.contains("next-step-hint")).toBe(true));
    await userEvent.click(check);
    await userEvent.click(
      await screen.findByRole("button", { name: "Подтверждаю совпадение" }),
    );
    await waitFor(() => expect(checkExecutionNode).toHaveBeenCalledOnce());
    await waitFor(() => expect(plan.classList.contains("next-step-hint")).toBe(true));
    expect(check.classList.contains("next-step-hint")).toBe(false);
  });

  it("requires a name before creating a metadata-only project", async () => {
    const value = api({
      chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"),
      createProject: vi.fn().mockResolvedValue(emptyProject),
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Выбрать родительскую папку" }),
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Заполните «Название проекта»",
    );
    expect(value.createProject).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Название проекта"), "Test");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect(value.createProject).toHaveBeenCalledWith({
      projectRoot: "C:/Projects\\Test",
      displayName: "Test",
      compatibilitySourceId: "default",
    });
  });

  it("rejects unsafe project folder names before calling the backend", async () => {
    const value = api({
      chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"),
      createProject: vi.fn(),
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Выбрать родительскую папку" }),
    );
    await userEvent.type(
      screen.getByLabelText("Название проекта"),
      "invalid/name",
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "одной папки Windows",
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect(value.createProject).not.toHaveBeenCalled();
  });

  it("keeps the opened project and creation form when the backend rejects a new project", async () => {
    const value = api({
      chooseProject: vi.fn().mockResolvedValue(emptyProject),
      chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"),
      createProject: vi.fn().mockResolvedValue({
        status: "ERROR",
        error: {
          code: "PROJECT_DESTINATION_EXISTS",
          message: "Destination already exists.",
        },
      }),
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть проект" }),
    );
    expect(await screen.findByText("Проект ещё не настроен")).toBeTruthy();
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Выбрать родительскую папку" }),
    );
    await userEvent.type(
      screen.getByLabelText("Название проекта"),
      "existing-project",
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "PROJECT_DESTINATION_EXISTS",
    );
    expect(screen.getByLabelText("Название проекта")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(screen.getByText("Проект ещё не настроен")).toBeTruthy();
  });

  it("adds a first server as a transient v1alpha3 CreateServer intent", async () => {
    const value = api();
    await openServers(value, emptyProject as unknown as OpenResult);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить сервер" }),
    );
    await userEvent.type(screen.getByLabelText("ID сервера"), "node1");
    await userEvent.selectOptions(
      screen.getByLabelText("Тип сервера"),
      "infra",
    );
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.example.internal",
    );
    await userEvent.type(
      screen.getByLabelText("IP-адрес / DNS-имя"),
      "192.0.2.10",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "CreateServer",
      hostId: "node1",
      type: "infra",
      desiredHostname: "node1.example.internal",
      address: "192.0.2.10",
    });
    expect(screen.getByText("Доступно после первого сохранения")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Изменить" })).toBeNull();
  });

  it("sends explicit port 22 only when the operator chooses it", async () => {
    const value = api();
    await openServers(value, emptyProject as unknown as OpenResult);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить сервер" }),
    );
    await userEvent.type(screen.getByLabelText("ID сервера"), "node1");
    await userEvent.selectOptions(
      screen.getByLabelText("Тип сервера"),
      "infra",
    );
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.example.internal",
    );
    await userEvent.type(
      screen.getByLabelText("IP-адрес / DNS-имя"),
      "192.0.2.10",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("SSH-порт"),
      "explicit",
    );
    await userEvent.clear(screen.getByLabelText("Явный SSH-порт"));
    await userEvent.type(screen.getByLabelText("Явный SSH-порт"), "22");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "CreateServer",
      hostId: "node1",
      type: "infra",
      desiredHostname: "node1.example.internal",
      address: "192.0.2.10",
      sshPort: 22,
    });
  });

  it("emits a deliberately partial UpdateServer and preserves omitted sshPort", async () => {
    const value = api();
    await openServers(value);
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    await userEvent.clear(screen.getByLabelText("Желаемое имя хоста"));
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.changed.internal",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "UpdateServer",
      hostId: "node1",
      desiredHostname: "node1.changed.internal",
    });
  });

  it("keeps explicit, omitted, and clear SSH-port edits distinct", async () => {
    const value = api();
    await openServers(value);
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    expect(
      screen.queryByRole("option", { name: /Наследовать порт/ }),
    ).toBeNull();
    expect(
      screen.getByRole("option", { name: "Убрать переопределение инсталлера" }),
    ).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("SSH-порт"), "clear");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "UpdateServer",
      hostId: "node1",
      clearSSHPort: true,
    });
  });

  it("preserves an unknown configured type when another field changes", async () => {
    const unknown = {
      ...project,
      managed: {
        ...project.managed,
        servers: { node1: { ...project.managed.servers.node1, type: "scada" } },
      },
      snapshot: {
        ...project.snapshot,
        hosts: { node1: { ...project.snapshot.hosts.node1, type: "scada" } },
      },
    };
    const value = api();
    await openServers(value, unknown as unknown as OpenResult);
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    expect(
      screen.getByRole("option", { name: "Неизвестный тип (scada)" }),
    ).toBeTruthy();
    await userEvent.clear(screen.getByLabelText("IP-адрес / DNS-имя"));
    await userEvent.type(
      screen.getByLabelText("IP-адрес / DNS-имя"),
      "192.0.2.11",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "UpdateServer",
      hostId: "node1",
      address: "192.0.2.11",
    });
  });

  it("requires confirmation and emits only generic DeleteServer", async () => {
    const value = api();
    await openServers(value);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
    );
    expect(
      screen.getByText(
        /Связанные сервисы и размещение автоматически не удаляются/,
      ),
    ).toBeTruthy();
    await userEvent.click(
      screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "DeleteServer",
      hostId: "node1",
    });
  });

  it("allows address-only edits when AppConfig is temporarily unavailable", async () => {
    const value = api({
      getApplicationConfig: vi.fn().mockResolvedValue({
        status: "ERROR",
        error: {
          code: "APPLICATION_CONFIG_INVALID",
          message: "Конфигурация приложения недоступна.",
        },
      }),
    });
    await openServers(value);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Конфигурация приложения недоступна.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    expect(screen.getByDisplayValue("infra")).toHaveProperty("readOnly", true);
    await userEvent.clear(screen.getByLabelText("IP-адрес / DNS-имя"));
    await userEvent.type(
      screen.getByLabelText("IP-адрес / DNS-имя"),
      "192.0.2.11",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "UpdateServer",
      hostId: "node1",
      address: "192.0.2.11",
    });
  });

  it("discards a newly created empty session when its first append fails", async () => {
    const value = api({
      appendEditCommand: vi.fn().mockResolvedValue({
        status: "ERROR",
        error: { code: "EDIT_COMMAND_BLOCKED", message: "Blocked" },
      }),
    });
    await openServers(value, emptyProject as unknown as OpenResult);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить сервер" }),
    );
    await userEvent.type(screen.getByLabelText("ID сервера"), "node1");
    await userEvent.selectOptions(
      screen.getByLabelText("Тип сервера"),
      "infra",
    );
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.example.internal",
    );
    await userEvent.type(
      screen.getByLabelText("IP-адрес / DNS-имя"),
      "192.0.2.10",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(value.discardEditSession).toHaveBeenCalledWith(sessionID);
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
  });

  it("saves from a local structural preview and verifies separately", async () => {
    const planID = "abcdef0123456789abcdef0123456789";
    const saved = {
      ...project,
      managed: {
        projectRevision: "sha256:new",
        servers: {
          node1: {
            ...project.managed.servers.node1,
            desiredHostname: "node1.changed.internal",
          },
        },
      },
      verification: { status: "STALE", projectRevision: "sha256:old" },
    };
    const value = api({
      getServiceConfigurationPreview: vi.fn()
        .mockResolvedValueOnce({ projectRevision: "sha256:old", runtimeDigest: "sha256:runtime-a", services: {} })
        .mockImplementation(() => new Promise(() => {})),
      reviewEditSession: vi.fn().mockResolvedValue({
        status: "READY",
        plan: {
          planId: planID,
          saveAllowed: true,
          semanticChanges: [],
          affectedDocuments: [
            {
              logicalPath: "inventory/hosts.yml",
              before: { state: "PRESENT" },
              after: { state: "PRESENT" },
            },
          ],
          impacts: ["Inventory changes require a later apply."],
        },
      }),
      commitEditPlan: vi.fn().mockResolvedValue({
        status: "COMMITTED",
        commit: { status: "COMMITTED", newProjectRevision: "sha256:new" },
        current: saved,
      }),
      verifyProject: vi.fn().mockResolvedValue({
        status: "VERIFIED",
        projectRevision: "sha256:new",
      }),
    });
    await openServers(value);
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    await userEvent.clear(screen.getByLabelText("Желаемое имя хоста"));
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.changed.internal",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Затрагиваемые документы" }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить проект" }),
    );
    expect(await screen.findByText("Проверка устарела")).toBeTruthy();
    expect(await screen.findByText("node1.changed.internal")).toBeTruthy();
    await waitFor(() => expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2));
    for (const name of ["Сервисы", "Приложения", "Установка"])
      expect(screen.getByRole("button", { name })).toHaveProperty("disabled", false);
    await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
    expect(value.verifyProject).toHaveBeenCalledOnce();
    expect(await screen.findByText("Проверено")).toBeTruthy();
  });
});

describe("UI-01F3 deployment editor", () => {
  it("shows each selected service member with its host and opens that member's settings", async () => {
    const value = api();
    await openTopology(value, h3Project as unknown as OpenResult);
    await userEvent.click(screen.getByRole("button", { name: /kafka-main/ }));
    expect(
      screen.getByRole("heading", { name: "Размещение на серверах" }),
    ).toBeTruthy();
    expect(screen.getByText("kafka-kafka-1")).toBeTruthy();
    expect(screen.getByText("kafka-kafka-2")).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", {
        name: "Настроить участника kafka-kafka-2 на сервере node1",
      }),
    );
    expect(
      await screen.findByRole("heading", { name: "Параметры экземпляра" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("region", {
        name: "Параметры выбранного сервиса",
      }),
    ).toBeTruthy();
    expect(
      (screen.getByLabelText("Экземпляр") as HTMLSelectElement).value,
    ).toBe("kafka-kafka-2");
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { name: "Параметры экземпляра" }),
    );
    expect(value.startEditSession).not.toHaveBeenCalled();
  });

  it("opens the exact member settings from Topology by servers", async () => {
    const value = api();
    await openTopology(value, h3Project as unknown as OpenResult);
    await userEvent.click(screen.getByRole("button", { name: "По серверам" }));
    expect(
      screen.getAllByRole("button", { name: /Настроить участника/ }),
    ).toHaveLength(2);
    await userEvent.click(
      screen.getAllByRole("button", { name: /Настроить участника/ })[0],
    );
    expect(
      (screen.getByLabelText("Экземпляр") as HTMLSelectElement).value,
    ).toBe("kafka-kafka-1");
    expect(value.startEditSession).not.toHaveBeenCalled();
  });

  it("opens Topology and renders saved deployments with a ready Core projection", async () => {
    const value = api();
    await openTopology(value);
    expect(
      await screen.findByRole("heading", { name: "Топология" }),
    ).toBeTruthy();
    expect(screen.getAllByText("kafka-main").length).toBeGreaterThan(0);
    expect(screen.getByText("Apache Kafka (kafka)")).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Настроить экземпляр" }),
    );
    const detailHeading = await screen.findByRole("heading", {
      name: "Настройка сервиса",
    });
    expect(document.activeElement).toBe(detailHeading);
    expect(screen.getByRole("heading", { name: "Сервисы" })).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: /^kafka-main/ })
        .getAttribute("aria-current"),
    ).toBe("page");
    expect(
      screen.getByRole("region", {
        name: "Параметры выбранного сервиса",
      }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Скрыть настройки" }),
    );
    const listHeading = await screen.findByRole("heading", {
      name: "Сервисы",
    });
    expect(document.activeElement).toBe(listHeading);
    expect(value.getExecutionNodeContext).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Проект" }));
    expect(
      screen.getByText("Развёртывания").parentElement?.querySelector("strong")
        ?.textContent,
    ).toBe("1");
  });

  it("appends one catalog-backed Create intent and selects the new deployment", async () => {
    const value = api();
    await openTopology(value);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    );
    await userEvent.type(
      screen.getByLabelText("Технический ID экземпляра сервиса"),
      "kafka-extra",
    );
    await userEvent.selectOptions(screen.getByLabelText("Режим"), "single");
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "CreateServiceDeployment",
      deploymentId: "kafka-extra",
      serviceType: "kafka",
      mode: "single",
    });
    expect(await screen.findByText("Новый черновик")).toBeTruthy();
    expect(screen.getByText("1 / 16 изменений")).toBeTruthy();
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce();
    for (const name of ["Сервисы", "Приложения"]) {
      expect(screen.getByRole("button", { name })).toHaveProperty("disabled", false);
    }
    expect(
      screen.getByRole("button", { name: "Удалить экземпляр" }),
    ).toHaveProperty("disabled", true);
  });

  it("keeps the pending saved Core projection when topology adds a draft", async () => {
    let complete!: (value: unknown) => void;
    const value = api({
      getServiceConfigurationPreview: vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            complete = resolve;
          }),
      ),
    });
    await openTopology(value);
    await waitFor(() =>
      expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    );
    await userEvent.type(
      screen.getByLabelText("Технический ID экземпляра сервиса"),
      "kafka-extra",
    );
    await userEvent.selectOptions(screen.getByLabelText("Режим"), "single");
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(value.appendEditCommand).toHaveBeenCalledOnce();
    await act(async () =>
      complete({
        projectRevision: "sha256:old",
        runtimeDigest: "sha256:runtime-a",
        services: {},
      }),
    );
    for (const name of ["Сервисы", "Приложения"]) {
      expect(screen.getByRole("button", { name })).toHaveProperty(
        "disabled",
        false,
      );
    }
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce();
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("rejects a duplicate deployment ID before calling the backend", async () => {
    const value = api();
    await openTopology(value);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    );
    await userEvent.type(
      screen.getByLabelText("Технический ID экземпляра сервиса"),
      "kafka-main",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Deployment с таким ID уже есть",
    );
    expect(value.startEditSession).not.toHaveBeenCalled();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
  });

  it("keeps guarded Delete available when the exact catalog is unavailable", async () => {
    const unavailable = {
      ...project,
      catalog: {
        status: "UNAVAILABLE",
        expectedBundleDigest: "sha256:bundle",
        expectedCatalogDigest: "sha256:catalog",
        error: { code: "CATALOG_UNAVAILABLE", message: "Catalog unavailable" },
      },
    };
    const value = api();
    await openTopology(value, unavailable as unknown as OpenResult);
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    await userEvent.click(
      screen.getByRole("button", { name: "Удалить экземпляр" }),
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Удалить экземпляр" }).at(-1)!,
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "DeleteServiceDeployment",
      deploymentId: "kafka-main",
    });
  });

  it("shares one EditSession and command count between Servers and Topology", async () => {
    const value = api({
      appendEditCommand: vi
        .fn()
        .mockResolvedValueOnce({
          status: "EDITING",
          session: { sessionId: sessionID, commandCount: 1 },
        })
        .mockResolvedValueOnce({
          status: "EDITING",
          session: { sessionId: sessionID, commandCount: 2 },
        }),
    });
    await openServers(value);
    await userEvent.click(screen.getByRole("button", { name: "Изменить" }));
    await userEvent.clear(screen.getByLabelText("Желаемое имя хоста"));
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.changed.internal",
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await userEvent.click(screen.getByRole("button", { name: "Топология" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    );
    await userEvent.type(
      screen.getByLabelText("Технический ID экземпляра сервиса"),
      "kafka-extra",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(value.startEditSession).toHaveBeenCalledOnce();
    expect(value.appendEditCommand).toHaveBeenLastCalledWith(sessionID, {
      operation: "CreateServiceDeployment",
      deploymentId: "kafka-extra",
      serviceType: "kafka",
      mode: "kraft",
    });
    expect(screen.getByText("2 / 16 изменений")).toBeTruthy();
  });

  it("treats COMMITTED_REFRESH_FAILED as committed and recovers only by reopen", async () => {
    const planID = "abcdef0123456789abcdef0123456789";
    const invalidated = {
      ...project,
      managed: undefined,
      snapshot: undefined,
      verification: { status: "UNVERIFIED" },
    };
    const refreshed = {
      ...project,
      managed: {
        ...project.managed,
        projectRevision: "sha256:new",
        deployments: {
          "kafka-main": project.managed.deployments["kafka-main"],
          "kafka-extra": {
            deploymentId: "kafka-extra",
            serviceType: "kafka",
            mode: "kraft",
          },
        },
      },
    };
    const value = api({
      reviewEditSession: vi.fn().mockResolvedValue({
        status: "READY",
        plan: {
          planId: planID,
          saveAllowed: true,
          semanticChanges: [],
          affectedDocuments: [],
        },
      }),
      commitEditPlan: vi.fn().mockResolvedValue({
        status: "COMMITTED_REFRESH_FAILED",
        commit: {
          status: "COMMITTED_REFRESH_FAILED",
          newProjectRevision: "sha256:new",
        },
        current: invalidated,
      }),
      openProject: vi
        .fn()
        .mockResolvedValueOnce({
          status: "ERROR",
          error: { code: "PROJECT_CHANGED", message: "Project changed" },
        })
        .mockResolvedValueOnce(refreshed),
    });
    await openTopology(value);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    );
    await userEvent.type(
      screen.getByLabelText("Технический ID экземпляра сервиса"),
      "kafka-extra",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить проект" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Проект сохранён, но текущее представление не обновлено",
      }),
    ).toBeTruthy();
    expect(screen.queryByText("kafka-main")).toBeNull();
    expect(screen.queryByText("kafka-extra")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
    expect(value.commitEditPlan).toHaveBeenCalledOnce();

    await userEvent.click(
      screen.getByRole("button", { name: "Обновить проект" }),
    );
    expect(value.openProject).toHaveBeenCalledWith("C:/Projects/test");
    expect(await screen.findByText("Project changed")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(value.commitEditPlan).toHaveBeenCalledOnce();

    await userEvent.click(
      screen.getByRole("button", { name: "Обновить проект" }),
    );
    expect((await screen.findAllByText("kafka-extra")).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", false);
    expect(value.commitEditPlan).toHaveBeenCalledOnce();
  });

  it("does not offer Review retry for EDIT_COMMAND_CONFLICT", async () => {
    const value = api({
      reviewEditSession: vi.fn().mockResolvedValue({
        status: "BLOCKED",
        error: {
          code: "EDIT_COMMAND_CONFLICT",
          message: "Conflicting deployment lifecycle intents",
        },
      }),
    });
    await openTopology(value);
    await userEvent.click(
      screen.getByRole("button", { name: "Удалить экземпляр" }),
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Удалить экземпляр" }).at(-1)!,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    expect(await screen.findByText("EDIT_COMMAND_CONFLICT")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Повторить проверку" }),
    ).toBeNull();
    expect(
      screen.getAllByRole("button", { name: "Отменить все изменения" }).length,
    ).toBeGreaterThan(0);
  });
});

describe("UI-01H2 services navigation and safe settings", () => {
  it("shows an immutable bundled default before READY without Verify or editing", async () => {
    const withDefault = {
      ...project,
      catalog: {
        ...project.catalog,
        services: project.catalog.services.map((service) => ({
          ...service,
          configurationSettings: service.configurationSettings.map((setting) =>
            setting.id === "replicaCount"
              ? {
                  ...setting,
                  staticDefaultState: "LITERAL",
                  staticDefaultValue: 3,
                }
              : setting,
          ),
        })),
      },
    };
    const value = api();
    value.chooseProject.mockResolvedValue(withDefault);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(screen.getByText("По умолчанию: 3")).toBeTruthy();
    expect(
      screen.getByRole("spinbutton", { name: "Количество реплик" }),
    ).toHaveProperty("value", "3");
    expect(screen.getByRole("button", { name: "Применить" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(value.verifyProject).not.toHaveBeenCalled();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
  });

  it("shows READY Core value and source without invoking Verify", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: "sha256:runtime-a",
      }),
      getServiceConfigurationPreview: vi.fn().mockResolvedValue({
        projectRevision: "sha256:old",
        runtimeDigest: "sha256:runtime-a",
        services: {
          "kafka-main": {
            configuration: {
              replicaCount: {
                state: "RESOLVED",
                source: "ROLE_DEFAULT",
                value: 5,
              },
            },
            members: {},
          },
        },
      }),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();
    expect(
      screen.getByText(
        "Значения получены из Core для текущей сохранённой ревизии. Это не проверка проекта.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("spinbutton", { name: "Количество реплик" }),
    ).toHaveProperty("value", "5");
    expect(screen.getByRole("button", { name: "Применить" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce();
    expect(value.verifyProject).not.toHaveBeenCalled();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
  });

  it("retries failed projection explicitly and reuses a successful revision", async () => {
    const value = api({
      createInstallationPlan: vi.fn(),
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: "sha256:runtime-a",
      }),
      getServiceConfigurationPreview: vi
        .fn()
        .mockRejectedValueOnce(
          new Error("SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED"),
        )
        .mockResolvedValue({
          projectRevision: "sha256:old",
          runtimeDigest: "sha256:runtime-a",
          services: {
            "kafka-main": {
              configuration: {
                replicaCount: {
                  state: "RESOLVED",
                  source: "ROLE_DEFAULT",
                  value: 5,
                },
              },
              members: {},
            },
          },
        }),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await screen.findByText(/Код: SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED/);
    for (const name of ["Сервисы", "Приложения", "Установка"])
      expect(screen.getByRole("button", { name })).toHaveProperty(
        "disabled",
        true,
      );
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить узел" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /^Серверы$/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Сервисы$/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2);
    expect(value.verifyProject).not.toHaveBeenCalled();
    expect(value.createInstallationPlan).not.toHaveBeenCalled();
  });

  it("blocks dependent sections until the automatic saved Core projection arrives", async () => {
    let complete!: (value: unknown) => void;
    const value = api({
      getServiceConfigurationPreview: vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            complete = resolve;
          }),
      ),
      createInstallationPlan: vi.fn(),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await waitFor(() =>
      expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce(),
    );
    for (const name of ["Сервисы", "Приложения", "Установка"]) {
      expect(screen.getByRole("button", { name })).toHaveProperty(
        "disabled",
        true,
      );
    }
    expect(screen.getByText(/Тайм-аут запроса — 90 секунд/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Получение данных Core…");
    expect(screen.getAllByText("Получение данных Core…")).toHaveLength(2);
    await act(async () =>
      complete({
        projectRevision: "sha256:old",
        runtimeDigest: "sha256:runtime-a",
        services: {},
      }),
    );
    for (const name of ["Сервисы", "Приложения", "Установка"]) {
      expect(screen.getByRole("button", { name })).toHaveProperty(
        "disabled",
        false,
      );
    }
    expect(value.verifyProject).not.toHaveBeenCalled();
    expect(value.createInstallationPlan).not.toHaveBeenCalled();
  });

  it("keeps admitted pages mounted and reachable during a new revision preview and after its failure", async () => {
    let complete!: (result: unknown) => void;
    const value = api({
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
      getServiceConfigurationPreview: vi.fn()
        .mockResolvedValueOnce({ projectRevision: "sha256:old", runtimeDigest: "sha256:runtime-a", services: {
          "kafka-main": { configuration: { replicaCount: { state: "RESOLVED", source: "ROLE_DEFAULT", value: 5 } }, members: {} },
        } })
        .mockImplementation(() => new Promise((resolve) => { complete = resolve; })),
      verifyProject: vi.fn().mockResolvedValue({ status: "VERIFIED", projectRevision: "sha256:new" }),
      getCurrentProject: vi.fn().mockResolvedValue({ ...project, managed: { ...project.managed, projectRevision: "sha256:new" } }),
      createInstallationPlan: vi.fn(),
    });
    await openServers(value);
    await waitFor(() => expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty("disabled", false));
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
    await waitFor(() => expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("heading", { name: "Параметры сервиса" })).toBeTruthy();
    expect(screen.queryByText("По умолчанию: 5")).toBeNull();
    for (const name of ["Сервисы", "Приложения", "Установка"])
      expect(screen.getByRole("button", { name })).toHaveProperty("disabled", false);
    await act(async () => complete({ diagnostic: { Code: "CORE_OPERATION_FAILED", SafeMessage: "Core operation failed" } }));
    expect(screen.getByRole("heading", { name: "Параметры сервиса" })).toBeTruthy();
    expect(screen.getAllByText(/Код: CORE_OPERATION_FAILED/).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Приложения" }));
    expect(screen.getByRole("heading", { name: "Приложения" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Установка" }));
    expect(screen.getByRole("heading", { name: "Установка" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Открыть установку:/ })).toHaveProperty("disabled", false);
    expect(value.createInstallationPlan).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await userEvent.click(screen.getByRole("button", { name: "Проверить узел" }));
    await waitFor(() => expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(3));
    await act(async () => complete({ projectRevision: "sha256:new", runtimeDigest: "sha256:runtime-a", services: {
      "kafka-main": { configuration: { replicaCount: { state: "RESOLVED", source: "ROLE_DEFAULT", value: 7 } }, members: {} },
    } }));
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    expect(await screen.findByText("По умолчанию: 7")).toBeTruthy();
    expect(screen.queryByText("По умолчанию: 5")).toBeNull();
  });

  it("requires the first successful projection again when another project is opened", async () => {
    const value = api({ getServiceConfigurationPreview: vi.fn()
      .mockResolvedValueOnce({ projectRevision: "sha256:old", runtimeDigest: "sha256:runtime-a", services: {} })
      .mockImplementation(() => new Promise(() => {})) });
    value.chooseProject.mockResolvedValueOnce(project)
      .mockResolvedValueOnce({ ...project, root: "C:/Projects/another" });
    render(<App api={value} />);
    await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty("disabled", false));
    await userEvent.click(screen.getByRole("button", { name: "Открыть проект" }));
    await waitFor(() => expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2));
    for (const name of ["Сервисы", "Приложения", "Установка"])
      expect(screen.getByRole("button", { name })).toHaveProperty("disabled", true);
  });

  it("keeps sections blocked on a stale Core projection and offers a retry", async () => {
    const value = api({
      getServiceConfigurationPreview: vi.fn().mockResolvedValue({
        projectRevision: "sha256:another",
        runtimeDigest: "sha256:runtime-a",
        services: {},
      }),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await screen.findByText(/Core вернул проекцию другой ревизии/);
    for (const name of ["Сервисы", "Приложения", "Установка"]) {
      expect(screen.getByRole("button", { name })).toHaveProperty(
        "disabled",
        true,
      );
    }
    expect(screen.getByRole("button", { name: "Проверить узел" })).toBeTruthy();
  });

  it("keeps gated pages blocked when the READY Core projection is unavailable", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: "sha256:runtime-a",
      }),
      getServiceConfigurationPreview: vi
        .fn()
        .mockRejectedValueOnce(
          new Error("SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED"),
        ).mockResolvedValue({ projectRevision: "sha256:old", runtimeDigest: "sha256:runtime-a", services: {} }),
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(
      await screen.findByText(
        /Core-проекция недоступна для текущей сохранённой ревизии.*SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED/,
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Ошибка получения данных Core");
    const errorChips = screen.getAllByText("Ошибка получения данных Core");
    expect(errorChips).toHaveLength(2);
    errorChips.forEach((chip) => expect(chip.classList.contains("status-chip--danger")).toBe(true));
    expect(screen.queryByText("Ожидание данных Core")).toBeNull();
    expect(screen.queryByText("Проверен: Подготовлен")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Проверить узел" }));
    expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();
    expect(screen.getByText("Подготовлен")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Подготовлен");
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("shows the structured Core preview failure without admitting it as a ready projection", async () => {
    const cause = "Этап: загрузка каталога сервисов. Отсутствует обязательный документ.";
    const value = api({ getServiceConfigurationPreview: vi.fn().mockResolvedValue({
      diagnostic: { Code: "PROJECT_SNAPSHOT_INPUT_INVALID", SafeMessage: cause },
    }) });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    expect(await screen.findByText(new RegExp(cause))).toBeTruthy();
    for (const name of ["Сервисы", "Приложения", "Установка"])
      expect(screen.getByRole("button", { name })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Открыть узел выполнения" }).textContent).toContain("Ошибка получения данных Core");
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("does not present an empty READY Core projection as resolved values", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: "sha256:runtime-a",
      }),
      getServiceConfigurationPreview: vi.fn().mockResolvedValue({
        projectRevision: "sha256:old",
        runtimeDigest: "sha256:runtime-a",
        services: {},
      }),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(
      await screen.findByText(
        /Core не вернул разрешённые значения для этого сервиса/,
      ),
    ).toBeTruthy();
    expect(
      screen.queryByText(
        /Значения получены из Core для текущей сохранённой ревизии/,
      ),
    ).toBeNull();
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("explains why READY cannot start Core projection without runtime identity", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({ status: "READY" }),
      getServiceConfigurationPreview: vi.fn(),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(
      await screen.findByText(
        /Core-проекция недоступна: runtime узла выполнения не подтверждён/,
      ),
    ).toBeTruthy();
    expect(value.getServiceConfigurationPreview).not.toHaveBeenCalled();
  });

  it("fills a member field from inherited defaults without saving it until explicit edit", async () => {
    const withMemberDefault = {
      ...h3Project,
      catalog: {
        ...h3Project.catalog,
        services: h3Project.catalog.services.map((service) => ({
          ...service,
          configurationSettings: service.configurationSettings.map((setting) =>
            setting.id === "replicaCount"
              ? {
                  ...setting,
                  scopes: ["deployment", "member"],
                  staticDefaultState: "LITERAL",
                  staticDefaultValue: 3,
                }
              : setting,
          ),
        })),
      },
    };
    const value = api();
    await openTopology(value, withMemberDefault as unknown as OpenResult);
    await userEvent.click(screen.getByRole("button", { name: /kafka-main/ }));
    await userEvent.click(
      screen.getByRole("button", {
        name: "Настроить участника kafka-kafka-2 на сервере node1",
      }),
    );
    const input = screen.getByRole("spinbutton", {
      name: "kafka-kafka-2: Количество реплик",
    });
    const apply = input
      .closest(".services-setting")
      ?.querySelector("button") as HTMLButtonElement;
    expect(input).toHaveProperty("value", "3");
    expect(apply).toHaveProperty("disabled", true);
    expect(value.appendEditCommand).not.toHaveBeenCalled();
    await userEvent.clear(input);
    await userEvent.type(input, "4");
    expect(apply).toHaveProperty("disabled", false);
    expect(value.appendEditCommand).not.toHaveBeenCalled();
    await userEvent.click(apply);
    expect(value.appendEditCommand).toHaveBeenCalledOnce();
  });

  it("hides a previous Core value when the same node switches runtime releases", async () => {
    let activeDigest = "sha256:runtime-a";
    const value = api({
      getExecutionNodeContext: vi.fn().mockImplementation(async () => ({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: activeDigest,
      })),
      checkExecutionNode: vi.fn().mockResolvedValue({ status: "READY" }),
      getServiceConfigurationPreview: vi.fn().mockImplementation(async () => ({
        projectRevision: "sha256:old",
        runtimeDigest: activeDigest,
        services: {
          "kafka-main": {
            configuration: {
              replicaCount: {
                state: "RESOLVED",
                source: "ROLE_DEFAULT",
                value: activeDigest.endsWith("a") ? 5 : 7,
              },
            },
            members: {},
          },
        },
      })),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();

    activeDigest = "sha256:runtime-b";
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить узел" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 7")).toBeTruthy();
    expect(screen.queryByText("По умолчанию: 5")).toBeNull();
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2);
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("accepts the password once while adding its internal reference to the normal draft", async () => {
    const redisProject = {
      ...project,
      managed: {
        ...project.managed,
        deployments: {
          ...project.managed.deployments,
          "redis-main": {
            deploymentId: "redis-main",
            serviceType: "redis",
            mode: "standalone",
          },
        },
      },
      catalog: {
        ...project.catalog,
        services: [
          ...project.catalog.services,
          {
            id: "redis",
            definitionVersion: "1",
            displayName: "Redis",
            category: "Database",
            ui: {},
            endpointConsumer: false,
            endpointProvider: false,
            modes: [
              {
                id: "standalone",
                displayName: "Standalone",
                placementKind: "MEMBER_SCOPED",
                roles: ["redis"],
                guidance: { minParticipants: 1, distinctHosts: false },
              },
            ],
            configurationSettings: [
              {
                id: "redisCredential",
                kind: "MANAGED",
                scopes: ["deployment"],
                editorShape: "RUNTIME_SECRET_REFERENCE_OBJECT",
                runtimeSecretRequirementRef: "redis-password",
              },
              { id: "dataDirectory", label: "Каталог данных", kind: "MANAGED", scopes: ["deployment"],
                editorShape: "BOUNDED_STRING", minLength: 1, maxLength: 255, staticDefaultState: "DEFERRED" },
            ],
          },
        ],
      },
    };
    const getPendingRuntimeSecretDescriptors = vi.fn().mockResolvedValue({
      status: "READY",
      descriptors: [
        {
          requirementRef: "redis-password",
          purpose: "SERVICE_PASSWORD",
          serviceDeployment: "redis-main",
          setting: "redisCredential",
          displayLabel: "Redis password",
          referenceConfigured: false,
          hosts: ["node1"],
        },
      ],
    });
    const setPendingDeploymentRuntimeSecretValues = vi.fn();
    const value = api({
      getPendingRuntimeSecretDescriptors,
      setPendingDeploymentRuntimeSecretValues,
      getServiceConfigurationPreview: vi.fn().mockResolvedValue({ projectRevision: "sha256:old", runtimeDigest: "sha256:runtime-a", services: {
        "redis-main": { configuration: { dataDirectory: { state: "RESOLVED", source: "ROLE_DEFAULT", value: "/data/redis-main" } }, members: {} },
      } }),
    });
    value.chooseProject.mockResolvedValue(redisProject);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^redis-main/ }));
    expect(screen.getByRole("textbox", { name: "Каталог данных" })).toHaveProperty("value", "/data/redis-main");
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    await userEvent.type(
      screen.getByLabelText("Redis password"),
      "not-persisted",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии" }),
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "redis-main",
      scope: "DEPLOYMENT",
      setting: "redisCredential",
      value: { passwordSecretRef: "runtime:redis-password" },
    });
    expect(setPendingDeploymentRuntimeSecretValues).toHaveBeenCalledWith({ serviceDeployment: "redis-main", values: { "redis-password": "not-persisted" } });
    expect(screen.queryByRole("dialog", { name: "Секреты сервиса" })).toBeNull();
    expect(screen.queryByText(/Ссылки добавлены в черновик/)).toBeNull();
    expect(screen.queryByText("not-persisted")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Каталог данных" })).toHaveProperty("value", "/data/redis-main");
    expect(screen.getByText(/Показан расчёт Core для сохранённой версии/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    await userEvent.type(screen.getByLabelText("Redis password"), "replacement-only-in-memory");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить в сессии" }));
    expect(value.appendEditCommand).toHaveBeenCalledOnce();
    expect(setPendingDeploymentRuntimeSecretValues).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("dialog", { name: "Секреты сервиса" })).toBeNull();
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledOnce();
  });

  it("requires the catalog-declared username when adding a runtime secret reference", async () => {
    const usernameProject = {
      ...project,
      catalog: {
        ...project.catalog,
        services: [
          {
            ...project.catalog.services[0],
            configurationSettings: [
              {
                id: "adminSuperuser",
                kind: "MANAGED",
                scopes: ["deployment"],
                label: "Administrator password",
                editorShape: "RUNTIME_SECRET_REFERENCE_OBJECT",
                runtimeSecretRequirementRef: "postgresql-admin-password",
                runtimeSecretUsernameRequired: true,
              },
            ],
          },
        ],
      },
    };
    const value = api({
      getPendingRuntimeSecretDescriptors: vi.fn().mockResolvedValue({
        status: "READY",
        descriptors: [
          {
            requirementRef: "postgresql-admin-password",
            purpose: "SERVICE_PASSWORD",
            serviceDeployment: "kafka-main",
            setting: "adminSuperuser",
            displayLabel: "Administrator password",
            referenceConfigured: false,
            hosts: ["node1"],
          },
        ],
      }),
    });
    value.chooseProject.mockResolvedValue(usernameProject);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    await userEvent.type(
      screen.getByLabelText("Administrator password"),
      "session-only",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии" }),
    );
    expect(
      screen.getByText(
        "Укажите допустимое имя пользователя для этого секрета.",
      ),
    ).toBeTruthy();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
    await userEvent.type(
      screen.getByLabelText("Имя пользователя"),
      "platform_admin",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии" }),
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "kafka-main",
      scope: "DEPLOYMENT",
      setting: "adminSuperuser",
      value: {
        username: "platform_admin",
        passwordSecretRef: "runtime:postgresql-admin-password",
      },
    });
  });

  it("opens one Services list/detail view after Core projection and returns to the list", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    expect(
      await screen.findByRole("heading", { name: "Сервисы" }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(
      await screen.findByRole("heading", { name: "Настройка сервиса" }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Скрыть настройки" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Выберите сервис" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Сервисы" })).toBeTruthy();
    expect(value.getExecutionNodeContext).toHaveBeenCalled();
  });

  it("imports typed service secret files through Go without exposing paths or values", async () => {
    const value = api({
      getPendingRuntimeSecretDescriptors: vi.fn().mockResolvedValue({
        status: "READY",
        descriptors: [
          {
            requirementRef: "vault-admin-token",
            purpose: "SERVICE_ADMIN_TOKEN",
            serviceDeployment: "kafka-main",
            displayLabel: "Administrative token",
            requiredWhen: "INITIALIZED",
            operations: ["SERVICE_APPLY", "SERVICE_VERIFY"],
            hosts: ["node1"],
          },
        ],
      }),
      choosePendingDeploymentRuntimeSecretFile: vi
        .fn()
        .mockResolvedValue("STORED"),
    });
    value.chooseProject.mockResolvedValue({
      ...project,
      catalog: {
        ...project.catalog,
        services: project.catalog.services.map((service) => ({
          ...service,
          secretInputs: [
            {
              requirementRef: "vault-admin-token",
              purpose: "SERVICE_ADMIN_TOKEN",
              displayLabel: "Administrative token",
              requiredWhen: "INITIALIZED",
              operations: ["SERVICE_APPLY", "SERVICE_VERIFY"],
            },
          ],
        })),
      },
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    await userEvent.type(
      screen.getByLabelText(/Пароль файла age/),
      "temporary-input-password",
    );
    await userEvent.click(screen.getByRole("button", { name: "Выбрать файл" }));
    expect(value.choosePendingDeploymentRuntimeSecretFile).toHaveBeenCalledWith(
      {
        serviceDeployment: "kafka-main",
        purpose: "SERVICE_ADMIN_TOKEN",
        encryptionPassword: "temporary-input-password",
      },
    );
    expect(
      screen.getByText("Файл принят и сохранён только в сессии."),
    ).toBeTruthy();
    expect(value.getExecutionNodeContext).toHaveBeenCalled();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
  });

  it("adds one deployment-scoped safe setting command through the shared session", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.type(screen.getByRole("spinbutton"), "3");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(value.startEditSession).toHaveBeenCalledOnce();
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "kafka-main",
      scope: "DEPLOYMENT",
      setting: "replicaCount",
      value: 3,
    });
    expect(screen.getByRole("button", { name: "Применить" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByText("Изменений в черновике: 1 из 16")).toBeTruthy();
    expect(
      screen.getByText(
        "Этот параметр доступен только для просмотра в текущем интерфейсе.",
      ),
    ).toBeTruthy();
  });

  it("edits a catalog-declared service data root through the shared session", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue({
      ...project,
      managed: {
        ...project.managed,
        deployments: {
          "qa-redis": {
            deploymentId: "qa-redis",
            serviceType: "redis",
            mode: "standalone",
          },
        },
      },
      catalog: {
        ...project.catalog,
        services: [
          {
            ...project.catalog.services[0],
            id: "redis",
            displayName: "Redis",
            configurationSettings: [
              {
                id: "dataRoot",
                kind: "MANAGED",
                scopes: ["deployment"],
                label: "Корневой каталог данных",
                editorShape: "BOUNDED_STRING",
                minLength: 1,
                maxLength: 255,
                staticDefaultState: "LITERAL",
                staticDefaultValue: "/var/lib/platform-redis",
              },
            ],
          },
        ],
      },
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^qa-redis/ }));
    const field = screen.getByRole("textbox", {
      name: "Корневой каталог данных",
    });
    expect(field).toHaveProperty("value", "/var/lib/platform-redis");
    await userEvent.clear(field);
    await userEvent.type(field, "/mnt/data/redis");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "qa-redis",
      scope: "DEPLOYMENT",
      setting: "dataRoot",
      value: "/mnt/data/redis",
    });
  });

  it("clears unapplied service form input when the shared draft is discarded", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    let field = screen.getByRole("spinbutton", { name: "Количество реплик" });
    await userEvent.type(field, "3");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    await userEvent.clear(field);
    await userEvent.type(field, "4");
    expect(field).toHaveProperty("value", "4");
    await userEvent.click(
      screen.getByRole("button", { name: "Отменить черновик" }),
    );
    expect(value.discardEditSession).toHaveBeenCalledWith(sessionID);
    field = screen.getByRole("spinbutton", { name: "Количество реплик" });
    expect(field).toHaveProperty("value", "");
    expect(screen.getByRole("button", { name: "Применить" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(value.commitEditPlan).not.toHaveBeenCalled();
  });

  it("lets an operator amend or reset an applied unsaved setting without touching other draft commands", async () => {
    const withDefault = {
      ...project,
      catalog: {
        ...project.catalog,
        services: project.catalog.services.map((service) => ({
          ...service,
          configurationSettings: service.configurationSettings.map((setting) =>
            setting.id === "replicaCount"
              ? {
                  ...setting,
                  staticDefaultState: "LITERAL",
                  staticDefaultValue: 3,
                }
              : setting,
          ),
        })),
      },
    };
    const value = api({
      amendServiceConfigurationDraft: vi
        .fn()
        .mockImplementation(
          async (
            _session: string,
            _index: number,
            _old: unknown,
            next: unknown,
          ) =>
            next === null
              ? { status: "DISCARDED" }
              : {
                  status: "EDITING",
                  session: { sessionId: sessionID, commandCount: 1 },
                },
        ),
    });
    value.chooseProject.mockResolvedValue(withDefault);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    const field = screen.getByRole("spinbutton", { name: "Количество реплик" });
    const apply = screen.getByRole("button", { name: "Применить" });
    const reset = screen.getByRole("button", { name: "Сбросить" });
    expect(field).toHaveProperty("value", "3");
    expect(apply).toHaveProperty("disabled", true);
    expect(reset).toHaveProperty("disabled", true);
    await userEvent.clear(field);
    await userEvent.type(field, "4");
    await userEvent.click(apply);
    expect(field).toHaveProperty("value", "4");
    expect(field).toHaveProperty("disabled", false);
    expect(reset).toHaveProperty("disabled", false);
    await userEvent.clear(field);
    await userEvent.type(field, "5");
    await userEvent.click(apply);
    expect(value.amendServiceConfigurationDraft).toHaveBeenCalledWith(
      sessionID,
      0,
      {
        operation: "SetServiceConfigurationValue",
        deploymentId: "kafka-main",
        scope: "DEPLOYMENT",
        setting: "replicaCount",
        value: 4,
      },
      {
        operation: "SetServiceConfigurationValue",
        deploymentId: "kafka-main",
        scope: "DEPLOYMENT",
        setting: "replicaCount",
        value: 5,
      },
    );
    expect(screen.getByText("Изменений в черновике: 1 из 16")).toBeTruthy();
    await userEvent.click(reset);
    expect(value.amendServiceConfigurationDraft).toHaveBeenLastCalledWith(
      sessionID,
      0,
      {
        operation: "SetServiceConfigurationValue",
        deploymentId: "kafka-main",
        scope: "DEPLOYMENT",
        setting: "replicaCount",
        value: 5,
      },
      null,
    );
    const resetField = screen.getByRole("spinbutton", {
      name: "Количество реплик",
    });
    const resetApply = screen.getByRole("button", { name: "Применить" });
    expect(resetField).toHaveProperty("value", "3");
    expect(resetApply).toHaveProperty("disabled", true);
    expect(value.appendEditCommand).toHaveBeenCalledTimes(1);
    expect(value.commitEditPlan).not.toHaveBeenCalled();
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
    await userEvent.clear(resetField);
    await userEvent.type(resetField, "6");
    await userEvent.click(resetApply);
    expect(value.startEditSession).toHaveBeenCalledTimes(2);
    expect(value.appendEditCommand).toHaveBeenCalledTimes(2);
  });

  it("keeps saved override identity read-only when the exact catalog is unavailable", async () => {
    const unavailable = {
      ...project,
      managed: {
        ...project.managed,
        deployments: {
          ...project.managed.deployments,
          "kafka-main": {
            ...project.managed.deployments["kafka-main"],
            configuration: [
              {
                setting: "unknownSetting",
                overridePresent: true,
                state: "UNKNOWN",
                value: "must-not-be-rendered",
              },
            ],
          },
        },
      },
      catalog: {
        status: "UNAVAILABLE",
        expectedBundleDigest: "sha256:bundle",
        expectedCatalogDigest: "sha256:catalog",
      },
    };
    const value = api();
    value.chooseProject.mockResolvedValue(unavailable);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("unknownSetting")).toBeTruthy();
    expect(screen.queryByText("must-not-be-rendered")).toBeNull();
    expect(
      screen.getByRole("textbox", { name: "Поиск сервисов" }),
    ).toBeTruthy();
    expect(screen.getAllByRole("textbox")).toHaveLength(1);
    expect(value.startEditSession).not.toHaveBeenCalled();
  });

  it("uses a trusted deployment selector for a service-deployment reference", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(dnsClientReferenceProject);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(
      screen.getByRole("button", { name: /^dns-client-main/ }),
    );
    const select = screen.getByLabelText("Authoritative DNS deployment");
    expect((select as HTMLSelectElement).options).toHaveLength(4);
    await userEvent.selectOptions(select, "bind-main");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "dns-client-main",
      scope: "DEPLOYMENT",
      setting: "dnsServerRef",
      value: "bind-main",
    });
  });
});

describe("UI-01H3 member settings and TLS navigation", () => {
  it("shows a safe inherited TLS ID even when no managed profile option matches", async () => {
    const withoutMatchingProfile = {
      ...h3Project,
      managed: {
        ...h3Project.managed,
        pki: { ...h3Project.managed.pki, tlsProfiles: {} },
      },
      catalog: {
        ...h3Project.catalog,
        services: h3Project.catalog.services.map((service) => ({
          ...service,
          configurationSettings: service.configurationSettings.map((setting) =>
            setting.id === "tlsProfile"
              ? {
                  ...setting,
                  staticDefaultState: "LITERAL",
                  staticDefaultValue: "infrastructure-tls",
                }
              : setting,
          ),
        })),
      },
    };
    const value = api();
    value.chooseProject.mockResolvedValue(withoutMatchingProfile);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    const deployment = screen.getByLabelText(
      "TLS profile",
    ) as HTMLSelectElement;
    expect(deployment.value).toBe("infrastructure-tls");
    expect(deployment.selectedOptions[0].disabled).toBe(true);
    expect(
      screen.getAllByText("По умолчанию: infrastructure-tls"),
    ).toHaveLength(2);
    expect(value.appendEditCommand).not.toHaveBeenCalled();
    await userEvent.selectOptions(
      screen.getByLabelText("Экземпляр"),
      "kafka-kafka-1",
    );
    const member = screen.getByLabelText(
      "kafka-kafka-1: TLS profile",
    ) as HTMLSelectElement;
    expect(member.value).toBe("infrastructure-tls");
    expect(member.selectedOptions[0].disabled).toBe(true);
  });

  it("uses the composite deployment/member target for a trusted member TLS override", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(h3Project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.selectOptions(
      screen.getByLabelText("Экземпляр"),
      "kafka-kafka-2",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("kafka-kafka-2: TLS profile"),
      "infrastructure-tls",
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Применить" }).at(-1)!,
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "SetServiceConfigurationValue",
      deploymentId: "kafka-main",
      scope: "MEMBER",
      memberId: "kafka-kafka-2",
      setting: "tlsProfile",
      value: "infrastructure-tls",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Экземпляр"),
      "kafka-kafka-1",
    );
    expect(
      (screen.getByLabelText("kafka-kafka-1: TLS profile") as HTMLSelectElement)
        .disabled,
    ).toBe(false);
  });

  it("returns from Certificates to the same selected Services member without starting a session", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(h3Project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.selectOptions(
      screen.getByLabelText("Экземпляр"),
      "kafka-kafka-2",
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Настроить сертификаты" }).at(-1)!,
    );
    expect(
      await screen.findByRole("heading", { name: "Сертификаты" }),
    ).toBeTruthy();
    expect(value.startEditSession).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Вернуться к настройке сервиса" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Настройка сервиса" }),
    ).toBeTruthy();
    expect(
      (screen.getByLabelText("Экземпляр") as HTMLSelectElement).value,
    ).toBe("kafka-kafka-2");
  });

  it("removes a member override through the same exact composite target", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue({
      ...h3Project,
      managed: {
        ...h3Project.managed,
        memberPlacements: h3Project.managed!.memberPlacements.map((member) =>
          member.memberId === "kafka-kafka-1"
            ? {
                ...member,
                configuration: [
                  {
                    setting: "tlsProfile",
                    overridePresent: true,
                    state: "EDITABLE" as const,
                    value: "infrastructure-tls",
                  },
                ],
              }
            : member,
        ),
      },
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Сервисы" })).toHaveProperty(
        "disabled",
        false,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    await userEvent.click(
      screen.getAllByRole("button", { name: "Сбросить" }).at(-1)!,
    );
    expect(value.appendEditCommand).toHaveBeenCalledWith(sessionID, {
      operation: "RemoveServiceConfigurationOverride",
      deploymentId: "kafka-main",
      scope: "MEMBER",
      memberId: "kafka-kafka-1",
      setting: "tlsProfile",
    });
  });
});

describe("UI-TEST-01 F4 placement acceptance", () => {
  it("saves, reopens and clears member- and host-scoped placement through the public backend", async () => {
    const { value, appended } = f4AcceptanceBackend();
    render(<App api={value} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Топология" }));
    await userEvent.click(
      screen.getAllByRole("button", { name: /kafka-main/ })[0],
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Добавить размещение" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить узел сервиса" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить узел сервиса" }),
    );
    expect(
      (screen.getByLabelText("Member ID 1") as HTMLInputElement).value,
    ).toBe("kafka-1");
    expect(
      (screen.getByLabelText("Member ID 2") as HTMLInputElement).value,
    ).toBe("kafka-2");
    await userEvent.selectOptions(
      screen.getAllByLabelText("Роли")[0],
      "broker",
    );
    await userEvent.selectOptions(
      screen.getAllByLabelText("Роли")[1],
      "controller",
    );
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(appended).toEqual([
      {
        operation: "ReconcileDeploymentPlacement",
        deploymentId: "kafka-main",
        members: [
          { memberId: "kafka-1", hostId: "node1", roles: ["broker"] },
          { memberId: "kafka-2", hostId: "node1", roles: ["controller"] },
        ],
      },
    ]);

    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Сохранить проект" }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Проект" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Закрыть проект" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Топология" }));
    await userEvent.click(
      screen.getAllByRole("button", { name: /kafka-main/ })[0],
    );
    expect(
      screen.getByRole("button", { name: "Изменить размещение" }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "По серверам" }));
    await userEvent.selectOptions(
      screen.getByLabelText("Deployment для размещения"),
      "agent-main",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить сервер" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(screen.getByLabelText("Приоритет 1")).toBeTruthy();
    expect(appended).toHaveLength(1);
    await userEvent.clear(screen.getByLabelText("Приоритет 1"));
    await userEvent.type(screen.getByLabelText("Приоритет 1"), "120");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(appended.at(-1)).toEqual({
      operation: "ReconcileHostScopedDeploymentPlacement",
      deploymentId: "agent-main",
      hosts: [{ hostId: "node1", roles: [], priority: 120 }],
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Сохранить проект" }),
    );

    await userEvent.selectOptions(
      screen.getByLabelText("Deployment для размещения"),
      "agent-role-main",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить сервер" }),
    );
    await userEvent.clear(screen.getByLabelText("Приоритет 1"));
    await userEvent.type(screen.getByLabelText("Приоритет 1"), "121");
    await userEvent.selectOptions(screen.getByLabelText("Роли"), "observer");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(appended.at(-1)).toEqual({
      operation: "ReconcileHostScopedDeploymentPlacement",
      deploymentId: "agent-role-main",
      hosts: [{ hostId: "node1", roles: ["observer"], priority: 121 }],
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Сохранить проект" }),
    );

    await userEvent.click(screen.getByRole("button", { name: "По сервисам" }));
    await userEvent.click(
      screen.getAllByRole("button", { name: /agent-main/ })[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Изменить размещение" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(appended.at(-1)).toEqual({
      operation: "ReconcileHostScopedDeploymentPlacement",
      deploymentId: "agent-main",
      hosts: [],
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Просмотреть изменения" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Сохранить проект" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Проект" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Закрыть проект" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Топология" }));

    expect(
      screen.getByRole("button", { name: "Добавить размещение" }),
    ).toBeTruthy();
    expect(appended).toHaveLength(4);
  });
});

describe("UI-01I2 project export", () => {
  it("previews before publishing a full portable configuration", async () => {
    const value = api({
      chooseProjectExportParent: vi.fn().mockResolvedValue("C:/Exports"),
      planProjectExport: vi.fn().mockResolvedValue({
        status: "READY",
        plan: {
          planDigest: "sha256:plan",
          sourceProjectRevision: "sha256:project",
          destinationRoot: "C:/Exports/portable-project",
          documents: [
            { logicalPath: "project.yml", size: 20, digest: "sha256:file" },
          ],
          aggregateSize: 20,
          excludedCategories: ["RUNTIME_CREDENTIALS", "LOGS"],
        },
      }),
      commitProjectExport: vi.fn().mockResolvedValue({
        status: "EXPORTED",
        result: {
          status: "EXPORTED",
          destinationRoot: "C:/Exports/portable-project",
        },
      }),
    });
    value.chooseProject.mockResolvedValue(project);
    value.openProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть проект" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Экспортировать проект" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Выбрать" }));
    await userEvent.type(
      screen.getByLabelText("Имя проекта и новой папки"),
      "portable-project",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить состав" }),
    );
    expect(value.planProjectExport).toHaveBeenCalledWith(
      "C:/Exports",
      "portable-project",
    );
    expect(await screen.findByText("C:/Exports/portable-project")).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Экспортировать" }),
    );
    expect(value.commitProjectExport).toHaveBeenCalledWith("sha256:plan");
    expect(await screen.findByText(/Экспорт завершён/)).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть экспортированный проект" }),
    );
    expect(value.openProject).toHaveBeenCalledWith(
      "C:/Exports/portable-project",
    );
  });
});

it("shows the specific blocking references for REFERENCE_IN_USE in Review", async () => {
  const safeMessage =
    "Нельзя удалить экземпляр: он всё ещё размещён — «qa-clickhouse»: узел node1, участник clickhouse-1. Сначала удалите эти размещения и повторите проверку.";
  const value = api({
    reviewEditSession: vi.fn().mockResolvedValue({
      status: "BLOCKED",
      plan: {
        saveAllowed: false,
        finding: {
          code: "REFERENCE_IN_USE",
          safeMessage,
        },
      },
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Просмотреть изменения" }),
  );
  expect(await screen.findByText(safeMessage)).toBeTruthy();
});

it("shows the endpoint consumer blocking group deletion in Review", async () => {
  const safeMessage =
    "Нельзя удалить группу endpoint: «edge» назначена потребителю «qa-vault-consumer». Сначала очистите эти назначения и повторите проверку.";
  const value = api({
    reviewEditSession: vi.fn().mockResolvedValue({
      status: "BLOCKED",
      plan: {
        saveAllowed: false,
        finding: { code: "REFERENCE_IN_USE", safeMessage },
      },
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Просмотреть изменения" }),
  );
  expect(await screen.findByText(safeMessage)).toBeTruthy();
});

it("shows a Russian explanation for INVALID_VALUE in Review", async () => {
  const value = api({
    reviewEditSession: vi.fn().mockResolvedValue({
      status: "BLOCKED",
      plan: {
        saveAllowed: false,
        finding: {
          code: "INVALID_VALUE",
          safeMessage:
            "Configuration value does not match the catalog descriptor",
        },
      },
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Просмотреть изменения" }),
  );
  expect(
    await screen.findByText("Значение не соответствует ограничениям каталога."),
  ).toBeTruthy();
  expect(
    screen.queryByText(
      "Configuration value does not match the catalog descriptor",
    ),
  ).toBeNull();
});

it("explains NO_CHANGE and does not offer a redundant review retry", async () => {
  const value = api({
    reviewEditSession: vi.fn().mockResolvedValue({
      status: "NO_CHANGE",
      plan: {
        status: "NO_CHANGE",
        saveAllowed: false,
        semanticChanges: [],
        affectedDocuments: [],
      },
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Просмотреть изменения" }),
  );

  expect(
    await screen.findByText(
      /Изменения не затрагивают файлы проекта — сохранять нечего\./,
    ),
  ).toBeTruthy();
  expect(
    screen.getByText(/Пароль PKCS#12 хранится только в текущем сеансе/),
  ).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Повторить проверку" }),
  ).toBeNull();
});

it("shows an error when repeating structural review fails", async () => {
  const reviewEditSession = vi
    .fn()
    .mockResolvedValueOnce({
      status: "BLOCKED",
      plan: {
        status: "BLOCKED",
        saveAllowed: false,
        semanticChanges: [],
        affectedDocuments: [],
      },
    })
    .mockRejectedValueOnce(new Error("transport detail"));
  const value = api({ reviewEditSession });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "Удалить" }).at(-1)!,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Просмотреть изменения" }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Повторить проверку" }),
  );

  expect(
    await screen.findByText(
      "Не удалось повторно проверить черновик. Попробуйте ещё раз.",
    ),
  ).toBeTruthy();
  expect(reviewEditSession).toHaveBeenCalledTimes(2);
});

it("keeps a failed global verification visible and opens its transfer reason", async () => {
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({
      status: "UNVERIFIED",
      error: {
        code: "PROJECT_TRANSFER_FAILED",
        message: "raw remote detail",
      },
    }),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  const status = await screen.findByRole("button", {
    name: "Проверка недоступна",
  });
  await userEvent.click(status);
  expect(
    await screen.findByText(
      "Не удалось передать проект на узел выполнения для проверки. Проверьте доступ SSH и права на временный каталог, затем повторите проверку. Сохранённый проект не изменён.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText("raw remote detail")).toBeNull();
});

it("shows a safe terminal status when verification binding rejects", async () => {
  const value = api({
    verifyProject: vi
      .fn()
      .mockRejectedValue(new Error("private transport detail")),
  });
  await openServers(value);
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(
    await screen.findByRole("button", {
      name: "Проверка недоступна",
    }),
  ).toBeTruthy();
  expect(screen.queryByText("private transport detail")).toBeNull();
});

it("refreshes the Core snapshot after successful Project Verify", async () => {
  const getCurrentProject = vi.fn().mockResolvedValue({
    ...project,
    snapshot: { ...project.snapshot, project: { name: "Verified Core" } },
  });
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({ status: "VERIFIED" }),
    getCurrentProject,
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  await waitFor(() => expect(getCurrentProject).toHaveBeenCalledOnce());
  expect(
    await screen.findByRole("heading", { name: "Verified Core" }),
  ).toBeTruthy();
});

it("explains the READY Execution Node prerequisite after Project Verify", async () => {
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({
      status: "UNVERIFIED",
      error: {
        code: "EXECUTION_NODE_READY_REQUIRED",
        message: "Execution Node is not READY",
      },
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(value.verifyProject).toHaveBeenCalledOnce();
  expect(
    await screen.findByText(
      "Для проверки нужен готовый узел выполнения. Откройте «Серверы» и проверьте его состояние.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText("Execution Node is not READY")).toBeNull();
});

it("explains a missing trusted Execution Node binding after Project Verify", async () => {
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({
      status: "UNVERIFIED",
      error: { code: "BINDING_REQUIRED", message: "Trusted binding required" },
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(
    await screen.findByText(
      "Для проверки настройте узел выполнения на странице «Серверы». Сохранённый проект не изменён.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText("Trusted binding required")).toBeNull();
});

it("shows a safe Project Verify diagnostic code without exposing backend detail", async () => {
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({
      status: "UNVERIFIED",
      error: {
        code: "PROJECT_SNAPSHOT_RESPONSE_INVALID",
        message: "private path and command output must remain hidden",
      },
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(
    await screen.findByText(
      "Проверка недоступна (код: PROJECT_SNAPSHOT_RESPONSE_INVALID). Сохранённый проект не изменён.",
    ),
  ).toBeTruthy();
  expect(screen.queryByText(/private path and command output/u)).toBeNull();
});

it("shows the structured snapshot failure reason on the Project page", async () => {
  const reason = "Не удалось построить снимок проекта. Этап: загрузка каталога сервисов. Отсутствует обязательный документ.";
  const value = api({ verifyProject: vi.fn().mockResolvedValue({
    status: "UNVERIFIED",
    error: { code: "PROJECT_SNAPSHOT_INPUT_INVALID", message: "private parser output" },
    findings: [{ code: "PROJECT_SNAPSHOT_INPUT_INVALID", summary: reason, severity: "BLOCKED" }],
  }) });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(await screen.findByText(`[BLOCKED] PROJECT_SNAPSHOT_INPUT_INVALID: ${reason}`)).toBeTruthy();
  expect(screen.queryByText("private parser output")).toBeNull();
});

it.each([
  { status: "INVALID", label: "Ошибки проверки", error: undefined },
  { status: "UNVERIFIED", label: "Проверка недоступна", error: { code: "PROJECT_SNAPSHOT_INPUT_INVALID", message: "hidden backend detail" } },
])("opens Project from the red header status for $status", async ({ status, label, error }) => {
  const reason = "У экземпляра сервиса «kafka-extra» не задана обязательная ссылка на секрет в параметре «adminCredential». Настройте секрет и сохраните проект.";
  const value = api();
  value.chooseProject.mockResolvedValue({ ...project, verification: {
    status, error, projectRevision: "sha256:old",
    findings: [{ code: "RUNTIME_SECRET_REFERENCE_REQUIRED", severity: "BLOCKED", summary: reason }],
  } });
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
  expect(screen.getByRole("heading", { name: "Серверы" })).toBeTruthy();
  const badge = screen.getByRole("button", { name: label });
  expect(badge.classList.contains("status-chip--danger")).toBe(true);
  expect(badge.classList.contains("readonly")).toBe(false);
  await userEvent.click(badge);
  expect(screen.getByRole("heading", { name: "Состояние проекта" })).toBeTruthy();
  expect(screen.getByText(`[BLOCKED] RUNTIME_SECRET_REFERENCE_REQUIRED: ${reason}`)).toBeTruthy();
  expect(screen.queryByText("hidden backend detail")).toBeNull();
});

it("shows current INVALID verification findings without a technical error or matching snapshot", async () => {
  const value = api({ verifyProject: vi.fn().mockResolvedValue({
    status: "INVALID", projectRevision: "sha256:old",
    findings: [{ code: "PLACEMENT_INVALID", summary: "Проверьте размещение сервиса.", severity: "BLOCKED", subjectKind: "deployment", subjectId: "docker-extra" }],
    findingsTruncated: true,
  }) });
  value.chooseProject.mockResolvedValue({ ...project, snapshot: undefined });
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(await screen.findByText("[BLOCKED] PLACEMENT_INVALID: Проверьте размещение сервиса. (deployment: docker-extra)")).toBeTruthy();
  expect(screen.queryByText("Не проверено")).toBeNull();
  expect(screen.getByText("Показана часть замечаний проверки.")).toBeTruthy();
});

it("shows a Core warning without styling it as a verification error", async () => {
  const value = api();
  value.chooseProject.mockResolvedValue({ ...project, verification: {
    status: "VERIFIED", projectRevision: "sha256:old",
    findings: [{ code: "CORE_WARNING", summary: "Проверьте рекомендацию Core.", severity: "WARNING" }],
  } });
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  expect(screen.getByText("[WARNING] CORE_WARNING: Проверьте рекомендацию Core.").classList.contains("field-error")).toBe(false);
  const badge = screen.getByRole("button", { name: "Проверено с предупреждениями" });
  expect(badge.classList.contains("status-chip--warning")).toBe(true);
  expect(badge.classList.contains("status-chip--danger")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
  await userEvent.click(badge);
  expect(screen.getByRole("heading", { name: "Состояние проекта" })).toBeTruthy();
  expect(screen.getByText("Проверено с предупреждениями", { selector: "dd" })).toBeTruthy();
});

it("does not treat evidence without a revision as a current project check", async () => {
  const value = api();
  value.chooseProject.mockResolvedValue({ ...project, managed: undefined, verification: {
    status: "INVALID",
    findings: [{ code: "NO_REVISION", summary: "Unbound finding", severity: "BLOCKED" }],
  } });
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  expect(screen.queryByText(/Unbound finding/u)).toBeNull();
  expect(screen.getByText("Не проверено")).toBeTruthy();
});

it("does not display verification findings for an older saved revision", async () => {
  const value = api();
  value.chooseProject.mockResolvedValue({ ...project, verification: {
    status: "INVALID", projectRevision: "sha256:older",
    findings: [{ code: "OLD_ERROR", summary: "Old finding", severity: "BLOCKED" }],
  } });
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  expect(screen.queryByText(/Old finding/u)).toBeNull();
  expect(screen.getByText("Не проверено")).toBeTruthy();
});

it("explains missing runtime identity after Project Verify", async () => {
  const value = api({
    verifyProject: vi.fn().mockResolvedValue({
      status: "UNVERIFIED",
      error: {
        code: "EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED",
        message: "internal runtime detail",
      },
    }),
  });
  value.chooseProject.mockResolvedValue(project);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Проверить" }));
  expect(
    await screen.findByText(
      /Нет подтверждённой привязки к runtime узла выполнения/u,
    ),
  ).toBeTruthy();
  expect(screen.queryByText("internal runtime detail")).toBeNull();
});

describe("UI-01E3 session credentials", () => {
  it("shows a safe Russian explanation for a rejected private key", async () => {
    const value = api({
      setSessionCredential: vi
        .fn()
        .mockRejectedValue(new Error("SESSION_PRIVATE_KEY_INVALID")),
    });
    await openServers(value);
    await userEvent.type(
      screen.getByLabelText("Технический пользователь"),
      "installer",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("SSH-аутентификация"),
      "SSH_PRIVATE_KEY",
    );
    await userEvent.type(
      screen.getByLabelText("Абсолютный путь к приватному ключу"),
      "C:/qa/key.pem",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сеансе" }),
    );
    expect(
      await screen.findByText(
        "Нужен поддерживаемый незашифрованный приватный ключ PEM.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("SESSION_PRIVATE_KEY_INVALID")).toBeNull();
  });

  it("submits write-only credentials and clears transient fields after success", async () => {
    const value = api();
    await openServers(value);
    await userEvent.type(
      screen.getByLabelText("Технический пользователь"),
      "installer",
    );
    await userEvent.type(
      screen.getByLabelText("SSH-пароль"),
      "not-visible-after-submit",
    );
    await userEvent.click(screen.getByLabelText("Требуется пароль sudo"));
    await userEvent.type(
      screen.getByLabelText("Пароль sudo"),
      "also-not-visible-after-submit",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сеансе" }),
    );
    expect(value.setSessionCredential).toHaveBeenCalledWith({
      username: "installer",
      sshMode: "SSH_PASSWORD",
      sshPassword: "not-visible-after-submit",
      privateKeyPath: "",
      elevationMode: "SUDO_PASSWORD",
      elevationPassword: "also-not-visible-after-submit",
    });
    expect(
      (screen.getByLabelText("SSH-пароль") as HTMLInputElement).value,
    ).toBe("");
    expect(
      (screen.getByLabelText("Пароль sudo") as HTMLInputElement).value,
    ).toBe("");
    expect(screen.getByText("Доступны")).toBeTruthy();
    expect(screen.getByText(/14.09.2026, 17:00:00 МСК/)).toBeTruthy();
    expect(screen.queryByText("not-visible-after-submit")).toBeNull();
  });
});

it.each(["blocked", "new-risk", "ready"])(
  "B4 approval builds library-only plan: %s",
  async (scenario) => {
    const fullPlan = {
      id: "b4-full",
      executionMode: "FULL_PROJECT",
      status: "EXECUTABLE",
      projectRevision: "sha256:old",
      planFingerprint: "sha256:fp",
      executionNodeId: "node",
      runtime: {},
      expiresAt: "2099-01-01",
      approved: false,
      acknowledgements: [],
      phases: [],
    };
    const mode = vi
      .fn()
      .mockResolvedValueOnce({ status: "PLAN_REVIEW", plan: fullPlan })
      .mockResolvedValue(
        scenario === "blocked"
          ? {
              status: "BLOCKED",
              error: {
                code: "INFRA_VERIFY_MISSING",
                message: "Verify required",
              },
            }
          : {
              status: "PLAN_REVIEW",
              plan: {
                ...fullPlan,
                id: "b4-library",
                executionMode: "APPLICATION_LIBRARIES_ONLY",
                skipInfrastructureVerify: true,
                acknowledgements:
                  scenario === "new-risk"
                    ? [{ code: "NEW_RISK", summary: "New confirmation" }]
                    : [],
              },
            },
      );
    const legacy = vi.fn();
    const value = api({
      createInstallationPlanForMode: mode,
      getInstallationPlan: vi.fn(async (id: string) =>
        id === "b4-full"
          ? { status: "PLAN_REVIEW", plan: fullPlan }
          : mode.mock.results.at(-1)?.value,
      ),
      createInstallationPlan: legacy,
      approveInstallationPlan: vi.fn().mockResolvedValue({
        status: "PLAN_APPROVED",
        plan: {
          ...fullPlan,
          id: "b4-library",
          executionMode: "APPLICATION_LIBRARIES_ONLY",
          skipInfrastructureVerify: true,
          approved: true,
        },
      }),
      getInstallationState: vi.fn().mockImplementation(async () => ({
        status: "PLAN_REVIEW",
        project: {
          id: "p",
          revision: "sha256:old",
          hasUnsavedChanges: false,
        },
        executionNode: { status: "READY" },
        plan:
          mode.mock.calls.length === 0
            ? { status: "NONE" }
            : {
                status: "PLAN_REVIEW",
                planId: mode.mock.calls.length > 1 ? "b4-library" : "b4-full",
              },
        prerequisites: [],
      })),
    });
    value.chooseProject.mockResolvedValue({
      ...project,
      managed: { ...project.managed, deployments: {} },
    });
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Установка" }));
    await userEvent.click(screen.getByRole("tab", { name: "План" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Сформировать свежий план" }),
    );
    await screen.findByRole("checkbox", {
      name: "Устанавливать инфраструктуру",
    });
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
    );
    expect(mode).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await userEvent.click(screen.getByRole("button", { name: "Установка" }));
    await userEvent.click(screen.getByRole("tab", { name: "План" }));
    expect(
      screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
    ).toHaveProperty("checked", false);
    await userEvent.click(
      screen.getByRole("button", { name: "Сформировать свежий план" }),
    );
    await waitFor(() =>
      expect(mode).toHaveBeenCalledWith({
        executionMode: "APPLICATION_LIBRARIES_ONLY",
        deploymentOrder: [],
        applicationVaultSources: {},
        skipInfrastructureVerify: true,
      }),
    );
    expect(legacy).not.toHaveBeenCalled();
    if (scenario === "ready") {
      await userEvent.click(
        await screen.findByRole("button", { name: "Одобрить план" }),
      );
      expect(value.approveInstallationPlan).toHaveBeenCalledWith(
        "b4-library",
        [],
      );
    } else expect(value.approveInstallationPlan).not.toHaveBeenCalled();
  },
);

it("retains service selection across navigation and sends all-unchecked through skipInfraVerify", async () => {
  const create = vi.fn().mockResolvedValue({ status: "BLOCKED" });
  const value = api({
    createInstallationPlanForMode: create,
    getApplicationConfig: vi.fn().mockResolvedValue({
      status: "READY",
      config: {
        schemaVersion: 1,
        serverTypes: [],
        serviceExecutionPriorities: [
          { serviceType: "kafka", priority: 1 },
          { serviceType: "vault", priority: 2 },
        ],
        libraryExecutionPriorities: [{ libraryName: "szi", priority: 1 }],
      },
    }),
    getInstallationState: vi
      .fn()
      .mockResolvedValue({
        status: "READY_TO_PLAN",
        project: { id: "p", hasUnsavedChanges: false },
        executionNode: { status: "READY" },
        plan: { status: "NONE" },
        prerequisites: [],
      }),
  });
  value.chooseProject.mockResolvedValue({
    ...project,
    managed: {
      ...project.managed,
      deployments: {
        "kafka-main": {
          deploymentId: "kafka-main",
          serviceType: "kafka",
          mode: "kraft",
        },
        "vault-main": {
          deploymentId: "vault-main",
          serviceType: "vault",
          mode: "raft-ha",
        },
      },
      applicationLibraries: { szi: { libraryRef: "szi@1.0.0" } },
    },
  } as unknown as OpenResult);
  render(<App api={value} />);
  await userEvent.click(
    screen.getByRole("button", { name: "Открыть папку проекта" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Установка" }));
  await userEvent.click(screen.getByRole("tab", { name: "План" }));
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Установить сервис kafka-main" }),
  );
  const revisit = async () => {
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await userEvent.click(screen.getByRole("button", { name: "Установка" }));
    await userEvent.click(screen.getByRole("tab", { name: "План" }));
  };
  await revisit();
  expect(
    screen.getByRole("checkbox", { name: "Установить сервис kafka-main" }),
  ).toHaveProperty("checked", false);
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  expect(create).toHaveBeenLastCalledWith(
    expect.objectContaining({
      executionMode: "FULL_PROJECT",
      skipServiceDeployments: ["kafka-main"],
    }),
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  );
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  );
  await revisit();
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  expect(create).toHaveBeenLastCalledWith(
    expect.objectContaining({
      executionMode: "APPLICATION_LIBRARIES_ONLY",
      skipInfrastructureVerify: true,
      applicationVaultSources: {},
    }),
  );
});

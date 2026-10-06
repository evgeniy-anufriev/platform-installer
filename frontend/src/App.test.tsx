import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { OpenResult, ProjectBackend } from "./backend";

const sessionID = "0123456789abcdef0123456789abcdef";
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
    status: "PREVIEW", previewId: "one-use-token",
    currentArtifactDigest: "sha256:old", newArtifactDigest: "sha256:new",
    newCatalogDigest: "sha256:catalog", bundleVersion: "2", coreVersion: "2",
  };
  const chooseRuntimeBundleUpdate = vi.fn().mockResolvedValue(preview);
  const confirmRuntimeBundleUpdate = vi.fn().mockResolvedValue({ status: "UPDATED" });
  const value = api({ chooseRuntimeBundleUpdate, confirmRuntimeBundleUpdate });
  value.chooseProject.mockResolvedValue(project as unknown as OpenResult);
  value.openProject.mockResolvedValue(project as unknown as OpenResult);
  render(<App api={value} />);
  await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
  expect(await screen.findByText("sha256:new")).toBeTruthy();
  expect(confirmRuntimeBundleUpdate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Привязать" }));
  await waitFor(() => expect(confirmRuntimeBundleUpdate).toHaveBeenCalledWith("one-use-token"));
});

function api(overrides: Record<string, unknown> = {}): MockApi {
  return {
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
  expect(screen.getByText("События появятся здесь после запуска плана.")).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Справка" }));
  expect(screen.getByRole("heading", { name: "Справка" })).toBeTruthy();
  expect(screen.getByText(/На странице «Проект» нажмите «Проверить новый набор»/)).toBeTruthy();
  expect(screen.getByText(/Не меняйте digest вручную/)).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "О программе" }));
  expect(screen.getByRole("heading", { name: "О программе" })).toBeTruthy();
  expect(screen.getAllByText("Platform Installer V2").length).toBeGreaterThan(0);
  expect(screen.getByText("v1")).toBeTruthy();

  await userEvent.click(screen.getByRole("button", { name: "Настройки" }));
  expect(screen.getByRole("heading", { name: "Настройки" })).toBeTruthy();
  expect(screen.getByText(/Учётные данные сеанса и секреты не сохраняются/)).toBeTruthy();
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
    getExecutionNodeContext: vi.fn().mockResolvedValue({ status: "READY" }),
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

  expect(screen.getByText("EXECUTION_NODE_BINDING_REQUIRED")).toBeTruthy();
  expect(screen.getByRole("tab", { name: "План" })).toBeTruthy();
  expect(getInstallationState).toHaveBeenCalled();
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
    expect(
      screen
        .getByRole("button", { name: "Установка" })
        .classList.contains("future"),
    ).toBe(false);
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
  });

  it("keeps Installation visible before readiness while preparation stays on Servers", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "NOT_PREPARED",
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
    ).toHaveProperty("disabled", false);
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить узел" }),
    );
    expect(value.checkExecutionNode).toHaveBeenCalledOnce();
    expect(
      (screen.getByRole("button", { name: "Установка" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
    expect(
      screen
        .getByRole("button", { name: "Установка" })
        .classList.contains("future"),
    ).toBe(false);
    await userEvent.click(
      screen.getByRole("button", { name: "Спланировать подготовку" }),
    );
    expect(
      await screen.findByRole("button", { name: "Подтвердить подготовку" }),
    ).toBeTruthy();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await userEvent.click(
      screen.getByRole("button", { name: "Подтвердить подготовку" }),
    );
    expect(value.prepareExecutionNode).toHaveBeenCalledWith("prepare-plan");
    expect(await screen.findByText(/Проверка проекта: Проверено/)).toBeTruthy();
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

  it("opens Topology without an Execution Node and renders saved deployments", async () => {
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
      screen.getByRole("button", { name: /^kafka-main/ }).getAttribute(
        "aria-current",
      ),
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
    expect(value.getExecutionNodeContext).toBeUndefined();
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
    expect(
      screen.getByRole("button", { name: "Удалить экземпляр" }),
    ).toHaveProperty("disabled", true);
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

  it("keeps local values visible when the READY Core projection is unavailable", async () => {
    const value = api({
      getExecutionNodeContext: vi.fn().mockResolvedValue({
        status: "READY",
        selectionKind: "PROJECT_SERVER",
        selectedHostId: "node1",
        runtimeDigest: "sha256:runtime-a",
      }),
      getServiceConfigurationPreview: vi
        .fn()
        .mockRejectedValue(
          new Error("SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED"),
        ),
    });
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(
      await screen.findByText(
        "Core-проекция недоступна для текущей сохранённой ревизии. Код: SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED. Показаны безопасные локальные значения.",
      ),
    ).toBeTruthy();
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
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(
      screen.getByText(
        "Core-проекция недоступна: runtime узла выполнения не подтверждён. Показаны безопасные локальные значения.",
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
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 5")).toBeTruthy();

    activeDigest = "sha256:runtime-b";
    await userEvent.click(screen.getByRole("button", { name: "Серверы" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить узел" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^kafka-main/ }));
    expect(await screen.findByText("По умолчанию: 7")).toBeTruthy();
    expect(screen.queryByText("По умолчанию: 5")).toBeNull();
    expect(value.getServiceConfigurationPreview).toHaveBeenCalledTimes(2);
    expect(value.verifyProject).not.toHaveBeenCalled();
  });

  it("adds only runtime references before accepting Redis secret values into memory", async () => {
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
            configurationSettings: [],
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
    });
    value.chooseProject.mockResolvedValue(redisProject);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Сервисы" }));
    await userEvent.click(screen.getByRole("button", { name: /^redis-main/ }));
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
    expect(setPendingDeploymentRuntimeSecretValues).not.toHaveBeenCalled();
    expect(screen.getByText(/Ссылки добавлены в черновик/)).toBeTruthy();
    expect(screen.queryByText("not-persisted")).toBeNull();
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

  it("opens one Services list/detail view without an Execution Node and returns to the list", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
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
    expect(value.getExecutionNodeContext).toBeUndefined();
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
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
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
    expect(value.getExecutionNodeContext).toBeUndefined();
    expect(value.appendEditCommand).not.toHaveBeenCalled();
  });

  it("adds one deployment-scoped safe setting command through the shared session", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
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

  it("clears unapplied service form input when the shared draft is discarded", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
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
      screen.getByLabelText("Имя новой папки"),
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

it("shows a Russian explanation for REFERENCE_IN_USE in Review", async () => {
  const value = api({
    reviewEditSession: vi.fn().mockResolvedValue({
      status: "BLOCKED",
      plan: {
        saveAllowed: false,
        finding: {
          code: "REFERENCE_IN_USE",
          safeMessage: "Referenced entity must be cleared before removal",
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
    await screen.findByText(
      "Объект используется. Сначала удалите связанные ссылки.",
    ),
  ).toBeTruthy();
  expect(
    screen.queryByText("Referenced entity must be cleared before removal"),
  ).toBeNull();
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
    await screen.findByText(/Нет подтверждённой привязки к runtime узла выполнения/u),
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
    expect(screen.getByText("Доступны до 2026-09-14T14:00:00Z")).toBeTruthy();
    expect(screen.queryByText("not-visible-after-submit")).toBeNull();
  });
});

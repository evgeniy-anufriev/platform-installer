import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { OpenResult, ProjectBackend } from "./backend";

const sessionID = "0123456789abcdef0123456789abcdef";
const project = {
  status: "OPEN",
  root: "C:/Projects/test",
  classification: "MANAGED_PROJECT",
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
  counts: { servers: 0, deployments: 0, runs: 0 },
};

type MockApi = ProjectBackend & {
  chooseProject: ReturnType<typeof vi.fn>;
  openProject: ReturnType<typeof vi.fn>;
  startEditSession: ReturnType<typeof vi.fn>;
  appendEditCommand: ReturnType<typeof vi.fn>;
  reviewEditSession: ReturnType<typeof vi.fn>;
  commitEditPlan: ReturnType<typeof vi.fn>;
  discardEditSession: ReturnType<typeof vi.fn>;
};

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
    reviewEditSession: vi.fn(),
    commitEditPlan: vi.fn(),
    discardEditSession: vi.fn().mockResolvedValue({ status: "DISCARDED" }),
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

describe("UI-01E2 server editor", () => {
  it("keeps a Core-opened project read-only until a server intent is added", async () => {
    const value = api();
    value.chooseProject.mockResolvedValue(project);
    render(<App api={value} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    expect(await screen.findByText("Проверено Core")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Топология" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(screen.queryByText("Есть несохранённые изменения")).toBeNull();
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
      screen.getByRole("button", { name: "Выбрать parent" }),
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

  it("hides the stale snapshot after COMMITTED_REFRESH_FAILED and reopens through OpenProject", async () => {
    const planID = "abcdef0123456789abcdef0123456789";
    const refreshed = {
      ...project,
      snapshot: {
        ...project.snapshot,
        projectRevision: "sha256:new",
        hosts: {
          node1: {
            ...project.snapshot.hosts.node1,
            desiredHostname: "node1.changed.internal",
          },
        },
      },
    };
    const value = api({
      reviewEditSession: vi.fn().mockResolvedValue({
        status: "READY",
        plan: {
          planId: planID,
          commitAllowed: true,
          validation: { status: "PASS", findings: [] },
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
        status: "COMMITTED_REFRESH_FAILED",
        commit: { status: "COMMITTED_REFRESH_FAILED" },
      }),
      openProject: vi.fn().mockResolvedValue(refreshed),
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
      screen.getByRole("button", { name: "Проверить изменения" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Затрагиваемые документы" }),
    ).toBeTruthy();
    expect(
      screen.getByText("Inventory changes require a later apply."),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить проект" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Снимок проекта требует обновления",
      }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Обновить снимок проекта" }),
    );
    expect(value.openProject).toHaveBeenCalledWith("C:/Projects/test");
    expect(await screen.findByText("node1.changed.internal")).toBeTruthy();
  });
});

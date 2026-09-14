import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

const editApi = () => ({
  getApplicationConfig: vi
    .fn()
    .mockResolvedValue({
      status: "READY",
      config: {
        schemaVersion: 1,
        serverTypes: [{ id: "infra", displayName: "Инфраструктура" }],
      },
    }),
  startEditSession: vi.fn(),
  appendEditCommand: vi.fn(),
  reviewEditSession: vi.fn(),
  commitEditPlan: vi.fn(),
  discardEditSession: vi.fn(),
});

describe("UI-01B read-only shell", () => {
  it("opens and closes a Core snapshot without exposing edit actions", async () => {
    const api = {
      ...editApi(),
      chooseProject: vi
        .fn()
        .mockResolvedValue({
          status: "OPEN",
          root: "C:/fixture",
          snapshot: {
            status: "PASS",
            project: { name: "Fixture" },
            projectRevision: "sha256:abc",
            snapshotFingerprint: "sha256:def",
            hosts: { node1: {} },
            serviceDeployments: {},
            pki: {},
            findings: [],
            documents: [],
          },
        }),
      chooseProjectParent: vi.fn(),
      createProject: vi.fn(),
      closeProject: vi.fn().mockResolvedValue({ status: "NO_PROJECT" }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Fixture" }),
    ).toBeTruthy();
    expect(screen.getByText("Проверено Core")).toBeTruthy();
    expect(screen.queryByText("Сохранить")).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Закрыть проект" }),
    );
    expect(
      await screen.findByText(
        "Выберите существующий проект или создайте новый",
      ),
    ).toBeTruthy();
  });

  it("creates and renders an empty managed project without a Core snapshot", async () => {
    const api = {
      ...editApi(),
      chooseProject: vi.fn(),
      chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"),
      closeProject: vi.fn(),
      createProject: vi
        .fn()
        .mockResolvedValue({
          status: "OPEN",
          root: "C:/Projects/new-project",
          classification: "EMPTY_MANAGED_PROJECT",
          project: {
            id: "project-0123456789abcdef",
            name: "New Project",
            source: {
              id: "default",
              bundleDigest: "sha256:bundle",
              catalogDigest: "sha256:catalog",
            },
          },
          counts: { servers: 0, deployments: 0, runs: 0 },
        }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.type(
      screen.getByLabelText("Название проекта"),
      "New Project",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Выбрать parent" }),
    );
    await userEvent.clear(screen.getByLabelText("Название проекта"));
    await userEvent.type(
      screen.getByLabelText("Название проекта"),
      "Renamed Project",
    );
    expect(
      (screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value,
    ).toBe("C:/Projects\\Renamed Project");
    await userEvent.clear(screen.getByLabelText("Новая папка проекта"));
    await userEvent.type(
      screen.getByLabelText("Новая папка проекта"),
      "D:/Manual/custom-folder",
    );
    await userEvent.clear(screen.getByLabelText("Название проекта"));
    await userEvent.type(
      screen.getByLabelText("Название проекта"),
      "Final Project",
    );
    expect(
      (screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value,
    ).toBe("D:/Manual/Final Project");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect(
      await screen.findByRole("heading", { name: "Проект ещё не настроен" }),
    ).toBeTruthy();
    expect(screen.getByText("Не создан")).toBeTruthy();
    expect(api.createProject).toHaveBeenCalledWith({
      projectRoot: "D:/Manual/Final Project",
      displayName: "Final Project",
      compatibilitySourceId: "default",
    });
  });

  it("shows a create error immediately instead of keeping its modal open", async () => {
    const api = {
      ...editApi(),
      chooseProject: vi.fn(),
      chooseProjectParent: vi.fn(),
      closeProject: vi.fn(),
      createProject: vi
        .fn()
        .mockResolvedValue({
          status: "ERROR",
          error: {
            code: "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE",
            message: "Нет проверенного local source.",
          },
        }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.type(screen.getByLabelText("Название проекта"), "Project");
    await userEvent.type(
      screen.getByLabelText("Новая папка проекта"),
      "C:/Projects/project",
    );
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect(
      await screen.findByText("Нет проверенного local source."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: "Создать проект" }),
    ).toBeNull();
  });

  it("requires a project name and never calls the backend without one", async () => {
    const api = {
      ...editApi(),
      chooseProject: vi.fn(),
      chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"),
      closeProject: vi.fn(),
      createProject: vi.fn(),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" })[0],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Выбрать parent" }),
    );
    expect(
      (screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value,
    ).toBe("C:/Projects\\");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!,
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Заполните «Название проекта»",
    );
    expect(api.createProject).not.toHaveBeenCalled();
  });

  it("keeps first-save changes transient until review and explicit save", async () => {
    const project = {
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
    const api = {
      ...editApi(),
      chooseProject: vi.fn().mockResolvedValue(project),
      chooseProjectParent: vi.fn(),
      createProject: vi.fn(),
      closeProject: vi.fn(),
      startEditSession: vi
        .fn()
        .mockResolvedValue({
          status: "EDITING",
          session: {
            sessionId: "0123456789abcdef0123456789abcdef",
            commandCount: 0,
          },
        }),
      appendEditCommand: vi
        .fn()
        .mockResolvedValue({
          status: "EDITING",
          session: {
            sessionId: "0123456789abcdef0123456789abcdef",
            commandCount: 1,
          },
        }),
      reviewEditSession: vi
        .fn()
        .mockResolvedValue({
          status: "READY",
          plan: {
            planId: "abcdef0123456789abcdef0123456789",
            commitAllowed: true,
            validation: { status: "PASS" },
            semanticChanges: [{ safeSummary: "CreateServer node1" }],
            affectedDocuments: [
              {
                logicalPath: "inventory/hosts.yml",
                before: { state: "ABSENT" },
                after: { state: "PRESENT" },
              },
            ],
          },
        }),
      commitEditPlan: vi
        .fn()
        .mockResolvedValue({
          status: "COMMITTED",
          commit: {
            status: "COMMITTED",
            snapshot: {
              status: "PASS",
              project: { name: "Test" },
              hosts: { node1: {} },
              serviceDeployments: {},
              pki: {},
              findings: [],
              documents: [],
              projectRevision: "sha256:new",
              snapshotFingerprint: "sha256:snapshot",
            },
          },
        }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Начать редактирование" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Тип сервера"),
      "infra",
    );
    await userEvent.type(screen.getByLabelText("Адрес"), "192.0.2.10");
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.example.internal",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(screen.getByText("Есть несохранённые изменения")).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить изменения" }),
    );
    expect(
      await screen.findByRole("heading", { name: "План изменений" }),
    ).toBeTruthy();
    expect(api.appendEditCommand).toHaveBeenCalledWith(
      "0123456789abcdef0123456789abcdef",
      {
        operation: "CreateServer",
        hostId: "node1",
        type: "infra",
        desiredHostname: "node1.example.internal",
        address: "192.0.2.10",
        sshPort: 22,
      },
    );
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("heading", { name: "Test" })).toBeTruthy();
    expect(api.commitEditPlan).toHaveBeenCalledWith(
      "0123456789abcdef0123456789abcdef",
      "abcdef0123456789abcdef0123456789",
    );
  });

  it("blocks only new server input when application config is unavailable", async () => {
    const project = {
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
    const api = {
      ...editApi(),
      getApplicationConfig: vi
        .fn()
        .mockResolvedValue({
          status: "ERROR",
          error: {
            code: "APPLICATION_CONFIG_INVALID",
            message: "Конфигурация приложения недоступна.",
          },
        }),
      chooseProject: vi.fn().mockResolvedValue(project),
      chooseProjectParent: vi.fn(),
      createProject: vi.fn(),
      closeProject: vi.fn(),
      startEditSession: vi
        .fn()
        .mockResolvedValue({
          status: "EDITING",
          session: {
            sessionId: "0123456789abcdef0123456789abcdef",
            commandCount: 0,
          },
        }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Начать редактирование" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Конфигурация приложения недоступна",
    );
    expect(
      (
        screen.getByRole("button", {
          name: "Добавить в черновик",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("retains the draft and reviewed plan across transient review and save failures", async () => {
    const project = {
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
    const sessionId = "0123456789abcdef0123456789abcdef";
    const planId = "abcdef0123456789abcdef0123456789";
    const plan = {
      planId,
      commitAllowed: true,
      validation: { status: "PASS" },
      semanticChanges: [{ safeSummary: "CreateServer node1" }],
      affectedDocuments: [
        {
          logicalPath: "inventory/hosts.yml",
          before: { state: "ABSENT" },
          after: { state: "PRESENT" },
        },
      ],
    };
    const refreshedPlan = {
      ...plan,
      planId: "fedcba9876543210fedcba9876543210",
    };
    const api = {
      ...editApi(),
      chooseProject: vi.fn().mockResolvedValue(project),
      chooseProjectParent: vi.fn(),
      createProject: vi.fn(),
      closeProject: vi.fn(),
      startEditSession: vi
        .fn()
        .mockResolvedValue({
          status: "EDITING",
          session: { sessionId, commandCount: 0 },
        }),
      appendEditCommand: vi
        .fn()
        .mockResolvedValue({
          status: "EDITING",
          session: { sessionId, commandCount: 1 },
        }),
      reviewEditSession: vi
        .fn()
        .mockResolvedValueOnce({
          status: "BLOCKED",
          plan: {
            status: "BLOCKED",
            validation: {
              status: "BLOCKED",
              findings: [
                {
                  code: "CORE_VALIDATION_UNAVAILABLE",
                  safeMessage: "Execution Node недоступен.",
                },
              ],
            },
          },
        })
        .mockResolvedValueOnce({ status: "READY", plan })
        .mockResolvedValueOnce({ status: "READY", plan: refreshedPlan }),
      commitEditPlan: vi
        .fn()
        .mockResolvedValueOnce({
          status: "BLOCKED",
          commit: {
            status: "BLOCKED",
            finding: { code: "PLAN_EXPIRED", safeMessage: "План истёк." },
          },
        })
        .mockResolvedValueOnce({
          status: "COMMITTED",
          commit: {
            status: "COMMITTED",
            snapshot: {
              status: "PASS",
              project: { name: "Test" },
              hosts: { node1: {} },
              serviceDeployments: {},
              pki: {},
              findings: [],
              documents: [],
              projectRevision: "sha256:new",
              snapshotFingerprint: "sha256:snapshot",
            },
          },
        }),
    };
    render(<App api={api} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Открыть папку проекта" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Начать редактирование" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Тип сервера"),
      "infra",
    );
    await userEvent.type(screen.getByLabelText("Адрес"), "192.0.2.10");
    await userEvent.type(
      screen.getByLabelText("Желаемое имя хоста"),
      "node1.example.internal",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Проверить изменения" }),
    );
    expect(
      await screen.findByRole("button", { name: "Повторить проверку" }),
    ).toBeTruthy();
    expect(screen.getByText("Есть несохранённые изменения")).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Повторить проверку" }),
    );
    expect(
      await screen.findByRole("heading", { name: "План изменений" }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByRole("button", { name: "Повторить сохранение" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Повторить проверку" }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Повторить проверку" }),
    );
    expect(
      await screen.findByRole("heading", { name: "План изменений" }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("heading", { name: "Test" })).toBeTruthy();
    expect(api.reviewEditSession).toHaveBeenCalledTimes(3);
    expect(api.commitEditPlan).toHaveBeenCalledTimes(2);
    expect(api.commitEditPlan).toHaveBeenLastCalledWith(
      sessionId,
      refreshedPlan.planId,
    );
  });
});

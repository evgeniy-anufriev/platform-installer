import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  InstallationPage,
  deploymentOrderFromPriorities,
} from "./InstallationPage";
import { desktop } from "../wailsjs/go/models";

const state = {
  apiVersion: "platform.installer/installation-state/v1alpha1" as const,
  kind: "InstallationState" as const,
  status: "PREREQUISITES_REQUIRED" as const,
  project: {
    id: "project-aaaaaaaaaaaaaaaa",
    revision: "sha256:revision",
    verificationStatus: "UNVERIFIED",
    hasUnsavedChanges: false,
  },
  executionNode: { status: "NOT_PREPARED", safeLabel: "node1 · 192.0.2.10" },
  plan: { status: "NOT_CREATED" as const },
  prerequisites: [
    {
      code: "EXECUTION_NODE_READY_REQUIRED",
      destination: "servers" as const,
      safeMessage:
        "A READY Execution Node is required before creating an installation plan.",
    },
  ],
};

const currentPlanState = (
  planId: string,
  revision: string,
  approved: boolean,
) => ({
  ...state,
  status: approved ? ("PLAN_APPROVED" as const) : ("PLAN_REVIEW" as const),
  project: { ...state.project, revision },
  executionNode: { status: "READY", safeLabel: "node1 · 192.0.2.10" },
  plan: {
    status: approved ? ("PLAN_APPROVED" as const) : ("PLAN_REVIEW" as const),
    planId,
  },
  prerequisites: [],
});

describe("InstallationPage", () => {
  it("requires explicit risky Infra Verify skip and sends it only in a fresh library plan", async () => {
    const user = userEvent.setup();
    const create = vi.fn();
    const props = {
      state: {
        ...state,
        status: "READY_TO_PLAN" as const,
        prerequisites: [],
        executionNode: { status: "READY" },
      },
      selectedExecutionMode: "APPLICATION_LIBRARIES_ONLY" as const,
      onTabChange: vi.fn(),
      busy: false,
      onOpenServers: vi.fn(),
      onCreatePlan: create,
      onApprovePlan: vi.fn(),
    };
    const view = render(<InstallationPage {...props} tab="summary" />);
    let flag = screen.getByRole("checkbox", {
      name: "Пропустить проверку инфраструктуры — принимаю риски",
    });
    expect((flag as HTMLInputElement).checked).toBe(false);
    await user.click(flag);
    view.rerender(<InstallationPage {...props} tab="plan" />);
    await user.click(
      screen.getByRole("button", { name: "Сформировать свежий план" }),
    );
    expect(create).toHaveBeenLastCalledWith(
      [],
      "APPLICATION_LIBRARIES_ONLY",
      true,
    );
    view.rerender(<InstallationPage {...props} tab="summary" />);
    flag = screen.getByRole("checkbox", {
      name: "Пропустить проверку инфраструктуры — принимаю риски",
    });
    await user.click(flag);
    view.rerender(<InstallationPage {...props} tab="plan" />);
    await user.click(
      screen.getByRole("button", { name: "Сформировать свежий план" }),
    );
    expect(create).toHaveBeenLastCalledWith([], "APPLICATION_LIBRARIES_ONLY");
  });

  it("orders services by priority, preserves YAML order for ties, then orders deployments by ID", () => {
    expect(
      deploymentOrderFromPriorities(
        [
          { deploymentId: "vault-z", serviceType: "vault" },
          { deploymentId: "haproxy-main", serviceType: "haproxy" },
          { deploymentId: "vault-a", serviceType: "vault" },
          { deploymentId: "bind-main", serviceType: "bind" },
        ],
        [
          { serviceType: "bind", priority: 0 },
          { serviceType: "haproxy", priority: 3 },
          { serviceType: "vault", priority: 4 },
        ],
      ),
    ).toEqual({
      order: ["bind-main", "haproxy-main", "vault-a", "vault-z"],
      missingTypes: [],
    });
  });

  it("does not invent an order when a selected service has no configured priority", () => {
    expect(
      deploymentOrderFromPriorities(
        [{ deploymentId: "postgres-main", serviceType: "postgresql" }],
        [{ serviceType: "bind", priority: 0 }],
      ),
    ).toEqual({ order: [], missingTypes: ["postgresql"] });
  });

  it("renders only safe prerequisite state and routes preparation to Servers", async () => {
    const user = userEvent.setup();
    const onOpenServers = vi.fn();
    render(
      <InstallationPage
        state={state}
        tab="summary"
        onTabChange={vi.fn()}
        onOpenServers={onOpenServers}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
      />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "Текущий этап: План · План не готов",
    );
    expect(screen.queryByLabelText("Стадии установки")).toBeNull();
    expect(screen.queryByText("PREREQUISITES_REQUIRED")).toBeNull();
    expect(screen.getByText("node1 · 192.0.2.10")).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: "Следующее действие" }),
    ).toBeNull();
    expect(screen.queryByText("Сформировать свежий план")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Открыть Серверы" }));
    expect(onOpenServers).toHaveBeenCalledOnce();
  });

  it("shows the Core plan preview on Summary and opens the full Plan view", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(
      <InstallationPage
        state={currentPlanState("plan-summary", "sha256:old", false)}
        tab="summary"
        onTabChange={onTabChange}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        plan={{
          status: "PLAN_REVIEW",
          plan: {
            id: "plan-summary",
            status: "EXECUTABLE",
            projectRevision: "sha256:old",
            planFingerprint: "sha256:plan",
            executionNodeId: "node1",
            runtime: {
              bundleDigest: "sha256:bundle",
              coreVersion: "core",
              catalogDigest: "sha256:catalog",
              protocol: "protocol",
            },
            expiresAt: "2026-09-22T10:00:00Z",
            approved: false,
            acknowledgements: [],
            phases: [
              {
                id: "apply",
                order: 0,
                actions: [
                  {
                    id: "apply:kafka-main",
                    type: "SERVICE_APPLY",
                    serviceDeployment: "kafka-main",
                    targets: ["node1", "node2"],
                    dependsOn: [],
                    mutating: true,
                    reboot: "NONE",
                    summary: "Kafka apply",
                  },
                ],
              },
            ],
          },
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "План установки" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: "Следующее действие" }),
    ).toBeNull();
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("Установить сервис kafka-main")).toBeTruthy();
    expect(screen.getByText("node1, node2")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Открыть план" }));
    expect(onTabChange).toHaveBeenCalledWith("plan");
  });

  it("keeps secret material out of Installation navigation", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(
      <InstallationPage
        state={state}
        tab="summary"
        onTabChange={onTabChange}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("tab", { name: "План" }));
    expect(onTabChange).toHaveBeenCalledWith("plan");
    expect(screen.queryByText("Runtime secrets")).toBeNull();
  });

  it("shows the bounded plan and requires each exact acknowledgement", async () => {
    const user = userEvent.setup();
    const onApprovePlan = vi.fn();
    render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={onApprovePlan}
        plan={{
          status: "PLAN_REVIEW",
          plan: {
            id: "plan-1",
            status: "EXECUTABLE",
            projectRevision: "sha256:old",
            planFingerprint: "sha256:plan",
            executionNodeId: "node1",
            runtime: {
              bundleDigest: "sha256:bundle",
              coreVersion: "core",
              catalogDigest: "sha256:catalog",
              protocol: "protocol",
            },
            expiresAt: "2026-09-22T10:00:00Z",
            approved: false,
            acknowledgements: [
              { code: "ACK_RISK", summary: "Review the planned change" },
            ],
            phases: [
              {
                id: "apply",
                order: 0,
                actions: [
                  {
                    id: "apply:kafka-main",
                    type: "SERVICE_APPLY",
                    serviceDeployment: "kafka-main",
                    targets: ["node1"],
                    dependsOn: [],
                    mutating: true,
                    reboot: "NONE",
                    summary: "Apply Kafka",
                  },
                ],
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("План готов к рассмотрению")).toBeTruthy();
    expect(screen.queryByText("PLAN_REVIEW")).toBeNull();
    expect(screen.getByText("Установить сервис kafka-main")).toBeTruthy();
    expect(screen.getByText("Развёртывание: kafka-main")).toBeTruthy();
    const approve = screen.getByRole("button", { name: "Одобрить план" });
    expect(approve).toHaveProperty("disabled", true);
    await user.click(screen.getByRole("checkbox", { name: /ACK_RISK/ }));
    await user.click(approve);
    expect(onApprovePlan).toHaveBeenCalledWith("plan-1", ["ACK_RISK"]);
  });

  it("starts only an already approved plan and renders safe execution state", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const plan = {
      status: "PLAN_APPROVED" as const,
      plan: {
        id: "plan-1",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: true,
        acknowledgements: [],
        phases: [],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", true)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        plan={plan}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Начать выполнение" }));
    expect(onStart).toHaveBeenCalledWith("plan-1");
  });

  it("keeps the start action visible but disabled while this installation is running", () => {
    const onStart = vi.fn();
    const plan = {
      status: "PLAN_APPROVED" as const,
      plan: {
        id: "plan-running",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: true,
        acknowledgements: [],
        phases: [],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-running", "sha256:old", true)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        runPlan={plan.plan}
        run={
          new desktop.InstallationRunOperation({
            status: "RUNNING",
            run: { runId: "run-1", state: "RUNNING", sequence: 3 },
          })
        }
      />,
    );
    const actions = screen.getByRole("contentinfo", {
      name: "Действия с планом",
    });
    const start = screen.getByRole("button", { name: "Начать выполнение" });
    expect(actions.contains(start)).toBe(true);
    expect(start).toHaveProperty("disabled", true);
    expect(actions.textContent).toContain("уже запущено");
    expect(onStart).not.toHaveBeenCalled();
  });

  it("shows the safe Start failure instead of saying that nothing happened", () => {
    render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", true)}
        tab="execution"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        run={
          new desktop.InstallationRunOperation({
            status: "BLOCKED",
            error: {
              code: "START_PREREQUISITE_MISSING",
              message: "Требуется подготовка.",
            },
          })
        }
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "START_PREREQUISITE_MISSING",
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "Требуется подготовка.",
    );
    expect(screen.queryByText("В этом сеансе запуск ещё не начат.")).toBeNull();
  });

  it("explains OUTPUT_BUSY and opens protected outputs from the failed execution", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    const onRefreshSecretOutputs = vi.fn();
    render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", true)}
        tab="execution"
        onTabChange={onTabChange}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        onStart={vi.fn()}
        onRefreshSecretOutputs={onRefreshSecretOutputs}
        run={
          new desktop.InstallationRunOperation({
            status: "READY",
            run: { runId: "run-output-busy", state: "FAILED", sequence: 2 },
          })
        }
        events={[
          new desktop.InstallationEventView({
            runId: "run-output-busy",
            sequence: 2,
            eventType: "DIAGNOSTIC",
            status: "FAILED",
            timestamp: "2026-10-08T08:36:27Z",
            safeMessage:
              "Controller preparation failed before execution (diagnostic: OUTPUT_BUSY)",
          }),
        ]}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain(
      "не перезаписать файлы",
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "Код диагностики: OUTPUT_BUSY",
    );
    expect(screen.queryByText(/Controller preparation failed/)).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Проверить и получить файлы" }),
    );
    expect(onTabChange).toHaveBeenCalledWith("result");
    expect(onRefreshSecretOutputs).toHaveBeenCalledOnce();
  });

  it("localizes a live run state and does not expose the protocol value", () => {
    const run = new desktop.InstallationRunOperation({
      status: "RUNNING",
      run: { runId: "run-safe", state: "RUNNING", sequence: 4 },
    });
    const { container } = render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", false)}
        tab="execution"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        run={run}
        runProgress={{
          runId: "run-safe",
          lastSequence: 4,
          lastContiguousSequence: 4,
          pendingSequences: [],
          complete: true,
          actionIds: ["a", "b"],
          completedActionIds: ["a"],
          actionOutcomes: { a: "SUCCESS" },
          actionOutcomeSequences: { a: 2 },
        }}
        events={[
          new desktop.InstallationEventView({
            runId: "run-safe",
            sequence: 3,
            eventType: "TASK_COMPLETED",
            status: "SUCCESS",
            timestamp: "2026-10-05T07:22:44Z",
            safeMessage: "Ansible task completed",
            host: "node1",
            serviceDeployment: "qa-bind",
            task: {
              role: "platform.bind",
              name: "platform.bind : Проверка swap",
              uuid: "task-1",
            },
          }),
          new desktop.InstallationEventView({
            runId: "run-safe",
            sequence: 4,
            eventType: "TASK_STARTED",
            status: "RUNNING",
            timestamp: "2026-10-05T07:22:45Z",
            safeMessage: "Ansible task started",
            host: "node2",
            task: { name: "Следующая задача", uuid: "task-2" },
          }),
        ]}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Идёт установка" }),
    ).toBeTruthy();
    expect(screen.queryByText("RUNNING")).toBeNull();
    expect(screen.getByText(/Запуск: run-safe/)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "Идёт установка · 50%",
    );
    expect(
      screen.getByText(/Последняя завершённая задача: Проверка swap/),
    ).toBeTruthy();
    expect(screen.getByText("Проверка swap")).toBeTruthy();
    expect(screen.queryByText("Детали события")).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Действия плана" }),
    ).toBeTruthy();
    expect(
      screen.queryByText(/Последняя завершённая задача: Следующая задача/),
    ).toBeNull();
    const eventTimes = container.querySelectorAll("time");
    expect(eventTimes).toHaveLength(2);
    expect(eventTimes[0].getAttribute("datetime")).toBe("2026-10-05T07:22:44Z");
    const eventTable = screen.getByRole("table");
    expect(eventTable.querySelector("th:nth-child(3)")?.textContent).toBe(
      "Развёртывание",
    );
    expect(eventTable.textContent).toContain("qa-bind");
  });

  it("shows only the newest 512 execution events and follows the latest update", () => {
    const run = new desktop.InstallationRunOperation({
      status: "RUNNING",
      run: { runId: "run-window", state: "RUNNING", sequence: 600 },
    });
    const events = Array.from({ length: 600 }, (_, index) => {
      const sequence = index + 1;
      return new desktop.InstallationEventView({
        runId: "run-window",
        sequence,
        eventType: "TASK_COMPLETED",
        status: "SUCCESS",
        timestamp: `2026-10-05T07:22:${String(sequence % 60).padStart(2, "0")}Z`,
        safeMessage: `Сообщение события ${sequence}`,
        host: "node1",
        task: { name: `Задача ${sequence}`, uuid: `task-${sequence}` },
      });
    });
    const props = {
      state: currentPlanState("plan-1", "sha256:old", false),
      tab: "execution" as const,
      onTabChange: vi.fn(),
      onOpenServers: vi.fn(),
      busy: false,
      onCreatePlan: vi.fn(),
      onApprovePlan: vi.fn(),
      run,
      events,
      onStart: vi.fn(),
      onCancel: vi.fn(),
    };
    const { container, rerender } = render(<InstallationPage {...props} />);
    const table = screen.getByRole("table");
    expect(screen.getByText("Показаны последние 512; всего 600")).toBeTruthy();
    expect(table.querySelectorAll("tbody tr")).toHaveLength(512);
    expect(table.querySelector("tbody tr")?.textContent).toContain("Задача 89");
    expect(screen.getAllByText("Сообщение события 600").length).toBeGreaterThan(
      0,
    );

    const scrollContainer = container.querySelector(
      ".execution-event-table-scroll",
    ) as HTMLDivElement;
    Object.defineProperty(scrollContainer, "scrollHeight", {
      configurable: true,
      value: 1200,
    });
    rerender(
      <InstallationPage
        {...props}
        events={[
          ...events,
          new desktop.InstallationEventView({
            ...events[599],
            sequence: 601,
            safeMessage: "Новейшее событие",
          }),
        ]}
      />,
    );
    expect(scrollContainer.scrollTop).toBe(1200);
  });

  it("explains phases without deployment actions instead of presenting them as service work", () => {
    const plan = {
      status: "PLAN_REVIEW" as const,
      plan: {
        id: "plan-empty",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: false,
        acknowledgements: [],
        phases: [
          { id: "apply", order: 0, actions: [] },
          { id: "verify", order: 1, actions: [] },
        ],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-empty", "sha256:old", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        plan={plan}
      />,
    );
    expect(
      screen.getByText(
        "В плане нет действий по развёртыванию сервисов. Проверьте состав и размещение сервисов в проекте.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Применение").closest("summary")).toBeTruthy();
    expect(
      screen.getByText("Проверка и завершение").closest("summary"),
    ).toBeTruthy();
    expect(screen.queryByText(/Развёртывание:/)).toBeNull();
  });

  it("shows known Core plan findings in Russian without merging repeated codes", () => {
    const plan = {
      status: "PLAN_BLOCKED" as const,
      plan: {
        id: "plan-findings",
        status: "BLOCKED" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: false,
        acknowledgements: [],
        phases: [],
        findings: [
          {
            code: "ENDPOINT_PROVIDER_FIELD_REQUIRED",
            safeMessage:
              "Endpoint provider deployment requires endpointGroupRef",
          },
          {
            code: "ENDPOINT_PROVIDER_FIELD_REQUIRED",
            safeMessage:
              "Endpoint provider deployment requires virtualAddresses",
          },
        ],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-findings", "sha256:old", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        plan={plan}
      />,
    );
    expect(
      screen.getByText("Для сервиса-поставщика укажите группу точек входа."),
    ).toBeTruthy();
    expect(
      screen.getByText("Для сервиса-поставщика укажите виртуальные IP-адреса."),
    ).toBeTruthy();
    expect(
      screen.getAllByText("ENDPOINT_PROVIDER_FIELD_REQUIRED"),
    ).toHaveLength(2);
    expect(
      screen.queryByText(
        "Endpoint provider deployment requires endpointGroupRef",
      ),
    ).toBeNull();
  });

  it("never offers Start for a draft or an approved plan bound to an old revision", () => {
    const onStart = vi.fn();
    const onCreatePlan = vi.fn();
    const plan = {
      status: "PLAN_APPROVED" as const,
      plan: {
        id: "plan-old",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: true,
        acknowledgements: [],
        phases: [],
      },
    };
    const view = render(
      <InstallationPage
        state={currentPlanState("plan-old", "sha256:old", true)}
        draftActive
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={onCreatePlan}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        plan={plan}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Начать выполнение" }),
    ).toHaveProperty("disabled", true);
    view.rerender(
      <InstallationPage
        state={{
          ...currentPlanState("plan-old", "sha256:new", true),
          status: "READY_TO_PLAN",
          plan: { status: "PLAN_STALE_OR_EXPIRED" },
        }}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={onCreatePlan}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        plan={plan}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Начать выполнение" }),
    ).toHaveProperty("disabled", true);
    expect(
      screen.getByRole("button", { name: "Сформировать свежий план" }),
    ).toHaveProperty("disabled", false);
    view.rerender(
      <InstallationPage
        state={undefined}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={onCreatePlan}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        plan={plan}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Начать выполнение" }),
    ).toHaveProperty("disabled", true);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("shows all known reasons when the approved plan cannot start", () => {
    const onStart = vi.fn();
    const plan = {
      status: "PLAN_APPROVED" as const,
      plan: {
        id: "plan-pki",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: true,
        pkiStorePasswordRequired: true,
        acknowledgements: [],
        phases: [],
        findings: [
          {
            code: "PROJECT_VALIDATION_BLOCKED",
            safeMessage: "Authoritative project validation is blocked",
          },
        ],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-pki", "sha256:old", true)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        onStart={onStart}
        plan={plan}
        credentialStatus={{
          status: "PRESENT",
          sudoPasswordStatus: "NOT_PROVIDED",
          pkiStorePasswordStatus: "MISSING",
        }}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Начать выполнение" }),
    ).toHaveProperty("disabled", true);
    expect(screen.queryByRole("button", { name: /Сертификаты/ })).toBeNull();
    const blockers = screen.getByRole("list", {
      name: "Причины недоступности запуска",
    });
    expect(
      within(blockers).getByText(
        "В сеансе не задан пароль хранилищ PKCS#12, необходимый плану.",
      ),
    ).toBeTruthy();
    expect(
      within(blockers).getByText(
        "Проверка проекта выявила ошибки; план установки заблокирован.",
      ),
    ).toBeTruthy();
    expect(onStart).not.toHaveBeenCalled();
  });

  it("shows approval error code in a card before protected output settings", () => {
    render(
      <InstallationPage
        state={currentPlanState("plan-1", "sha256:old", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        plan={{
          status: "PLAN_REVIEW",
          error: {
            code: "INSTALLATION_SECRETS_MISSING",
            message: "Задайте пароль сервиса postgres-desktop.",
          },
          plan: {
            id: "plan-1",
            status: "EXECUTABLE",
            projectRevision: "sha256:old",
            planFingerprint: "sha256:plan",
            executionNodeId: "node1",
            runtime: {
              bundleDigest: "sha256:bundle",
              coreVersion: "core",
              catalogDigest: "sha256:catalog",
              protocol: "protocol",
            },
            expiresAt: "2026-09-22T10:00:00Z",
            approved: false,
            acknowledgements: [],
            phases: [],
            secretOutputEncryptionRequired: true,
            secretOutputEncryptionPasswordPresent: true,
          },
        }}
      />,
    );
    const heading = screen.getByRole("heading", {
      name: "Новый план установки",
    });
    const alert = screen.getByRole("alert");
    const output = screen.getByText(/Защищённые выходные файлы/);
    expect(
      within(alert).getByText("INSTALLATION_SECRETS_MISSING"),
    ).toBeTruthy();
    expect(alert.textContent).toContain(
      "Задайте пароль сервиса postgres-desktop.",
    );
    expect(
      heading.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      alert.compareDocumentPosition(output) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("focuses the error card after each failed approval, including the same error twice", () => {
    const operation = {
      status: "PLAN_REVIEW" as const,
      error: {
        code: "INSTALLATION_SECRETS_MISSING",
        message: "Задайте пароль сервиса.",
      },
      plan: {
        id: "plan-1",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: false,
        acknowledgements: [],
        phases: [],
      },
    };
    const common = {
      state: currentPlanState("plan-1", "sha256:old", false),
      tab: "plan" as const,
      onTabChange: vi.fn(),
      onOpenServers: vi.fn(),
      busy: false,
      onCreatePlan: vi.fn(),
      onApprovePlan: vi.fn(),
      plan: operation,
    };
    const view = render(
      <InstallationPage {...common} approvalErrorAttempt={0} />,
    );
    const alert = screen.getByRole("alert");
    expect(document.activeElement).not.toBe(alert);
    view.rerender(<InstallationPage {...common} approvalErrorAttempt={1} />);
    expect(document.activeElement).toBe(alert);
    screen.getByRole("button", { name: "Одобрить план" }).focus();
    view.rerender(<InstallationPage {...common} approvalErrorAttempt={2} />);
    expect(document.activeElement).toBe(alert);
  });

  it("requires the common output password and uses the default secrets folder before plan approval", async () => {
    const user = userEvent.setup();
    const onApprovePlan = vi.fn();
    const setOutputPassword = vi.fn().mockResolvedValue(undefined);
    const plan = {
      status: "PLAN_REVIEW" as const,
      plan: {
        id: "plan-vault",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:revision",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-26T10:00:00Z",
        approved: false,
        secretOutputEncryptionRequired: true,
        secretOutputEncryptionPasswordPresent: false,
        acknowledgements: [{ code: "ACK_RISK", summary: "Review changes" }],
        phases: [],
      },
    };
    const view = render(
      <InstallationPage
        state={currentPlanState("plan-vault", "sha256:revision", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={onApprovePlan}
        plan={plan}
        onSetOutputEncryptionPassword={setOutputPassword}
      />,
    );
    const approve = screen.getByRole("button", { name: "Одобрить план" });
    expect(approve).toHaveProperty("disabled", true);
    await user.type(screen.getByLabelText("Пароль шифрования"), "session-only");
    await user.type(screen.getByLabelText("Повторите пароль"), "session-only");
    await user.click(
      screen.getByRole("button", { name: "Сохранить пароль в сеансе" }),
    );
    await user.click(screen.getByRole("checkbox", { name: /ACK_RISK/ }));
    expect(approve).toHaveProperty("disabled", false);
    await user.click(approve);
    expect(setOutputPassword).toHaveBeenCalledWith(
      "session-only",
      "session-only",
    );
    expect(onApprovePlan).toHaveBeenCalledWith("plan-vault", ["ACK_RISK"]);
    // Fresh backend state after expiry must override the previous local ACK.
    view.rerender(
      <InstallationPage
        state={currentPlanState("plan-vault", "sha256:revision", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={onApprovePlan}
        plan={{
          ...plan,
          plan: { ...plan.plan, secretOutputEncryptionPasswordPresent: false },
        }}
        onSetOutputEncryptionPassword={setOutputPassword}
      />,
    );
    expect(screen.getByLabelText("Пароль шифрования")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Одобрить план" }),
    ).toHaveProperty("disabled", true);
    view.rerender(
      <InstallationPage
        state={currentPlanState("replacement-plan", "sha256:revision", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={onApprovePlan}
        plan={{
          ...plan,
          plan: {
            ...plan.plan,
            id: "replacement-plan",
            secretOutputEncryptionPasswordPresent: false,
          },
        }}
        onSetOutputEncryptionPassword={setOutputPassword}
      />,
    );
    expect(screen.getByLabelText("Пароль шифрования")).toBeTruthy();
  });

  it("shows a Russian error when the session output passwords do not match", async () => {
    const user = userEvent.setup();
    const plan = {
      status: "PLAN_REVIEW" as const,
      plan: {
        id: "plan-password",
        status: "EXECUTABLE" as const,
        projectRevision: "sha256:old",
        planFingerprint: "sha256:plan",
        executionNodeId: "node1",
        runtime: {
          bundleDigest: "sha256:bundle",
          coreVersion: "core",
          catalogDigest: "sha256:catalog",
          protocol: "protocol",
        },
        expiresAt: "2026-09-22T10:00:00Z",
        approved: false,
        secretOutputEncryptionRequired: true,
        acknowledgements: [],
        phases: [],
      },
    };
    render(
      <InstallationPage
        state={currentPlanState("plan-password", "sha256:old", false)}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        plan={plan}
        onSetOutputEncryptionPassword={vi
          .fn()
          .mockRejectedValue("SECRET_OUTPUT_PASSWORD_INVALID")}
      />,
    );
    await user.type(
      screen.getByLabelText("Пароль шифрования"),
      "first-session-value",
    );
    await user.type(
      screen.getByLabelText("Повторите пароль"),
      "second-session-value",
    );
    await user.click(
      screen.getByRole("button", { name: "Сохранить пароль в сеансе" }),
    );
    expect(
      screen.getByText(
        "Пароли шифрования не совпадают или не подходят. Проверьте оба поля.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("SECRET_OUTPUT_PASSWORD_INVALID")).toBeNull();
  });

  it("shows only safe output-delivery status and package metadata", async () => {
    const user = userEvent.setup();
    const refresh = vi.fn();
    const deliver = vi.fn().mockResolvedValue(undefined);
    render(
      <InstallationPage
        state={state}
        tab="result"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        secretOutputPackages={{
          status: "READY",
          packages: [
            {
              protocol: "SecretOutputDelivery/v1alpha1",
              packageId: "pkg-safe",
              projectId: "project-1",
              deploymentId: "vault-ha",
              sourceRunId: "run-safe",
              runtimeDigest: "sha256:runtime",
              generation: 1,
              state: "READY",
              entries: ["admin-token", "unseal-shares"],
            },
          ],
        }}
        outputDelivery={{
          status: "DELIVERED",
          directory: "C:\\VaultSecrets\\vault-ha",
        }}
        onRefreshSecretOutputs={refresh}
        onCollectSecretOutputs={deliver}
      />,
    );
    expect(
      screen.getByText(
        "Зашифрованные файлы сохранены: C:\\VaultSecrets\\vault-ha",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("DELIVERED")).toBeNull();
    expect(screen.getByText(/Защищённый пакет · vault-ha/)).toBeTruthy();
    expect(screen.getByText(/Состояние: Ожидает получения/)).toBeTruthy();
    expect(screen.queryByText(/Состояние: READY/)).toBeNull();
    expect(screen.queryByText(/root token|unseal key/i)).toBeNull();
    await user.click(
      screen.getByRole("button", {
        name: "Проверить и сохранить зашифрованные файлы",
      }),
    );

    expect(refresh).not.toHaveBeenCalled();
    expect(deliver).toHaveBeenCalledOnce();
  });

  it("hides collection after verified local delivery", () => {
    render(
      <InstallationPage
        state={state}
        tab="result"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        secretOutputPackages={{
          status: "READY",
          packages: [
            {
              protocol: "SecretOutputDelivery/v1alpha1",
              packageId: "pkg-safe",
              projectId: "project-1",
              deploymentId: "vault-ha",
              sourceRunId: "run-safe",
              runtimeDigest: "sha256:runtime",
              generation: 1,
              state: "LOCAL_DELIVERED",
              entries: ["admin-token", "unseal-shares"],
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/Состояние: Сохранён на инсталлере/)).toBeTruthy();
    expect(
      screen.queryByRole("button", {
        name: "Проверить и сохранить зашифрованные файлы",
      }),
    ).toBeNull();
    expect(screen.queryByText(/Ожидает получения/)).toBeNull();
  });

  it("blocks fresh plan creation while a run is active without a plan snapshot", () => {
    render(
      <InstallationPage
        state={state}
        tab="plan"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        run={
          new desktop.InstallationRunOperation({
            status: "RUNNING",
            run: { runId: "run-1", state: "RUNNING", sequence: 1 },
          })
        }
      />,
    );
    expect(
      screen.getByRole("button", { name: "Подготовка образов и плана…" }),
    ).toHaveProperty("disabled", true);
  });

  it("shows a safe delivery failure without exposing transport details", () => {
    render(
      <InstallationPage
        state={state}
        tab="result"
        onTabChange={vi.fn()}
        onOpenServers={vi.fn()}
        busy={false}
        onCreatePlan={vi.fn()}
        onApprovePlan={vi.fn()}
        outputDelivery={{
          status: "UNAVAILABLE",
          error: {
            code: "SECRET_OUTPUT_DELIVERY_FAILED",
            message:
              "Не удалось получить защищённые выходные файлы. Проверьте подключение и повторите попытку.",
          },
        }}
        onRefreshSecretOutputs={vi.fn()}
        onCollectSecretOutputs={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain(
      "Не удалось получить защищённые выходные файлы",
    );
    expect(screen.queryByText("SECRET_OUTPUT_DELIVERY_FAILED")).toBeNull();
  });
});

import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { InstallationEventView } from "./backend";
import { eventTimestampLabel } from "./event-format";
import { UtilityPages } from "./UtilityPages";

function event(sequence: number): InstallationEventView {
  return {
    runId: "run-current",
    sequence,
    timestamp: `2026-10-06T18:30:${String(sequence % 60).padStart(2, "0")}Z`,
    eventType: "TASK_COMPLETED",
    status: "SUCCESS",
    phaseId: "apply",
    actionId: "apply:service",
    host: "node1",
    serviceDeployment: "service-1",
    task: {
      role: "service",
      name: `service : task-${sequence}`,
      uuid: `uuid-${sequence}`,
    },
    elapsedMilliseconds: 15,
    safeMessage: `Задача ${sequence} завершена`,
    redacted: true,
  } as InstallationEventView;
}

function renderLogs(events: InstallationEventView[]) {
  return render(
    <UtilityPages
      page="logs"
      events={events}
      runId="run-current"
      serverTypes={[]}
      configError={null}
    />,
  );
}

describe("UtilityPages logs", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("renders every event field through hideable columns and details", () => {
    renderLogs([event(1)]);
    expect(screen.getByRole("columnheader", { name: "Время" })).toBeTruthy();
    expect(
      screen.getByRole("cell", {
        name: eventTimestampLabel(event(1).timestamp),
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole("columnheader", { name: "Сообщение" }),
    ).toBeTruthy();
    expect(screen.getAllByText("Задача 1 завершена").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Колонки (6 из 17)"));
    const taskColumnToggle = screen.getByLabelText("Задача");
    fireEvent.click(screen.getByLabelText("Роль задачи"));
    fireEvent.click(taskColumnToggle);
    expect(screen.getByRole("columnheader", { name: "Задача" })).toBeTruthy();
    const table = screen.getByRole("table");
    expect(within(table).getByText("task-1")).toBeTruthy();
    expect(within(table).getByText("service")).toBeTruthy();
    expect(within(table).queryByText("service : task-1")).toBeNull();
    fireEvent.click(taskColumnToggle);
    expect(screen.queryByRole("columnheader", { name: "Задача" })).toBeNull();
  });

  it("shows newest events first and pages older events last in batches of 512", () => {
    renderLogs(Array.from({ length: 513 }, (_, index) => event(index + 1)));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(513);
    expect(screen.getByText("Показаны 1–512 из 513")).toBeTruthy();
    const newestPageRows = within(table).getAllByRole("row");
    expect(newestPageRows[1].textContent).toContain("Задача 513 завершена");
    expect(newestPageRows.at(-1)?.textContent).toContain("Задача 2 завершена");
    fireEvent.click(screen.getByRole("button", { name: "Далее" }));
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("Показаны 513–513 из 513")).toBeTruthy();
    expect(within(table).getByText("Задача 1 завершена")).toBeTruthy();
  });

  it("searches all current-run events rather than only the visible page", () => {
    renderLogs(Array.from({ length: 513 }, (_, index) => event(index + 1)));
    fireEvent.change(screen.getByPlaceholderText("Сообщение, задача, узел…"), {
      target: { value: "Задача 513 завершена" },
    });
    expect(screen.getByText("Показаны 1–1 из 1")).toBeTruthy();
    expect(screen.getAllByText("Задача 513 завершена").length).toBeGreaterThan(
      0,
    );
  });

  it("moves a newly received event to the top of the newest-first page", () => {
    const view = renderLogs([event(1), event(2)]);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")[1].textContent).toContain(
      "Задача 2 завершена",
    );

    view.rerender(
      <UtilityPages
        page="logs"
        events={[event(1), event(2), event(3)]}
        runId="run-current"
        serverTypes={[]}
        configError={null}
      />,
    );

    expect(within(table).getAllByRole("row")[1].textContent).toContain(
      "Задача 3 завершена",
    );
  });

  it("retains selected columns when the logs page is reopened in the session", () => {
    const firstView = renderLogs([event(1)]);
    fireEvent.click(screen.getByText("Колонки (6 из 17)"));
    fireEvent.click(screen.getByLabelText("Роль задачи"));
    firstView.unmount();

    renderLogs([event(1)]);

    expect(screen.getByText("Колонки (7 из 17)")).toBeTruthy();
    expect(
      screen.getByRole("columnheader", { name: "Роль задачи" }),
    ).toBeTruthy();
  });
});

describe("UtilityPages help", () => {
  it("shows six topics, opens an article, and navigates to its page", () => {
    const onNavigate = vi.fn();
    render(
      <UtilityPages
        page="help"
        events={[]}
        serverTypes={[]}
        configError={null}
        onNavigate={onNavigate}
      />,
    );

    const topics = [
      "Проект и набор",
      "Серверы",
      "Сервисы и топология",
      "Проверка и установка",
      "Журналы",
      "Ошибки",
    ];
    for (const topic of topics) {
      expect(
        screen.getByRole("button", { name: new RegExp(topic) }),
      ).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("button", { name: /Серверы/ }));
    expect(
      screen.getByRole("heading", { name: "Добавление сервера" }),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "Открыть страницу «Серверы»" }),
    );
    expect(onNavigate).toHaveBeenCalledWith("servers");
  });

  it("explains how to check the real run state and latest safe events on Execution Node", () => {
    render(
      <UtilityPages
        page="help"
        events={[]}
        serverTypes={[]}
        configError={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Ошибки/ }));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Если страница «Выполнение» перестала обновляться",
      }),
    );

    expect(
      screen.getByRole("heading", {
        name: "Если страница «Выполнение» перестала обновляться",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        /Потеря связи с Execution Node не означает, что выполнение завершилось/,
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Не запускайте операцию повторно/)).toBeTruthy();
  });
});

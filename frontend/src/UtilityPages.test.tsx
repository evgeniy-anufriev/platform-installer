import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { InstallationEventView } from "./backend";
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
      name: `task-${sequence}`,
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
  it("renders every event field through hideable columns and details", () => {
    renderLogs([event(1)]);
    expect(screen.getByRole("columnheader", { name: "Время" })).toBeTruthy();
    expect(
      screen.getByRole("columnheader", { name: "Сообщение" }),
    ).toBeTruthy();
    expect(screen.getAllByText("Задача 1 завершена").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Колонки (6 из 17)"));
    const taskColumnToggle = screen.getByLabelText("Задача");
    fireEvent.click(taskColumnToggle);
    expect(screen.getByRole("columnheader", { name: "Задача" })).toBeTruthy();
    fireEvent.click(taskColumnToggle);
    expect(screen.queryByRole("columnheader", { name: "Задача" })).toBeNull();
  });

  it("pages through all events in batches of 512", () => {
    renderLogs(Array.from({ length: 513 }, (_, index) => event(index + 1)));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(513);
    expect(screen.getByText("Показаны 1–512 из 513")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Далее" }));
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText("Показаны 513–513 из 513")).toBeTruthy();
    expect(screen.getAllByText("Задача 513 завершена").length).toBeGreaterThan(
      0,
    );
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
});


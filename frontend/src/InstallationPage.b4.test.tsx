import { desktop } from "../wailsjs/go/models";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect, vi } from "vitest";
import { InstallationPage } from "./InstallationPage";
import type { InstallationPlanOperation } from "./backend";

const defaults = {
  tab: "plan" as const,
  onTabChange: vi.fn(),
  onOpenServers: vi.fn(),
  busy: false,
  onApprovePlan: vi.fn(),
  state: {
    status: "PLAN_APPROVED" as const,
    project: { id: "p", revision: "sha256:rev", hasUnsavedChanges: false },
    executionNode: { status: "READY" },
    plan: { status: "PLAN_APPROVED" as const, planId: "full" },
    prerequisites: [],
  } as never,
};
const fullPlan: InstallationPlanOperation = {
  status: "PLAN_APPROVED",
  plan: {
    id: "full",
    executionMode: "FULL_PROJECT",
    status: "EXECUTABLE",
    projectRevision: "sha256:rev",
    planFingerprint: "sha256:fp",
    executionNodeId: "node",
    runtime: {
      bundleDigest: "sha256:b",
      coreVersion: "core",
      catalogDigest: "sha256:c",
      protocol: "p",
    },
    expiresAt: "2099-01-01",
    approved: true,
    acknowledgements: [],
    phases: [
      {
        id: "services",
        order: 0,
        actions: [
          {
            id: "infra",
            type: "SERVICE_APPLY",
            serviceDeployment: "db",
            targets: ["node"],
            dependsOn: [],
            mutating: true,
            reboot: "NONE",
            summary: "Infra action",
          },
          {
            id: "infra-verify",
            type: "SERVICE_VERIFY",
            serviceDeployment: "db",
            targets: ["node"],
            dependsOn: ["infra"],
            mutating: false,
            reboot: "NONE",
            summary: "Infra verify",
          },
        ],
      },
    ],
  },
};
it("owner amendment offers execution controls before Build and on Summary", () => {
  const view = render(
    <InstallationPage {...defaults} onCreatePlan={vi.fn()} />,
  );
  expect(
    screen.queryByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  ).toBeTruthy();
  view.rerender(
    <InstallationPage
      {...defaults}
      tab="summary"
      plan={fullPlan}
      onCreatePlan={vi.fn()}
    />,
  );
  expect(
    screen.queryByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  ).toBeTruthy();
});
it("B4 excludes infrastructure, leaves libraries Apply/Verify and requests only that scope", async () => {
  const create = vi.fn();
  render(
    <InstallationPage {...defaults} plan={fullPlan} onCreatePlan={create} />,
  );
  const checkbox = screen.getByRole("checkbox", {
    name: "Устанавливать инфраструктуру",
  });
  expect(checkbox).toHaveProperty("checked", true);
  await userEvent.click(checkbox);
  expect(
    screen.getByText(
      /При отсутствии актуального Verify Core включит проверку инфраструктуры/,
    ),
  ).toBeTruthy();
  expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  expect(screen.queryByText("Установить сервис db")).toBeNull();
  expect(screen.getByText("Проверить сервис db")).toBeTruthy();
  expect(create).not.toHaveBeenCalled();
  expect(
    checkbox
      .closest(".plan-phase-card")
      ?.classList.contains("installation-phase-excluded"),
  ).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Одобрить план" }));
  expect(create).not.toHaveBeenCalled();
  expect(defaults.onApprovePlan).toHaveBeenCalledWith("full", []);
});
it("requires a fresh plan when Infra Verify skip changes in either direction", async () => {
  const create = vi.fn();
  const props = {
    ...defaults,
    selectedExecutionMode: "APPLICATION_LIBRARIES_ONLY" as const,
    onCreatePlan: create,
  };
  const plan = {
    ...fullPlan,
    plan: {
      ...fullPlan.plan!,
      executionMode: "APPLICATION_LIBRARIES_ONLY" as const,
      skipInfrastructureVerify: false,
    },
  };
  const view = render(<InstallationPage {...props} plan={plan} />);
  await userEvent.click(
    screen.getByRole("checkbox", {
      name: "Пропустить проверку инфраструктуры — принимаю риски",
    }),
  );
  expect(screen.getByRole("button", { name: "Одобрить план" })).toHaveProperty(
    "disabled",
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  expect(create).toHaveBeenLastCalledWith(
    [],
    "APPLICATION_LIBRARIES_ONLY",
    true,
  );
  view.rerender(
    <InstallationPage
      {...props}
      plan={{ ...plan, plan: { ...plan.plan, skipInfrastructureVerify: true } }}
    />,
  );
  await userEvent.click(
    screen.getByRole("checkbox", {
      name: "Пропустить проверку инфраструктуры — принимаю риски",
    }),
  );
  expect(screen.getByRole("button", { name: "Одобрить план" })).toHaveProperty(
    "disabled",
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  expect(create).toHaveBeenLastCalledWith([], "APPLICATION_LIBRARIES_ONLY");
});
it("B4 never filters actions from an authoritative Core plan for the selected scope", () => {
  const libraryModePlan: InstallationPlanOperation = {
    ...fullPlan,
    plan: { ...fullPlan.plan!, executionMode: "APPLICATION_LIBRARIES_ONLY" },
  };
  render(
    <InstallationPage
      {...defaults}
      plan={libraryModePlan}
      selectedExecutionMode="APPLICATION_LIBRARIES_ONLY"
      onCreatePlan={vi.fn()}
    />,
  );
  expect(screen.getByText("Установить сервис db")).toBeTruthy();
});
it("B4 hides approval for a plan from a different selected scope", async () => {
  const plan: InstallationPlanOperation = {
    status: "PLAN_APPROVED",
    plan: {
      id: "old",
      executionMode: "FULL_PROJECT",
      status: "EXECUTABLE",
      projectRevision: "sha256:rev",
      planFingerprint: "sha256:fp",
      executionNodeId: "node",
      runtime: {
        bundleDigest: "sha256:b",
        coreVersion: "core",
        catalogDigest: "sha256:c",
        protocol: "p",
      },
      expiresAt: "2099-01-01",
      approved: true,
      acknowledgements: [],
      phases: [],
    },
  };
  render(<InstallationPage {...defaults} plan={plan} onCreatePlan={vi.fn()} />);
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  );
  expect(
    screen.queryByRole("button", { name: "Начать выполнение" }),
  ).toBeNull();
  expect(screen.getByText(/Состав запуска изменён/)).toBeTruthy();
});
it("B4 cached observation remains UNKNOWN and does not claim current verification", () => {
  render(
    <InstallationPage
      {...defaults}
      onCreatePlan={vi.fn()}
      infrastructureObservation={{
        availability: "UNKNOWN",
        observedAt: "2026-10-14T12:00:00Z",
      }}
    />,
  );
  expect(
    screen.getByText(/Предыдущее наблюдение инфраструктуры: UNKNOWN/),
  ).toBeTruthy();
  expect(screen.queryByText("Инфраструктура проверена")).toBeNull();
});

it("B4 resets risk acknowledgement when Core returns a replacement plan", async () => {
  const riskPlan: InstallationPlanOperation = {
    ...fullPlan,
    status: "PLAN_REVIEW",
    plan: {
      ...fullPlan.plan!,
      approved: false,
      acknowledgements: [{ code: "RISK", summary: "Original risk" }],
    },
  };
  const replacement: InstallationPlanOperation = {
    ...riskPlan,
    plan: {
      ...riskPlan.plan!,
      id: "replacement",
      acknowledgements: [{ code: "RISK", summary: "Changed risk details" }],
    },
  };
  const view = render(
    <InstallationPage
      {...defaults}
      state={
        {
          status: "PLAN_REVIEW",
          project: {
            id: "p",
            revision: "sha256:rev",
            hasUnsavedChanges: false,
          },
          executionNode: { status: "READY" },
          plan: { status: "PLAN_REVIEW", planId: "full" },
          prerequisites: [],
        } as never
      }
      plan={riskPlan}
      onCreatePlan={vi.fn()}
    />,
  );
  const acknowledgement = screen.getByRole("checkbox", {
    name: /Original risk/,
  });
  await userEvent.click(acknowledgement);
  expect(acknowledgement).toHaveProperty("checked", true);
  view.rerender(
    <InstallationPage
      {...defaults}
      state={
        {
          status: "PLAN_REVIEW",
          project: {
            id: "p",
            revision: "sha256:rev",
            hasUnsavedChanges: false,
          },
          executionNode: { status: "READY" },
          plan: { status: "PLAN_REVIEW", planId: "replacement" },
          prerequisites: [],
        } as never
      }
      plan={replacement}
      onCreatePlan={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("checkbox", { name: /Changed risk details/ }),
  ).toHaveProperty("checked", false);
});

it("B4 locks the services scope during an active run", () => {
  render(
    <InstallationPage
      {...defaults}
      plan={fullPlan}
      runPlan={fullPlan.plan}
      run={
        new desktop.InstallationRunOperation({
          status: "READY",
          run: { runId: "run-current", state: "RUNNING", sequence: 1 },
        })
      }
      onCreatePlan={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("checkbox", { name: "Устанавливать инфраструктуру" }),
  ).toHaveProperty("disabled", true);
});

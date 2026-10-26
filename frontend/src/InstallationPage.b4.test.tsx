import { desktop, executionnode } from "../wailsjs/go/models";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect, vi } from "vitest";
import {
  InstallationPage,
  libraryOrderFromPriorities,
} from "./InstallationPage";
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

it("keeps library selection and Vault source in the applications phase", () => {
  const plan = {
    ...fullPlan,
    plan: {
      ...fullPlan.plan!,
      phases: [
        ...fullPlan.plan!.phases,
        {
          id: "applications",
          order: 2,
          actions: [
            {
              id: "applications:apply",
              type: "APPLICATION_LIBRARIES_APPLY",
              targets: ["node"],
              dependsOn: [],
              mutating: true,
              reboot: "NONE",
              summary: "Libraries",
            },
          ],
        },
      ],
    },
  };
  render(
    <InstallationPage
      {...defaults}
      plan={plan}
      onCreatePlan={vi.fn()}
      serviceDeployments={[
        { deploymentId: "vault-main", serviceType: "vault" },
      ]}
      libraryDeployments={[{ deploymentId: "szi", libraryRef: "szi@1.0.0" }]}
      onApplicationVaultSourcesChange={vi.fn()}
    />,
  );
  const services = screen
    .getByText("services · Инфраструктура")
    .closest("details")!;
  const libraries = screen
    .getAllByText("Библиотеки")
    .map((element) => element.closest("details"))
    .find(Boolean)!;
  expect(
    within(services).getByRole("checkbox", {
      name: "Устанавливать инфраструктуру",
    }),
  ).toBeTruthy();
  expect(
    within(services).queryByRole("checkbox", {
      name: "Установить библиотеку szi",
    }),
  ).toBeNull();
  expect(
    within(services).queryByRole("combobox", {
      name: "Источник токена Vault · vault-main",
    }),
  ).toBeNull();
  expect(
    within(libraries).getByRole("checkbox", {
      name: "Установить библиотеку szi",
    }),
  ).toBeTruthy();
  expect(
    within(libraries).getByRole("combobox", {
      name: "Источник токена Vault · vault-main",
    }),
  ).toBeTruthy();
});

it.each([
  ["FULL_PROJECT", false, false],
  ["APPLICATION_LIBRARIES_ONLY", false, true],
  ["APPLICATION_LIBRARIES_ONLY", true, false],
] as const)(
  "renders prior Infra Verify gate only when applicable: %s/%s",
  (mode, skip, visible) => {
    render(
      <InstallationPage
        {...defaults}
        onCreatePlan={vi.fn()}
        plan={{
          ...fullPlan,
          plan: {
            ...fullPlan.plan!,
            executionMode: mode,
            skipInfrastructureVerify: skip,
            infrastructureVerification:
              new executionnode.InfrastructureVerification({
                status: "BLOCKED",
                code: "INFRA_VERIFY_MISSING",
                deployments: [],
              }),
          },
        }}
      />,
    );
    expect(screen.queryByText(/BLOCKED.*INFRA_VERIFY_MISSING/) !== null).toBe(
      visible,
    );
    expect(
      screen.queryByText("Advanced: источники инфраструктурных Verify"),
    ).toBeNull();
  },
);
it("orders selected libraries from configured priorities and rejects an unknown name", () => {
  const deployments = [
    { deploymentId: "sdku-east", libraryRef: "sdku@1.0.0" },
    { deploymentId: "szi", libraryRef: "szi@1.0.0" },
    { deploymentId: "sdku-west", libraryRef: "sdku@1.0.0" },
  ];
  expect(
    libraryOrderFromPriorities(deployments, [
      { libraryName: "sdku", priority: 1 },
      { libraryName: "szi", priority: 0 },
    ]),
  ).toEqual({ order: ["szi", "sdku-east", "sdku-west"], missingNames: [] });
  expect(
    libraryOrderFromPriorities(deployments, [
      { libraryName: "szi", priority: 0 },
    ]),
  ).toEqual({ order: [], missingNames: ["sdku"] });
});

it.each(["STARTING", "RUNNING", "CANCELLING"])(
  "does not call the active run plan stale: %s",
  (state) => {
    render(
      <InstallationPage
        {...defaults}
        plan={fullPlan}
        runPlan={fullPlan.plan}
        onCreatePlan={vi.fn()}
        run={
          new desktop.InstallationRunOperation({
            status: "READY",
            run: { runId: "active", state, sequence: 1 },
          })
        }
      />,
    );
    expect(screen.queryByText(/Этот план нельзя использовать/)).toBeNull();
  },
);
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

it("Stage3 binds skipped library IDs to a fresh plan and blocks the old Start", async () => {
  const create = vi.fn();
  render(
    <InstallationPage
      {...defaults}
      plan={fullPlan}
      onCreatePlan={create}
      libraryDeployments={[
        { deploymentId: "identity-east", libraryRef: "szi@1.0.0" },
        { deploymentId: "sdku-one", libraryRef: "sdku@1.0.0" },
      ]}
      libraryExecutionPriorities={[
        { libraryName: "szi", priority: 0 },
        { libraryName: "sdku", priority: 1 },
      ]}
    />,
  );
  expect(
    screen.getByRole("checkbox", {
      name: "Установить библиотеку identity-east",
    }),
  ).toHaveProperty("checked", true);
  expect(
    screen.getByRole("checkbox", { name: "Установить библиотеку sdku-one" }),
  ).toHaveProperty("checked", true);
  await userEvent.click(
    screen.getByRole("checkbox", {
      name: "Установить библиотеку identity-east",
    }),
  );
  expect(screen.queryByRole("button", { name: "Начать установку" })).toBeNull();
  expect(screen.getByRole("button", { name: "Одобрить план" })).toHaveProperty(
    "disabled",
    true,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сформировать свежий план" }),
  );
  expect(create).toHaveBeenCalledWith(
    expect.any(Array),
    "FULL_PROJECT",
    false,
    ["identity-east", "sdku-one"],
    ["identity-east"],
  );
});

it("Stage3 locks library selection during execution", () => {
  render(
    <InstallationPage
      {...defaults}
      plan={fullPlan}
      runPlan={fullPlan.plan}
      onCreatePlan={vi.fn()}
      libraryDeployments={[
        { deploymentId: "identity", libraryRef: "szi@1.0.0" },
      ]}
      run={
        new desktop.InstallationRunOperation({
          status: "READY",
          run: { runId: "running", state: "RUNNING", sequence: 1 },
        })
      }
    />,
  );
  expect(
    screen.getByRole("checkbox", { name: "Установить библиотеку identity" }),
  ).toHaveProperty("disabled", true);
});

it("Stage3 restores the Core plan selection when reopening the Plan tab", () => {
  render(
    <InstallationPage
      {...defaults}
      plan={{
        ...fullPlan,
        plan: { ...fullPlan.plan!, skipApplicationLibraries: ["identity"] },
      }}
      onCreatePlan={vi.fn()}
      libraryDeployments={[
        { deploymentId: "identity", libraryRef: "szi@1.0.0" },
      ]}
    />,
  );
  expect(
    screen.getByRole("checkbox", { name: "Установить библиотеку identity" }),
  ).toHaveProperty("checked", false);
  expect(
    screen.getByText(/Установка библиотек пропущена: identity/),
  ).toBeTruthy();
});

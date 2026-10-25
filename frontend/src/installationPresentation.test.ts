import { describe, expect, it } from "vitest";
import type { InstallationEventView, InstallationPlanView } from "./backend";
import {
  actionResultLabel,
  beginRunProgress,
  installationDisplay,
  observeRunEvent,
  installationActionRows,
} from "./installationPresentation";

const plan = {
  id: "plan-1",
  status: "EXECUTABLE",
  projectRevision: "sha256:project",
  planFingerprint: "sha256:plan",
  executionNodeId: "node1",
  runtime: {
    bundleDigest: "sha256:bundle",
    coreVersion: "core",
    catalogDigest: "sha256:catalog",
    protocol: "protocol",
  },
  expiresAt: "2026-10-04T12:00:00Z",
  approved: true,
  acknowledgements: [],
  phases: [
    {
      id: "apply",
      order: 0,
      actions: [
        {
          id: "apply:one",
          type: "SERVICE_APPLY",
          serviceDeployment: "one",
          targets: ["node1"],
          dependsOn: [],
          mutating: true,
          reboot: "NONE",
          summary: "Apply one",
        },
        {
          id: "verify:one",
          type: "SERVICE_VERIFY",
          serviceDeployment: "one",
          targets: ["node1"],
          dependsOn: ["apply:one"],
          mutating: false,
          reboot: "NONE",
          summary: "Verify one",
        },
      ],
    },
  ],
} as InstallationPlanView;

const event = (
  sequence: number,
  eventType: string,
  actionId?: string,
  runId = "run-1",
): InstallationEventView =>
  ({
    apiVersion: "platform.installer/event/v1alpha1",
    kind: "InstallationEventView",
    runId,
    sequence,
    timestamp: "2026-10-04T12:00:00Z",
    eventType,
    status: "SUCCESS",
    actionId,
    safeMessage: "safe",
    redacted: true,
  }) as unknown as InstallationEventView;

describe("installation status presentation", () => {
  it("counts library leaves once and restores the same progress after replay", () => {
    const nested = structuredClone(plan);
    const apply = nested.phases[0].actions[0];
    apply.id = "applications:apply";
    apply.type = "APPLICATION_LIBRARIES_APPLY";
    apply.progressSteps = [
      { id: "applications:prepare", summary: "Prepare" },
      { id: "applications:library:sdku", summary: "SDKU" },
      { id: "applications:library:cspa", summary: "CSPA" },
    ];
    const events = [
      event(1, "ACTION_STARTED", apply.id),
      event(2, "ACTION_STARTED", "applications:prepare"),
      event(3, "ACTION_COMPLETED", "applications:prepare"),
      event(4, "ACTION_STARTED", "applications:library:sdku"),
      event(5, "TASK_COMPLETED", apply.id),
      event(6, "ACTION_COMPLETED", "applications:library:sdku"),
      event(7, "ACTION_STARTED", "applications:library:cspa"),
    ];
    const progress = events.reduce(
      observeRunEvent,
      beginRunProgress("run-1", nested),
    );
    expect(progress.actionIds).toHaveLength(4);
    expect(progress.activeActionId).toBe("applications:library:cspa");
    expect(
      installationDisplay(
        undefined,
        { run: { state: "RUNNING" } } as never,
        progress,
      ).percent,
    ).toBe(50);
    expect(installationActionRows(nested)).toHaveLength(5);
    const replay = [...events, events[5]].reduce(
      observeRunEvent,
      beginRunProgress("run-1", nested),
    );
    expect(replay.completedActionIds).toEqual(progress.completedActionIds);
    expect(replay.activeActionId).toBe(progress.activeActionId);
    // The controller reports failure through task/diagnostic and terminal state,
    // without a fabricated parent ACTION_COMPLETED FAILED event.
    const failure = event(8, "TASK_COMPLETED", apply.id);
    failure.status = "FAILED";
    const failed = observeRunEvent(progress, failure);
    expect(
      actionResultLabel("applications:library:cspa", "FAILED", failed),
    ).toBe("Не завершено");
    expect(
      installationDisplay(
        undefined,
        { run: { state: "FAILED" } } as never,
        failed,
      ).percent,
    ).toBe(50);
    expect(
      installationDisplay(
        undefined,
        { run: { state: "CANCELLED" } } as never,
        failed,
      ).percent,
    ).toBe(50);
    expect(
      observeRunEvent(progress, event(8, "ACTION_COMPLETED", apply.id))
        .completedActionIds,
    ).toHaveLength(2);
  });

  it("shows blocked and approved-but-not-started states separately", () => {
    expect(installationDisplay().label).toBe("План не готов");
    expect(
      installationDisplay({ status: "PLAN_APPROVED" } as never).label,
    ).toBe("Установка не начата");
  });

  it("keeps a confirmed-action percentage after an event sequence gap", () => {
    let progress = beginRunProgress("run-1", plan);
    progress = observeRunEvent(progress, event(1, "RUN_STARTED"));
    progress = observeRunEvent(
      progress,
      event(2, "ACTION_STARTED", "apply:one"),
    );
    progress = observeRunEvent(
      progress,
      event(3, "ACTION_COMPLETED", "apply:one"),
    );
    expect(
      installationDisplay(
        undefined,
        { run: { runId: "run-1", state: "RUNNING", sequence: 3 } } as never,
        progress,
      ).percent,
    ).toBe(50);
    expect(actionResultLabel("apply:one", "RUNNING", progress)).toBe("Успешно");
    expect(actionResultLabel("verify:one", "SUCCEEDED", progress)).toBe(
      "Событие не получено",
    );
    progress = observeRunEvent(
      progress,
      event(5, "ACTION_COMPLETED", "verify:one"),
    );
    expect(
      installationDisplay(
        undefined,
        { run: { runId: "run-1", state: "RUNNING", sequence: 5 } } as never,
        progress,
      ).percent,
    ).toBe(99);
    expect(progress.complete).toBe(false);
    expect(progress.lastContiguousSequence).toBe(3);
    expect(actionResultLabel("verify:one", "FAILED", progress)).toBe("Успешно");
    progress = observeRunEvent(progress, event(4, "TASK_COMPLETED"));
    expect(progress.complete).toBe(true);
    expect(progress.lastContiguousSequence).toBe(5);
  });

  it("counts unique action completions delivered out of sequence", () => {
    let progress = beginRunProgress("run-1", plan);
    progress = observeRunEvent(progress, event(1, "RUN_STARTED"));
    progress = observeRunEvent(
      progress,
      event(2, "ACTION_STARTED", "apply:one"),
    );
    progress = observeRunEvent(
      progress,
      event(4, "ACTION_COMPLETED", "verify:one"),
    );
    expect(progress.completedActionIds).toEqual(["verify:one"]);
    expect(progress.lastContiguousSequence).toBe(2);
    expect(progress.complete).toBe(false);

    progress = observeRunEvent(
      progress,
      event(3, "ACTION_COMPLETED", "apply:one"),
    );
    progress = observeRunEvent(
      progress,
      event(4, "ACTION_COMPLETED", "verify:one"),
    );
    expect(progress.completedActionIds).toEqual(["apply:one", "verify:one"]);
    expect(progress.lastContiguousSequence).toBe(4);
    expect(progress.complete).toBe(true);
    expect(
      installationDisplay(
        undefined,
        { run: { runId: "run-1", state: "RUNNING", sequence: 4 } } as never,
        progress,
      ).percent,
    ).toBe(99);
  });

  it("reserves 100 percent for the authoritative successful terminal state", () => {
    const progress = beginRunProgress("run-1", plan);
    expect(
      installationDisplay(
        undefined,
        { run: { runId: "run-1", state: "FAILED", sequence: 1 } } as never,
        progress,
      ).percent,
    ).toBe(0);
    expect(
      installationDisplay(
        undefined,
        { run: { runId: "run-1", state: "SUCCEEDED", sequence: 1 } } as never,
        progress,
      ).percent,
    ).toBe(100);
  });
});

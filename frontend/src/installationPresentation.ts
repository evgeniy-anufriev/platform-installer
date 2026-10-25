import type {
  InstallationEventView,
  InstallationPlanView,
  InstallationRunOperation,
  InstallationState,
} from "./backend";

export type RunProgress = {
  runId: string;
  // Highest sequence observed, which can advance ahead of delivery order.
  lastSequence: number;
  // Highest sequence for which every preceding event has been observed.
  lastContiguousSequence: number;
  pendingSequences: number[];
  complete: boolean;
  actionIds: string[];
  stepParents: Record<string, string>;
  completedActionIds: string[];
  actionOutcomes: Record<string, string>;
  actionOutcomeSequences: Record<string, number>;
  activeActionId?: string;
};

export function beginRunProgress(
  runId: string,
  plan?: InstallationPlanView,
): RunProgress {
  return {
    runId,
    lastSequence: 0,
    lastContiguousSequence: 0,
    pendingSequences: [],
    complete: true,
    actionIds: [
      ...new Set(
        plan?.phases.flatMap((phase) =>
          phase.actions.flatMap((action) =>
            action.progressSteps?.length
              ? action.progressSteps.map((step) => step.id)
              : [action.id],
          ),
        ) || [],
      ),
    ],
    stepParents: Object.fromEntries(
      plan?.phases.flatMap((phase) =>
        phase.actions.flatMap(
          (action) =>
            action.progressSteps?.map((step) => [step.id, action.id]) || [],
        ),
      ) || [],
    ),
    completedActionIds: [],
    actionOutcomes: {},
    actionOutcomeSequences: {},
  };
}

export function observeRunEvent(
  current: RunProgress,
  event: InstallationEventView,
): RunProgress {
  if (event.runId !== current.runId || event.sequence < 1) return current;
  const pending = new Set(current.pendingSequences);
  let contiguous = current.lastContiguousSequence;
  if (event.sequence > contiguous) pending.add(event.sequence);
  while (pending.delete(contiguous + 1)) contiguous += 1;
  const complete = pending.size === 0;
  const isNewest = event.sequence >= current.lastSequence;
  const knownAction =
    !!event.actionId &&
    (current.actionIds.includes(event.actionId) ||
      Object.values(current.stepParents).includes(event.actionId));
  const outcomeRecorded =
    knownAction &&
    event.eventType === "ACTION_COMPLETED" &&
    [
      "SUCCESS",
      "CHANGED",
      "SKIPPED",
      "FAILED",
      "CANCELLED",
      "INTERRUPTED",
    ].includes(event.status);
  const shouldRecordOutcome =
    outcomeRecorded &&
    event.sequence > (current.actionOutcomeSequences[event.actionId!] || 0);
  const actionOutcomes = shouldRecordOutcome
    ? { ...current.actionOutcomes, [event.actionId!]: event.status }
    : current.actionOutcomes;
  const actionOutcomeSequences = shouldRecordOutcome
    ? { ...current.actionOutcomeSequences, [event.actionId!]: event.sequence }
    : current.actionOutcomeSequences;
  const completedActionIds = current.actionIds.filter((actionId) =>
    ["SUCCESS", "CHANGED", "SKIPPED"].includes(actionOutcomes[actionId]),
  );
  return {
    ...current,
    lastSequence: Math.max(current.lastSequence, event.sequence),
    lastContiguousSequence: contiguous,
    pendingSequences: [...pending],
    complete,
    completedActionIds,
    actionOutcomes,
    actionOutcomeSequences,
    activeActionId: !isNewest
      ? current.activeActionId
      : knownAction && event.eventType === "ACTION_STARTED"
        ? event.actionId
        : event.eventType === "ACTION_COMPLETED" &&
            (event.actionId === current.activeActionId ||
              event.actionId ===
                current.stepParents[current.activeActionId || ""])
          ? undefined
          : current.activeActionId,
  };
}

export function actionResultLabel(
  actionId: string,
  runState: string,
  progress?: RunProgress,
): string {
  const outcome = progress?.actionOutcomes[actionId];
  if (outcome === "SUCCESS" || outcome === "CHANGED") return "Успешно";
  if (outcome === "SKIPPED") return "Пропущено";
  if (outcome === "FAILED") return "Ошибка";
  if (outcome === "CANCELLED" || outcome === "INTERRUPTED") return "Прервано";
  if (terminalStates.has(runState) && progress?.activeActionId === actionId)
    return "Не завершено";
  if (!progress?.complete) return "Сведения неполные";
  return runState === "SUCCEEDED" ? "Событие не получено" : "Не подтверждено";
}

// Keep the executable parent visible; child rows are display-only work units.
export function installationActionRows(plan?: InstallationPlanView) {
  return (
    plan?.phases.flatMap((phase) =>
      phase.actions.flatMap((action) => [
        { ...action, parentId: undefined as string | undefined },
        ...(action.progressSteps?.map((step) => ({
          ...action,
          id: step.id,
          summary: step.summary,
          type: "APPLICATION_PROGRESS",
          progressSteps: undefined,
          parentId: action.id,
        })) || []),
      ]),
    ) || []
  );
}

const terminalStates = new Set([
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
  "INTERRUPTED",
]);
const activeStates = new Set(["STARTING", "RUNNING", "CANCELLING"]);

export function installationDisplay(
  state?: InstallationState,
  run?: InstallationRunOperation,
  progress?: RunProgress,
): {
  label: string;
  detail: string;
  tone: "neutral" | "running" | "failed" | "succeeded";
  percent?: number;
  stage: "plan" | "execution" | "result";
} {
  const runState = run?.run?.state;
  if (runState === "SUCCEEDED") {
    return {
      label: "Установка выполнена",
      detail: "Все действия завершены",
      tone: "succeeded",
      percent: 100,
      stage: "result",
    };
  }
  if (runState && terminalStates.has(runState)) {
    const label =
      runState === "FAILED"
        ? "Ошибка установки"
        : runState === "CANCELLED"
          ? "Установка отменена"
          : "Установка прервана";
    return {
      label,
      detail: "Откройте результат запуска",
      tone: "failed",
      percent: confirmedPercent(progress),
      stage: "result",
    };
  }
  if (runState && activeStates.has(runState)) {
    return {
      label: runState === "CANCELLING" ? "Отмена установки" : "Идёт установка",
      detail: "Откройте ход выполнения",
      tone: "running",
      percent: confirmedPercent(progress),
      stage: "execution",
    };
  }
  if (run?.error) {
    return {
      label: "Запуск не начался",
      detail: "Требуется исправить ошибку",
      tone: "failed",
      stage: "plan",
    };
  }
  if (state?.status === "PLAN_APPROVED" || state?.status === "PLAN_REVIEW") {
    return {
      label: "Установка не начата",
      detail:
        state.status === "PLAN_APPROVED"
          ? "План одобрен"
          : "План ожидает одобрения",
      tone: "neutral",
      stage: "plan",
    };
  }
  return {
    label: "План не готов",
    detail: "Сформируйте свежий план",
    tone: "neutral",
    stage: "plan",
  };
}

function confirmedPercent(progress?: RunProgress): number | undefined {
  if (!progress || progress.actionIds.length === 0) return undefined;
  return Math.min(
    99,
    Math.floor(
      (progress.completedActionIds.length * 100) / progress.actionIds.length,
    ),
  );
}

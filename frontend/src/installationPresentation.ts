import type {
  InstallationEventView,
  InstallationPlanView,
  InstallationRunOperation,
  InstallationState,
} from "./backend";

export type RunProgress = {
  runId: string;
  lastSequence: number;
  complete: boolean;
  actionIds: string[];
  completedActionIds: string[];
  actionOutcomes: Record<string, string>;
  activeActionId?: string;
};

export function beginRunProgress(
  runId: string,
  plan?: InstallationPlanView,
): RunProgress {
  return {
    runId,
    lastSequence: 0,
    complete: true,
    actionIds: [
      ...new Set(
        plan?.phases.flatMap((phase) =>
          phase.actions.map((action) => action.id),
        ) || [],
      ),
    ],
    completedActionIds: [],
    actionOutcomes: {},
  };
}

export function observeRunEvent(
  current: RunProgress,
  event: InstallationEventView,
): RunProgress {
  if (event.runId !== current.runId || event.sequence <= current.lastSequence)
    return current;
  const complete =
    current.complete && event.sequence === current.lastSequence + 1;
  const knownAction =
    !!event.actionId && current.actionIds.includes(event.actionId);
  const completed =
    knownAction &&
    event.eventType === "ACTION_COMPLETED" &&
    ["SUCCESS", "CHANGED", "SKIPPED"].includes(event.status);
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
  return {
    ...current,
    lastSequence: event.sequence,
    complete,
    completedActionIds:
      completed && !current.completedActionIds.includes(event.actionId!)
        ? [...current.completedActionIds, event.actionId!]
        : current.completedActionIds,
    actionOutcomes: outcomeRecorded
      ? { ...current.actionOutcomes, [event.actionId!]: event.status }
      : current.actionOutcomes,
    activeActionId:
      knownAction && event.eventType === "ACTION_STARTED"
        ? event.actionId
        : event.eventType === "ACTION_COMPLETED" &&
            event.actionId === current.activeActionId
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
  if (!progress?.complete) return "Сведения неполные";
  return runState === "SUCCEEDED" ? "Событие не получено" : "Не подтверждено";
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
  if (!progress?.complete || progress.actionIds.length === 0) return undefined;
  return Math.min(
    99,
    Math.floor(
      (progress.completedActionIds.length * 100) / progress.actionIds.length,
    ),
  );
}

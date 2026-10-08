// Presentation only: runtime identity and capability decisions remain in Go.
export function executionNodeStatusLabel(status?: string): string {
  switch (status) {
    case "NOT_CONFIGURED": return "Не настроен";
    case "NOT_PREPARED":
    case "UNPREPARED": return "Не подготовлен";
    case "UNREACHABLE": return "Недоступен";
    case "PREPARATION_REQUIRED": return "Требуется подготовка";
    case "UPDATE_REQUIRED": return "Требуется обновление";
    case "INCOMPATIBLE": return "Несовместим";
    case "BROKEN": return "Ошибка узла";
    case "READY": return "Готов";
    default: return "Состояние неизвестно";
  }
}

export function executionNodeSelectionLabel(source?: string): string {
  switch (source) {
    case "NONE": return "Не выбран";
    case "EXPLICIT": return "Выбран вручную";
    case "AUTO_LOCAL_LINUX": return "Автоматически: этот компьютер";
    case "AUTO_FIRST_ELIGIBLE": return "Автоматически: первый подходящий сервер";
    default: return "Источник выбора неизвестен";
  }
}

export function executionNodePreparationLabel(status?: string): string {
  switch (status) {
    case "CONFIRMATION_REQUIRED": return "Ожидает подтверждения";
    case "BLOCKED": return "Подготовка недоступна";
    case "PREPARED": return "Подготовлен";
    default: return executionNodeStatusLabel(status);
  }
}

type ExecutionNodeStatusInput = {
  status?: string;
  error?: { message?: string };
  findings?: Array<{ safeMessage: string }>;
  steps?: Array<{ mutates?: boolean }>;
};

export type ExecutionNodeCombinedStatus = {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
  detail?: string;
};

export function executionNodeCombinedStatus(
  readiness?: ExecutionNodeStatusInput | null,
  preparation?: ExecutionNodeStatusInput | null,
): ExecutionNodeCombinedStatus {
  if (preparation?.status === "PREPARING") {
    return { label: "Выполняется подготовка", tone: "warning" };
  }
  if (preparation?.status === "PREPARED") {
    return { label: "Проверен: Подготовлен", tone: "success" };
  }
  if (preparation?.error) {
    return {
      label: "Ошибка подготовки",
      tone: "danger",
      detail: preparation.error.message,
    };
  }
  if (preparation?.status === "CONFIRMATION_REQUIRED") {
    if (preparation.steps?.some((step) => step.mutates)) {
      return {
        label: "Проверен: Требуется подготовка",
        tone: "warning",
        detail: "Ожидает подтверждения",
      };
    }
    if (!preparation.steps?.length) {
      return {
        label: "Проверен: Ожидает подтверждения",
        tone: "warning",
      };
    }
    return {
      label: "Проверен: Подготовлен",
      tone: "success",
      detail: "Ожидает подтверждения проверки",
    };
  }
  if (preparation?.status === "BLOCKED") {
    return {
      label: "Подготовка недоступна",
      tone: "danger",
      detail: preparation.findings?.map((finding) => finding.safeMessage).join(" · "),
    };
  }
  if (preparation?.status === "UNREACHABLE") {
    return { label: "Проверен: Недоступен", tone: "danger" };
  }
  if (preparation?.status === "INCOMPATIBLE") {
    return { label: "Проверен: Несовместим", tone: "danger" };
  }
  if (preparation?.status === "BROKEN") {
    return { label: "Проверен: Ошибка узла", tone: "danger" };
  }
  if (preparation?.status === "UPDATE_REQUIRED") {
    return { label: "Проверен: Требуется обновление", tone: "warning" };
  }
  if (
    preparation?.status === "PREPARATION_REQUIRED" ||
    preparation?.status === "UNPREPARED" ||
    preparation?.status === "NOT_PREPARED"
  ) {
    return { label: "Проверен: Требуется подготовка", tone: "warning" };
  }
  if (preparation?.status === "READY") {
    return { label: "Проверен: Подготовлен", tone: "success" };
  }
  if (readiness?.error) {
    return {
      label: "Проверка недоступна",
      tone: "danger",
      detail: readiness.error.message,
    };
  }
  if (!readiness) return { label: "Не проверен", tone: "neutral" };
  switch (readiness.status) {
    case "READY":
      return { label: "Проверен: Подготовлен", tone: "success" };
    case "UPDATE_REQUIRED":
      return { label: "Проверен: Требуется обновление", tone: "warning" };
    case "PREPARATION_REQUIRED":
    case "UNPREPARED":
    case "NOT_PREPARED":
      return { label: "Проверен: Требуется подготовка", tone: "warning" };
    case "UNREACHABLE":
      return { label: "Проверен: Недоступен", tone: "danger" };
    case "INCOMPATIBLE":
      return { label: "Проверен: Несовместим", tone: "danger" };
    case "BROKEN":
      return { label: "Проверен: Ошибка узла", tone: "danger" };
    case "NOT_CONFIGURED":
      return { label: "Не проверен: Узел не настроен", tone: "neutral" };
    default:
      return { label: "Состояние неизвестно", tone: "neutral" };
  }
}

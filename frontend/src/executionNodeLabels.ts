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

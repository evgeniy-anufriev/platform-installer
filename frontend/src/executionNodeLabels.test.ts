import { describe, expect, it } from "vitest";
import { executionNodePreparationLabel, executionNodeSelectionLabel, executionNodeStatusLabel } from "./executionNodeLabels";

describe("русские подписи узла выполнения", () => {
  it("не показывает внутренние коды готовности", () => {
    expect(executionNodeStatusLabel("NOT_PREPARED")).toBe("Не подготовлен");
    expect(executionNodeStatusLabel("READY")).toBe("Готов");
    expect(executionNodeStatusLabel("UNKNOWN_CODE")).toBe("Состояние неизвестно");
  });

  it("не показывает внутренние коды источника выбора", () => {
    expect(executionNodeSelectionLabel("AUTO_FIRST_ELIGIBLE")).toBe("Автоматически: первый подходящий сервер");
    expect(executionNodeSelectionLabel("EXPLICIT")).toBe("Выбран вручную");
    expect(executionNodeSelectionLabel("UNKNOWN_CODE")).toBe("Источник выбора неизвестен");
  });

  it("не показывает внутренние коды подготовки", () => {
    expect(executionNodePreparationLabel("CONFIRMATION_REQUIRED")).toBe("Ожидает подтверждения");
    expect(executionNodePreparationLabel("BLOCKED")).toBe("Подготовка недоступна");
    expect(executionNodePreparationLabel("PREPARED")).toBe("Подготовлен");
    expect(executionNodePreparationLabel("READY")).toBe("Готов");
  });
});

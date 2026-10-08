import { describe, expect, it } from "vitest";
import { executionNodeCombinedStatus, executionNodePreparationLabel, executionNodeSelectionLabel, executionNodeStatusLabel } from "./executionNodeLabels";

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

  it("объединяет проверку и подготовку в один статус", () => {
    expect(executionNodeCombinedStatus().label).toBe("Не проверен");
    expect(executionNodeCombinedStatus({ status: "UPDATE_REQUIRED" }).label).toBe("Проверен: Требуется обновление");
    expect(executionNodeCombinedStatus({ status: "PREPARATION_REQUIRED" }).label).toBe("Проверен: Требуется подготовка");
    expect(executionNodeCombinedStatus({ status: "READY" }).label).toBe("Проверен: Подготовлен");
    expect(executionNodeCombinedStatus(undefined, { status: "CONFIRMATION_REQUIRED", steps: [{ mutates: true }] })).toMatchObject({ label: "Проверен: Требуется подготовка", detail: "Ожидает подтверждения" });
    expect(executionNodeCombinedStatus(undefined, { status: "PREPARED" }).label).toBe("Проверен: Подготовлен");
    expect(executionNodeCombinedStatus(undefined, { status: "BLOCKED", error: { message: "Недоступно" } })).toMatchObject({ label: "Ошибка подготовки", detail: "Недоступно" });
  });
});

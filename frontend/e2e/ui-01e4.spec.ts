import { expect, test } from "@playwright/test";
test("E4 auto and manual selection", async ({ page }) => {
  await page.goto("/?qa=e4");
  await page.getByRole("button", { name: "Открыть папку проекта" }).click();
  await page.getByRole("button", { name: "Серверы", exact: true }).click();
  await expect(
    page.getByText("Автоматически: первый подходящий сервер"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Выбрать узел выполнения" }).click();
  await page
    .getByRole("combobox", { name: "Сервер проекта для узла выполнения" })
    .selectOption("node2");
  await page.getByRole("button", { name: "Выбрать" }).click();
  await expect(page.getByText("Выбран вручную")).toBeVisible();
});

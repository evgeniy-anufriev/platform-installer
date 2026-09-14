import { expect, test } from "@playwright/test";
test("E4 auto and manual selection", async ({ page }) => {
  await page.goto("/?qa=e4");
  await page.getByRole("button", { name: "Открыть папку проекта" }).click();
  await page.getByRole("button", { name: "Серверы", exact: true }).click();
  await expect(page.getByText("AUTO_FIRST_ELIGIBLE")).toBeVisible();
  await page.getByRole("button", { name: "Выбрать Execution Node" }).click();
  await page.getByRole("combobox", { name: "Сервер проекта для Execution Node" }).selectOption("node2");
  await page.getByRole("button", { name: "Выбрать" }).click();
  await expect(page.getByText("EXPLICIT")).toBeVisible();
});

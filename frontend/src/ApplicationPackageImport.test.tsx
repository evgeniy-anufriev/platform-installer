import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationPackageImport } from "./ApplicationPackageImport";

describe("ApplicationPackageImport", () => {
  it("keeps the single library import at page level", async () => {
    const review = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    render(
      <ApplicationPackageImport
        disabled={false}
        choose={async () => "C:/packages/szi/1.0.0"}
        review={review}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Импорт пакета…" }));
    await user.selectOptions(screen.getByLabelText("Тип"), "library");
    await user.type(screen.getByLabelText("Имя"), "szi");
    await user.click(
      screen.getByRole("button", { name: "Выбрать папку пакета" }),
    );
    await user.click(screen.getByRole("button", { name: "Проверить импорт" }));
    expect(review).toHaveBeenCalledWith(
      "C:/packages/szi/1.0.0",
      "library",
      "szi",
      "",
      "",
    );
  });
  it("imports the exact application from its instance screen", async () => {
    const review = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    render(
      <ApplicationPackageImport
        disabled={false}
        applicationRef="gateway@1.0.0"
        choose={async () => "C:/packages/gateway/1.0.0"}
        review={review}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Импорт пакета приложения…" }),
    );
    expect(screen.queryByLabelText("Тип")).toBeNull();
    expect(screen.queryByLabelText("Имя")).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Выбрать папку пакета" }),
    );
    await user.click(screen.getByRole("button", { name: "Проверить импорт" }));
    expect(review).toHaveBeenCalledWith(
      "C:/packages/gateway/1.0.0",
      "application",
      "gateway",
      "1.0.0",
      "",
    );
  });
  it("reviews a selected package without manual version or SHA", async () => {
    const review = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    render(
      <ApplicationPackageImport
        disabled={false}
        choose={async () => "C:/packages/application-packages"}
        review={review}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Импорт пакета…" }));
    expect(screen.queryByLabelText("Версия")).toBeNull();
    expect(screen.queryByLabelText("Ожидаемый digest пакета")).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Выбрать папку пакета" }),
    );
    expect(screen.queryByLabelText("Имя")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Проверить импорт" }));
    await waitFor(() =>
      expect(review).toHaveBeenCalledWith(
        "C:/packages/application-packages",
        "application",
        "",
        "",
        "",
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "Импорт пакета" }),
      ).toBeNull(),
    );
  });
});

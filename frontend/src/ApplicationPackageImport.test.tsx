import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationPackageImport } from "./ApplicationPackageImport";

describe("ApplicationPackageImport", () => {
  it("reviews a selected package without manual version or SHA", async () => {
    const review = vi.fn().mockResolvedValue(true);
    const user = userEvent.setup();
    render(
      <ApplicationPackageImport
        disabled={false}
        choose={async () => "C:/packages/gateway/1.0.0"}
        review={review}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Импорт пакета…" }));
    expect(screen.queryByLabelText("Версия")).toBeNull();
    expect(screen.queryByLabelText("Ожидаемый digest пакета")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Выбрать папку пакета" }));
    await user.type(screen.getByLabelText("Имя"), "gateway");
    await user.click(screen.getByRole("button", { name: "Проверить импорт" }));
    await waitFor(() =>
      expect(review).toHaveBeenCalledWith(
        "C:/packages/gateway/1.0.0",
        "application",
        "gateway",
        "",
        "",
      ),
    );
    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "Импорт пакета" })).toBeNull(),
    );
  });
});

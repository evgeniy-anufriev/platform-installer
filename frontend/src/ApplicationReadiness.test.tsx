import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApplicationReadiness } from "./ApplicationReadiness";

function setup(
  value: Record<string, unknown> = {},
  defaults: Record<string, unknown> = {
    mode: "container",
    retries: 10,
    delay: 2,
  },
  accept = true,
) {
  const save = vi.fn(async () => accept),
    reset = vi.fn(async () => accept),
    dirty = vi.fn();
  render(
    <ApplicationReadiness
      value={value}
      defaults={defaults}
      disabled={false}
      onSave={save}
      onReset={reset}
      onDirtyChange={dirty}
    />,
  );
  return { user: userEvent.setup(), save, reset, dirty };
}
describe("readiness form", () => {
  it("shows package values without creating overrides", () => {
    const { save } = setup();
    expect(
      (screen.getByLabelText("Режим проверки") as HTMLSelectElement).value,
    ).toBe("container");
    expect(
      (screen.getByLabelText("Число попыток") as HTMLInputElement).value,
    ).toBe("10");
    expect(
      screen.getByLabelText("Число попыток").hasAttribute("disabled"),
    ).toBe(true);
    expect(save).not.toHaveBeenCalled();
    expect(screen.queryByText(/Добавить параметр/)).toBeNull();
  });
  it("stages only edited numbers plus the required mode", async () => {
    const { user, save, dirty } = setup();
    await user.click(screen.getByText("Изменить readiness"));
    await user.clear(screen.getByLabelText("Число попыток"));
    await user.type(screen.getByLabelText("Число попыток"), "15");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith({ mode: "container", retries: 15 });
    expect(dirty).toHaveBeenLastCalledWith(false);
  });
  it("enforces contract retry and delay bounds", async () => {
    const { user, save } = setup();
    await user.click(screen.getByText("Изменить readiness"));
    await user.clear(screen.getByLabelText("Число попыток"));
    await user.type(screen.getByLabelText("Число попыток"), "61");
    expect(screen.getByText("В черновик").hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
  });
  it("does not invent effective Core defaults when the package omits readiness", () => {
    setup({}, {});
    expect(
      (screen.getByLabelText("Число попыток") as HTMLInputElement).value,
    ).toBe("");
    expect(
      (screen.getByLabelText("Режим проверки") as HTMLSelectElement).value,
    ).toBe("");
  });
  it("resets the authored section and preserves dirty state if staging is rejected", async () => {
    const { user, save, reset, dirty } = setup(
      { mode: "healthcheck", retries: 5 },
      undefined,
      false,
    );
    await user.click(screen.getByText("Изменить readiness"));
    await user.clear(screen.getByLabelText("Интервал, сек."));
    await user.type(screen.getByLabelText("Интервал, сек."), "3");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith({
      mode: "healthcheck",
      retries: 5,
      delay: 3,
    });
    expect(dirty).toHaveBeenLastCalledWith(true);
    await user.click(screen.getByText("Сбросить readiness к пакету"));
    expect(reset).toHaveBeenCalled();
  });
});

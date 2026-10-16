import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import {
  ApplicationValueFields,
  inferParameterValue,
} from "./ApplicationValueFields";

describe("parameter input", () => {
  it.each([
    ["true", true],
    ["false", false],
    ["42", 42],
    ["-2.5", -2.5],
    ["001", "001"],
    ["1.2.3", "1.2.3"],
    ["192.168.1.1", "192.168.1.1"],
    ["", ""],
    ["9007199254740993", "9007199254740993"],
    [" 12 ", " 12 "],
  ])("infers %s without losing string identifiers", (input, expected) => {
    expect(inferParameterValue(String(input))).toBe(expected);
  });
  it("adds by name first, then stages the inferred numeric value", async () => {
    const save = vi
        .fn<(value: Record<string, unknown>) => Promise<boolean>>()
        .mockResolvedValue(true),
      user = userEvent.setup();
    function Editor() {
      const [value, setValue] = useState<Record<string, unknown>>({});
      return (
        <ApplicationValueFields
          label="Параметры"
          value={value}
          defaults={{}}
          disabled={false}
          onDirtyChange={vi.fn()}
          onSave={async (next) => {
            await save(next);
            setValue(next);
            return true;
          }}
        />
      );
    }
    render(<Editor />);
    expect(screen.queryByText("Добавить значение")).toBeNull();
    await user.click(screen.getByText("Добавить параметр · Параметры"));
    await user.type(screen.getByLabelText("Имя параметра"), "timeout");
    expect(screen.queryByLabelText("Значение")).toBeNull();
    await user.click(screen.getByText("Добавить", { exact: true }));
    await user.type(screen.getByLabelText("timeout", { exact: true }), "30");
    expect(screen.getByText("Тип: Число · автоматически")).toBeTruthy();
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenLastCalledWith({ timeout: 30 });
  });
  it("retains package strings and offers a manual type override", async () => {
    const save = vi.fn(async () => true),
      user = userEvent.setup();
    render(
      <ApplicationValueFields
        label="Параметры"
        value={{}}
        defaults={{ code: "001" }}
        disabled={false}
        onDirtyChange={vi.fn()}
        onSave={save}
      />,
    );
    await user.clear(screen.getByLabelText("code", { exact: true }));
    await user.type(screen.getByLabelText("code", { exact: true }), "42");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenLastCalledWith({ code: "42" });
    await user.click(screen.getByText("Дополнительно"));
    await user.selectOptions(screen.getByLabelText("Тип · code"), "number");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenLastCalledWith({ code: 42 });
  });
  it("keeps numeric validation and reset semantics", async () => {
    const save = vi.fn(async () => true),
      user = userEvent.setup();
    render(
      <ApplicationValueFields
        label="Параметры"
        value={{ timeout: 3 }}
        defaults={{ timeout: 2 }}
        disabled={false}
        onDirtyChange={vi.fn()}
        onSave={save}
      />,
    );
    await user.clear(screen.getByLabelText("timeout", { exact: true }));
    await user.type(screen.getByLabelText("timeout", { exact: true }), "wrong");
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("В черновик").hasAttribute("disabled")).toBe(true);
    await user.click(screen.getByText("Сбросить к default"));
    expect(save).toHaveBeenCalledWith({});
  });
  it("exposes object fields without a JSON text editor", async () => {
    const user = userEvent.setup(),
      save = vi.fn(async () => true);
    render(
      <ApplicationValueFields
        label="Параметры"
        value={{ nested: "" }}
        defaults={{}}
        disabled={false}
        onDirtyChange={vi.fn()}
        onSave={save}
      />,
    );
    await user.click(screen.getByText("Дополнительно"));
    await user.click(screen.getByText("Создать объект"));
    expect(save).toHaveBeenCalledWith({ nested: {} });
    expect(
      within(screen.getByRole("combobox")).getByText("Автоматически"),
    ).toBeTruthy();
  });
});

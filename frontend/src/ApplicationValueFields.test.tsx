import { useState } from "react";
import { render, screen, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import {
  ApplicationValueFields,
  inferParameterValue,
} from "./ApplicationValueFields";

describe("parameter input", () => {
  it("keeps nested endpoint fields compact and saves only the nested override", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <ApplicationValueFields
        compact
        label="Endpoint"
        value={{}}
        defaults={{ probe: { path: "/health", expected_status: 200 } }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    const input = screen.getByLabelText("expected_status");
    expect(input.closest(".application-value-row")).toBeTruthy();
    expect(screen.queryByText("Дополнительно")).toBeNull();
    fireEvent.change(input, { target: { value: "201" } });
    await userEvent.click(
      within(input.closest(".application-value-row")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect(save).toHaveBeenCalledWith({ probe: { expected_status: 201 } });
  });
  it("shows Core values but focuses and saves the authored source, never the projected value", async () => {
    const save = vi.fn().mockResolvedValue(true);
    const props = {
      compact: true,
      label: "ENV",
      value: { NAME: "{{ application_instance_id }}" },
      defaults: { NAME: "default-name" },
      disabled: false,
      onSave: save,
      onDirtyChange: vi.fn(),
    };
    const { rerender } = render(
      <ApplicationValueFields
        {...props}
        resolvedValues={{ NAME: "core-name", FLAG: false, COUNT: 0 }}
      />,
    );
    const input = screen.getByLabelText("NAME") as HTMLInputElement;
    expect(input.value).toBe("core-name");
    expect((screen.getByLabelText("FLAG") as HTMLInputElement).value).toBe(
      "false",
    );
    expect((screen.getByLabelText("COUNT") as HTMLInputElement).value).toBe(
      "0",
    );
    expect(input.title).toContain("Default: default-name");
    await userEvent.click(input);
    expect(input.value).toBe("{{ application_instance_id }}");
    await userEvent.tab();
    expect(input.value).toBe("core-name");
    expect(save).not.toHaveBeenCalled();
    await userEvent.click(input);
    fireEvent.change(input, { target: { value: "authored-name" } });
    await userEvent.click(
      within(input.closest(".application-value-row")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect(save).toHaveBeenCalledWith({ NAME: "authored-name" });
    rerender(<ApplicationValueFields {...props} resolvedValues={{}} />);
    expect(screen.queryByLabelText("FLAG")).toBeNull();
  });
  it("drops stale Core display and restores the source without saving", () => {
    const props = {
      compact: true,
      label: "ENV",
      value: {},
      defaults: { URL: "{{ url }}" },
      disabled: false,
      onSave: vi.fn(),
      onDirtyChange: vi.fn(),
    };
    const { rerender } = render(
      <ApplicationValueFields
        {...props}
        resolvedValues={{ URL: "https://resolved" }}
      />,
    );
    expect((screen.getByLabelText("URL") as HTMLInputElement).value).toBe(
      "https://resolved",
    );
    rerender(<ApplicationValueFields {...props} resolvedValues={{}} />);
    expect((screen.getByLabelText("URL") as HTMLInputElement).value).toBe(
      "{{ url }}",
    );
    expect(props.onSave).not.toHaveBeenCalled();
  });
  it.each([
    ["42", 42],
    ["false", false],
    ["001", "001"],
    ["{{ application_instance_id }}", "{{ application_instance_id }}"],
  ])(
    "uses compact automatic typing for %s without advanced controls",
    async (text, expected) => {
      const save = vi.fn().mockResolvedValue(true);
      const dirty = vi.fn();
      render(
        <ApplicationValueFields
          compact
          label="ENV"
          value={{ KEY: "old" }}
          defaults={{ KEY: "default" }}
          disabled={false}
          onSave={save}
          onDirtyChange={dirty}
        />,
      );
      expect(screen.queryByText("Дополнительно")).toBeNull();
      expect(screen.queryByRole("combobox")).toBeNull();
      const input = screen.getByLabelText("KEY");
      fireEvent.change(input, { target: { value: String(text) } });
      await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
      expect(save).toHaveBeenLastCalledWith({ KEY: expected });
      expect(dirty).toHaveBeenLastCalledWith(false);
      await userEvent.click(
        screen.getByRole("button", { name: "Сбросить к default" }),
      );
      expect(save).toHaveBeenLastCalledWith({});
    },
  );
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

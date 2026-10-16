import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationSecretBindings } from "./ApplicationSecretBindings";

const defaults = {
  type: "vault-agent",
  mode: "process-supervisor",
  secret_bindings: {
    PG_PASSWORD: { source: { account: "postgres", field: "password" } },
    JAVA_PASSWORD: { source: { library_secret: "java" } },
  },
};
const accounts = {
  postgres: {
    credentials: {
      username: { source: { kind: "literal", value: "synthetic-user" } },
      password: { source: { kind: "runtime_secret_ref", ref: "pg-pass" } },
    },
  },
};
const initial = {
  type: "vault-agent",
  mode: "process-supervisor",
  auth: { method: "approle" },
  secrets: { mount: "applications" },
  secret_bindings: {
    CUSTOM_USER: { source: { account: "postgres", field: "username" } },
    CUSTOM_SHARED: { source: { library_secret: "other" } },
  },
};
function Harness({
  save,
  dirty = vi.fn(),
  accept = true,
}: {
  save: (value: Record<string, unknown>) => void;
  dirty?: (dirty: boolean) => void;
  accept?: boolean;
}) {
  const [value, setValue] = useState<Record<string, unknown>>(initial);
  return (
    <ApplicationSecretBindings
      value={value}
      defaults={defaults}
      accounts={[accounts]}
      disabled={false}
      onDirtyChange={dirty}
      onSave={async (next) => {
        save(next);
        if (accept) setValue(next);
        return accept;
      }}
    />
  );
}
describe("application secret bindings", () => {
  it("overrides and resets a package binding without changing shared bindings or Agent settings", async () => {
    const save = vi.fn();
    render(<Harness save={save} />);
    const row = () =>
      within(screen.getByRole("group", { name: "PG_PASSWORD" }));
    expect(
      (row().getByLabelText("Источник PG_PASSWORD") as HTMLSelectElement)
        .disabled,
    ).toBe(true);
    await userEvent.click(
      row().getByRole("button", { name: "Переопределить PG_PASSWORD" }),
    );
    await userEvent.selectOptions(
      row().getByLabelText("Источник PG_PASSWORD"),
      "postgres:username",
    );
    await userEvent.click(row().getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenLastCalledWith({
      ...initial,
      secret_bindings: {
        ...initial.secret_bindings,
        PG_PASSWORD: { source: { account: "postgres", field: "username" } },
      },
    });
    await userEvent.click(
      row().getByRole("button", { name: "Сбросить PG_PASSWORD к default" }),
    );
    expect(save).toHaveBeenLastCalledWith(initial);
    expect(
      (row().getByLabelText("Источник PG_PASSWORD") as HTMLSelectElement).value,
    ).toBe("postgres:password");
    expect(
      (row().getByLabelText("Источник PG_PASSWORD") as HTMLSelectElement)
        .disabled,
    ).toBe(true);
  });
  it("adds and removes an alias, rejects duplicate/invalid names and persists no credential payload", async () => {
    const save = vi.fn();
    render(<Harness save={save} />);
    const add = within(
      screen.getByRole("group", { name: "Добавить переменную" }),
    );
    const name = add.getByLabelText("Имя переменной приложения");
    await userEvent.type(name, "PG_PASSWORD");
    await userEvent.selectOptions(
      add.getByLabelText("Поле credentials"),
      "postgres:password",
    );
    expect(
      (add.getByRole("button", { name: "В черновик" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await userEvent.clear(name);
    await userEvent.type(name, "invalid-name");
    expect(
      (add.getByRole("button", { name: "В черновик" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    await userEvent.clear(name);
    await userEvent.type(name, "DB_PASSWORD");
    await userEvent.click(add.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenLastCalledWith({
      ...initial,
      secret_bindings: {
        ...initial.secret_bindings,
        DB_PASSWORD: { source: { account: "postgres", field: "password" } },
      },
    });
    expect(JSON.stringify(save.mock.calls)).not.toContain("synthetic-user");
    expect(JSON.stringify(save.mock.calls)).not.toContain("pg-pass");
    await userEvent.click(
      screen.getByRole("button", { name: "Сбросить DB_PASSWORD к default" }),
    );
    expect(save).toHaveBeenLastCalledWith(initial);
    expect(screen.queryByRole("group", { name: "DB_PASSWORD" })).toBeNull();
  });
  it("keeps dirty sibling input and a rejected save", async () => {
    const save = vi.fn(),
      dirty = vi.fn();
    render(<Harness save={save} dirty={dirty} accept={false} />);
    await userEvent.type(
      screen.getByLabelText("Имя переменной приложения"),
      "UNSTAGED",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить PG_PASSWORD" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Источник PG_PASSWORD"),
      "postgres:username",
    );
    await userEvent.click(
      within(screen.getByRole("group", { name: "PG_PASSWORD" })).getByRole(
        "button",
        { name: "В черновик" },
      ),
    );
    expect(
      (screen.getByLabelText("Имя переменной приложения") as HTMLInputElement)
        .value,
    ).toBe("UNSTAGED");
    expect(
      (screen.getByLabelText("Источник PG_PASSWORD") as HTMLSelectElement)
        .value,
    ).toBe("postgres:username");
    expect(dirty).toHaveBeenLastCalledWith(true);
  });
  it("keeps an unstaged sibling dirty after an accepted row save", async () => {
    const save = vi.fn(),
      dirty = vi.fn();
    render(<Harness save={save} dirty={dirty} />);
    await userEvent.type(
      screen.getByLabelText("Имя переменной приложения"),
      "LOCAL_ONLY",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить PG_PASSWORD" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Источник PG_PASSWORD"),
      "postgres:username",
    );
    await userEvent.click(
      within(screen.getByRole("group", { name: "PG_PASSWORD" })).getByRole(
        "button",
        { name: "В черновик" },
      ),
    );
    expect(dirty).toHaveBeenLastCalledWith(true);
    expect(
      (screen.getByLabelText("Имя переменной приложения") as HTMLInputElement)
        .value,
    ).toBe("LOCAL_ONLY");
  });
  it("includes required provisioner keys from the package and disables edits while busy", async () => {
    const save = vi.fn();
    const view = render(
      <ApplicationSecretBindings
        value={{}}
        defaults={defaults}
        accounts={[accounts]}
        disabled={false}
        onSave={save.mockResolvedValue(true)}
        onDirtyChange={vi.fn()}
      />,
    );
    const add = within(
      screen.getByRole("group", { name: "Добавить переменную" }),
    );
    await userEvent.type(
      add.getByLabelText("Имя переменной приложения"),
      "DB_USER",
    );
    await userEvent.selectOptions(
      add.getByLabelText("Поле credentials"),
      "postgres:username",
    );
    await userEvent.click(add.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      type: "vault-agent",
      mode: "process-supervisor",
      secret_bindings: {
        DB_USER: { source: { account: "postgres", field: "username" } },
      },
    });
    view.rerender(
      <ApplicationSecretBindings
        value={{}}
        defaults={defaults}
        accounts={[accounts]}
        disabled
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      (screen.getByLabelText("Имя переменной приложения") as HTMLInputElement)
        .disabled,
    ).toBe(true);
  });
});

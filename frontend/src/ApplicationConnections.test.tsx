import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationBindings } from "./ApplicationBindings";
import {
  ApplicationCredentials,
  CredentialSourceEditor,
} from "./ApplicationCredentials";

describe("application connection settings", () => {
  it("resets only account management mode and preserves credentials and rights", async () => {
    const save = vi.fn().mockResolvedValue(true);
    const credentials = {
      password: { source: { kind: "runtime_secret_ref", ref: "pg-password" } },
    };
    const databaseAccess = [{ databaseRef: "db", privileges: ["SELECT"] }];
    render(
      <ApplicationCredentials
        defaults={{ accounts: { postgres: { mode: "managed", credentials } } }}
        authored={{
          accounts: {
            postgres: { mode: "existing", credentials, databaseAccess },
          },
        }}
        connections={{ postgres: { library_binding: "db" } }}
        bindings={{}}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText("Настройки"));
    await userEvent.selectOptions(
      screen.getByLabelText("Управление учётной записью"),
      "",
    );
    expect(save).toHaveBeenCalledWith({
      postgres: { credentials, databaseAccess },
    });
  });
  it("requires an explicit account mode before a credential override without copying package fields", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <ApplicationCredentials
        defaults={{
          accounts: {
            postgres: {
              mode: "managed",
              databaseRef: "db",
              credentials: { password: { source: { kind: "generated" } } },
            },
          },
        }}
        authored={{}}
        connections={{ postgres: { library_binding: "database" } }}
        bindings={{}}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      (screen.getByLabelText("Источник") as HTMLSelectElement).disabled,
    ).toBe(true);
    await userEvent.selectOptions(
      screen.getByLabelText("Управление учётной записью"),
      "managed",
    );
    expect(save).toHaveBeenCalledWith({
      postgres: { mode: "managed", credentials: {} },
    });
  });
  it("uses project candidates and preserves adjacent bindings", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <ApplicationBindings
        value={{ keep: { deploymentRef: "existing" } }}
        hints={{ database: "deployment" }}
        deployments={["db-one", "db-two"]}
        profiles={["tls-one"]}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Подключение database"),
      "db-two",
    );
    const group = screen.getByLabelText("Подключение database").closest("tr")!;
    await userEvent.click(
      Array.from(group.querySelectorAll("button")).find(
        (b) => b.textContent === "В черновик",
      )!,
    );
    expect(save).toHaveBeenCalledWith({
      keep: { deploymentRef: "existing" },
      database: { deploymentRef: "db-two" },
    });
  });
  it("serializes a typed Vault descriptor without literal password fields", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <CredentialSourceEditor
        label="Password source"
        source={{}}
        packageSource={{ kind: "generated" }}
        allowLiteral={false}
        disabled={false}
        onSave={save}
        onReset={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Источник"),
      "vault_ref",
    );
    for (const [label, value] of [
      ["Binding", "secrets"],
      ["Vault mount", "kv"],
      ["Vault document", "application/c"],
      ["Поле секрета", "password"],
    ])
      await userEvent.type(screen.getByLabelText(label), value);
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      kind: "vault_ref",
      binding: "secrets",
      mount: "kv",
      document: "application/c",
      field: "password",
    });
    expect(
      screen.queryByRole("option", { name: "Имя пользователя" }),
    ).toBeNull();
  });
});

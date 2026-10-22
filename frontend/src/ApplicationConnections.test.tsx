import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationBindings } from "./ApplicationBindings";
import {
  ApplicationCredentials,
  CredentialSourceEditor,
} from "./ApplicationCredentials";

describe("application connection settings", () => {
  it("saves generated as a source without accepting a plaintext value", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <CredentialSourceEditor
        label="Пароль"
        source={{}}
        packageSource={{ kind: "runtime_secret_ref", ref: "app-password" }}
        allowLiteral={false}
        disabled={false}
        onSave={save}
        onReset={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Источник"),
      "generated",
    );
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText(/Создаётся при применении/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({ kind: "generated" });
  });
  it("displays the Core username but edits and saves only the authored source", async () => {
    const save = vi.fn().mockResolvedValue(true);
    const template = "{{ application_instance_id | replace('-', '_') }}";
    render(
      <ApplicationCredentials
        defaults={{
          accounts: {
            postgres: {
              mode: "existing",
              credentials: {
                username: { source: { kind: "literal", value: template } },
              },
            },
          },
        }}
        authored={{ accounts: { postgres: { mode: "existing" } } }}
        resolvedAccounts={{
          postgres: {
            credentials: {
              username: { source: { kind: "literal", value: "gateway_cspa" } },
            },
          },
        }}
        connections={{}}
        bindings={{}}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    const input = screen.getByRole("textbox", { name: "Имя пользователя" });
    expect((input as HTMLInputElement).value).toBe("gateway_cspa");
    await userEvent.click(input);
    expect((input as HTMLInputElement).value).toBe(template);
    await userEvent.tab();
    expect((input as HTMLInputElement).value).toBe("gateway_cspa");
    expect(save).not.toHaveBeenCalled();
    await userEvent.click(input);
    await userEvent.clear(input);
    await userEvent.type(input, "custom-user");
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      postgres: {
        mode: "existing",
        credentials: {
          username: { source: { kind: "literal", value: "custom-user" } },
        },
      },
    });
  });
  it("drops a resolved username when current Core evidence is removed", () => {
    const props = {
      label: "Имя пользователя",
      source: {},
      packageSource: {
        kind: "literal",
        value: "{{ application_instance_id }}",
      },
      allowLiteral: true,
      disabled: false,
      onSave: vi.fn(),
      onReset: vi.fn(),
      onDirtyChange: vi.fn(),
    };
    const view = render(
      <CredentialSourceEditor {...props} resolvedLiteralValue="gateway-cspa" />,
    );
    expect((screen.getByRole("textbox") as HTMLInputElement).value).toBe(
      "gateway-cspa",
    );
    view.rerender(<CredentialSourceEditor {...props} />);
    expect((screen.getByRole("textbox") as HTMLInputElement).value).toBe(
      "{{ application_instance_id }}",
    );
  });
  it("creates a runtime reference automatically when switching the resource source", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <CredentialSourceEditor
        label="Пароль"
        source={{}}
        packageSource={{ kind: "generated" }}
        runtimeInput={<span>Ввод в строке ресурса</span>}
        allowLiteral={false}
        disabled={false}
        onSave={save}
        onReset={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Источник"),
      "runtime_secret_ref",
    );
    expect(screen.queryByLabelText(/имя ссылки/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      kind: "runtime_secret_ref",
      ref: expect.stringMatching(/^application-[a-f0-9-]{36}$/),
    });
    expect(Object.keys(save.mock.calls[0][0]).sort()).toEqual(["kind", "ref"]);
  });
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

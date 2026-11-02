import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import {
  ApplicationBindings,
  connectionCandidates,
} from "./ApplicationBindings";

function setup(save = vi.fn(async () => true)) {
  const dirty = vi.fn();
  render(
    <ApplicationBindings
      value={{ pg: { deploymentRef: "pg1" }, tls: { profileRef: "server" } }}
      hints={{}}
      deployments={["pg1", "pg2"]}
      profiles={["server", "client"]}
      disabled={false}
      onSave={save}
      onDirtyChange={dirty}
    />,
  );
  return { user: userEvent.setup(), save, dirty };
}
describe("library connections table", () => {
  it("filters by declared role, not the arbitrary binding name", () => {
    const result = connectionCandidates(
      {
        customDb: ["postgres"],
        cache: ["redis", "sentinel"],
        secrets: ["vault"],
        database: ["custom-role"],
        conflicting: ["postgres", "redis"],
      },
      {
        pg1: "postgresql",
        pg2: "postgresql",
        redis: "redis",
        vault: "vault",
        docker: "docker",
      },
      [],
    );
    expect(result.customDb.deploymentRefs).toEqual(["pg1", "pg2"]);
    expect(result.cache.deploymentRefs).toEqual(["redis"]);
    expect(result.secrets.deploymentRefs).toEqual(["vault"]);
    expect(result.conflicting.deploymentRefs).toEqual([]);
    expect(result.database).toBeUndefined();
  });
  it("filters choices and preserves an incompatible saved reference", async () => {
    const save = vi.fn(async () => true);
    render(
      <ApplicationBindings
        value={{ database: { deploymentRef: "old-redis" } }}
        hints={{
          database: "deployment",
          cache: "deployment",
          secrets: "deployment",
          sso: "deployment",
        }}
        deployments={["pg-a", "pg-b", "old-redis", "vault-a", "docker-a"]}
        profiles={[]}
        providedConnections={["szi/sso", "other/api"]}
        candidates={{
          database: {
            deploymentRefs: ["pg-a", "pg-b"],
            providedConnectionRefs: [],
          },
          cache: { deploymentRefs: ["old-redis"], providedConnectionRefs: [] },
          secrets: { deploymentRefs: ["vault-a"], providedConnectionRefs: [] },
          sso: {
            kind: "providedConnectionRef",
            deploymentRefs: [],
            providedConnectionRefs: ["szi/sso"],
          },
        }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    const options = (name: string) =>
      within(screen.getByLabelText("Подключение " + name))
        .getAllByRole("option")
        .map((option) => (option as HTMLOptionElement).value);
    expect(options("database")).toEqual(["", "old-redis", "pg-a", "pg-b"]);
    expect(
      screen.getByRole("option", { name: /old-redis · недоступно/ }),
    ).toBeTruthy();
    expect(options("cache")).toEqual(["", "old-redis"]);
    expect(options("secrets")).toEqual(["", "vault-a"]);
    expect(screen.getByLabelText("Тип подключения sso")).toHaveProperty(
      "disabled",
      true,
    );
    expect(options("sso")).toEqual(["", "szi/sso"]);
    expect(save).not.toHaveBeenCalled();
  });
  it("renders the full list in one scroll region without pagination", () => {
    render(
      <ApplicationBindings
        value={Object.fromEntries(
          ["a", "b", "c", "d", "e", "f"].map((key) => [
            key,
            { deploymentRef: "pg1" },
          ]),
        )}
        hints={{}}
        deployments={["pg1"]}
        profiles={[]}
        disabled={false}
        onSave={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("region", { name: "Список подключений" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Подключение f")).toBeTruthy();
    expect(screen.queryByText("Далее")).toBeNull();
  });
  it("uses the secrets binding without a separate provider selection button", () => {
    render(
      <ApplicationBindings
        value={{
          secrets: { deploymentRef: "qa-vault" },
          other: { deploymentRef: "qa-other-vault" },
        }}
        hints={{}}
        deployments={["qa-vault", "qa-other-vault"]}
        profiles={[]}
        disabled={false}
        onSave={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      within(screen.getByRole("row", { name: /^secrets / })).getByText(
        "Хранилище секретов",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Для секретов" })).toBeNull();
  });
  it("renders named rows with current deployment and profile", () => {
    setup();
    expect(screen.getByRole("table")).toBeTruthy();
    expect(
      (screen.getByLabelText("Подключение pg") as HTMLSelectElement).value,
    ).toBe("pg1");
    expect(
      (screen.getByLabelText("Подключение tls") as HTMLSelectElement).value,
    ).toBe("server");
  });
  it("changes one binding and preserves its sibling", async () => {
    const { user, save, dirty } = setup();
    await user.selectOptions(screen.getByLabelText("Подключение pg"), "pg2");
    await user.click(
      within(screen.getByRole("row", { name: /pg/ })).getByText("В черновик"),
    );
    expect(save).toHaveBeenCalledWith({
      pg: { deploymentRef: "pg2" },
      tls: { profileRef: "server" },
    });
    expect(dirty).toHaveBeenLastCalledWith(false);
  });
  it("locks all reference kinds while retaining saved bindings and target selection", async () => {
    const { user, save } = setup();
    expect(screen.getByLabelText("Тип подключения pg")).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByLabelText("Тип подключения pg")).toHaveProperty(
      "value",
      "deploymentRef",
    );
    expect(screen.getByLabelText("Тип подключения tls")).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByLabelText("Тип подключения tls")).toHaveProperty(
      "value",
      "profileRef",
    );
    expect(screen.getByLabelText("Подключение pg")).toHaveProperty(
      "value",
      "pg1",
    );
    expect(save).not.toHaveBeenCalled();
    await user.selectOptions(
      screen.getByLabelText("Подключение tls"),
      "client",
    );
    await user.click(
      within(screen.getByRole("row", { name: /^tls / })).getByText(
        "В черновик",
      ),
    );
    expect(save).toHaveBeenCalledWith({
      pg: { deploymentRef: "pg1" },
      tls: { profileRef: "client" },
    });
  });
  it("resets only the selected binding", async () => {
    const { user, save } = setup();
    await user.click(
      within(screen.getByRole("row", { name: /^pg / })).getByText("Сбросить"),
    );
    expect(save).toHaveBeenCalledWith({ tls: { profileRef: "server" } });
  });
  it("retains dirty state after rejected staging", async () => {
    const { user, dirty } = setup(vi.fn(async () => false));
    await user.selectOptions(screen.getByLabelText("Подключение pg"), "pg2");
    await user.click(
      within(screen.getByRole("row", { name: /^pg / })).getByText("В черновик"),
    );
    expect(dirty).toHaveBeenLastCalledWith(true);
  });
});

it.each([{ refs: [] }, { refs: ["szi/sso"] }])(
  "keeps the declared application kind even without candidates and preserves a mismatched saved binding until staging: %j",
  async ({ refs }) => {
    const save = vi.fn(async () => true);
    render(
      <ApplicationBindings
        value={{ identity: { deploymentRef: "old-service" } }}
        hints={{ identity: "deployment" }}
        candidates={connectionCandidates(
          { identity: ["sso"] },
          { "old-service": "docker" },
          refs,
        )}
        deployments={["old-service"]}
        profiles={[]}
        providedConnections={refs}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Тип подключения identity")).toHaveProperty(
      "value",
      "providedConnectionRef",
    );
    expect(screen.getByLabelText("Тип подключения identity")).toHaveProperty(
      "disabled",
      true,
    );
    expect(
      screen.getByText(/Сохранённая привязка имеет другой тип/),
    ).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
    if (refs.length) {
      await userEvent.selectOptions(
        screen.getByLabelText("Подключение identity"),
        "szi/sso",
      );
      await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
      expect(save).toHaveBeenCalledWith({
        identity: { providedConnectionRef: { libraryId: "szi", name: "sso" } },
      });
    }
  },
);

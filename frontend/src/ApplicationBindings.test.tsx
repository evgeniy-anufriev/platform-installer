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
          sso: { deploymentRefs: [], providedConnectionRefs: ["szi/sso"] },
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
    expect(options("sso")).toEqual([""]);
    await userEvent.selectOptions(
      screen.getByLabelText("Тип подключения sso"),
      "providedConnectionRef",
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
  it("selects a Vault binding in the same table using its existing alias", async () => {
    const user = userEvent.setup(),
      select = vi.fn(async () => true);
    render(
      <ApplicationBindings
        value={{
          store: { deploymentRef: "qa-vault" },
          other: { deploymentRef: "qa-other-vault" },
          pg: { deploymentRef: "pg1" },
        }}
        hints={{}}
        deployments={["qa-vault", "qa-other-vault", "pg1"]}
        deploymentTypes={{
          "qa-vault": "vault",
          "qa-other-vault": "vault",
          pg1: "postgresql",
        }}
        vaultBinding="store"
        onSelectVault={select}
        profiles={[]}
        disabled={false}
        onSave={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      within(screen.getByRole("row", { name: /^store / })).getByText(
        "Хранилище секретов",
      ),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("row", { name: /^pg / })).queryByText(
        "Для секретов",
      ),
    ).toBeNull();
    await user.click(
      within(screen.getByRole("row", { name: /^other / })).getByText(
        "Для секретов",
      ),
    );
    expect(select).toHaveBeenCalledWith("other");
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
  it("clears the selected reference when switching reference kind", async () => {
    const { user, save } = setup();
    await user.selectOptions(
      screen.getByLabelText("Тип подключения pg"),
      "profileRef",
    );
    expect(
      (screen.getByLabelText("Подключение pg") as HTMLSelectElement).value,
    ).toBe("");
    await user.selectOptions(screen.getByLabelText("Подключение pg"), "client");
    await user.click(
      within(screen.getByRole("row", { name: /^pg / })).getByText("В черновик"),
    );
    expect(save).toHaveBeenCalledWith({
      pg: { profileRef: "client" },
      tls: { profileRef: "server" },
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

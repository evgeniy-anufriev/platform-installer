import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApplicationLibraryResources } from "./ApplicationLibraryResources";

const resources = {
  database: {
    kind: "postgresql.database",
    binding: "pg",
    parameters: { name: "app_db" },
    mode: "existing",
  },
  schema: {
    kind: "postgresql.schema",
    binding: "pg",
    databaseRef: "database",
    parameters: { name: "app_schema" },
  },
};
function setup() {
  const save = vi.fn(async () => true);
  const dirty = vi.fn();
  render(
    <ApplicationLibraryResources
      deployments={{ "qa-postgresql": { serviceType: "postgresql" } }}
      resources={resources}
      bindings={{ pg: { deploymentRef: "qa-postgresql" } }}
      disabled={false}
      onSave={save}
      onDirtyChange={dirty}
    />,
  );
  return { user: userEvent.setup(), save, dirty };
}
describe("library resource table", () => {
  it("uses the database name as its key and filters bindings when type changes", async () => {
    const save = vi.fn(async () => true),
      user = userEvent.setup();
    render(
      <ApplicationLibraryResources
        resources={{}}
        bindings={{
          pg: { deploymentRef: "qa-pg" },
          ch: { deploymentRef: "qa-ch" },
          pki: { deploymentRef: "qa-pki" },
        }}
        deployments={{
          "qa-pg": { serviceType: "postgresql" },
          "qa-ch": { serviceType: "clickhouse" },
          "qa-pki": { serviceType: "pki" },
        }}
        disabled={false}
        onDirtyChange={vi.fn()}
        onSave={save}
      />,
    );
    await user.click(screen.getByText("Добавить БД"));
    expect(screen.queryByLabelText("ID ресурса")).toBeNull();
    const connection = screen.getByLabelText("Подключение библиотеки");
    expect(connection.textContent).toContain("qa-pg");
    expect(connection.textContent).not.toContain("qa-ch");
    expect(connection.textContent).not.toContain("qa-pki");
    await user.selectOptions(
      screen.getByLabelText("Тип", { exact: true }),
      "clickhouse.database",
    );
    expect(connection.textContent).toContain("qa-ch");
    expect(connection.textContent).not.toContain("qa-pg");
    await user.type(screen.getByLabelText("Имя БД / схемы"), "analytics");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith({
      analytics: {
        kind: "clickhouse.database",
        binding: "ch",
        mode: "managed",
        parameters: { name: "analytics" },
      },
    });
  });
  it("groups resources by deployment without recursive add-value forms", () => {
    setup();
    expect(screen.getByText("qa-postgresql")).toBeTruthy();
    expect(screen.queryByText("Добавить значение")).toBeNull();
    expect(screen.getByText("app_schema")).toBeTruthy();
  });
  it("renames a schema while preserving its database reference and sibling resources", async () => {
    const { user, save, dirty } = setup();
    await user.click(screen.getAllByText("Настроить")[1]);
    await user.clear(screen.getByLabelText("Имя БД / схемы"));
    await user.type(screen.getByLabelText("Имя БД / схемы"), "new_schema");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith({
      ...resources,
      schema: {
        ...resources.schema,
        mode: "managed",
        parameters: { name: "new_schema" },
      },
    });
    expect(dirty).toHaveBeenLastCalledWith(false);
  });
  it("adds another database without replacing existing resources", async () => {
    const { user, save } = setup();
    await user.click(screen.getByText("Добавить БД"));
    await user.type(screen.getByLabelText("Имя БД / схемы"), "another_db");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith({
      ...resources,
      another_db: {
        kind: "postgresql.database",
        binding: "pg",
        mode: "managed",
        parameters: { name: "another_db" },
      },
    });
  });
  it("removes only the selected declaration after confirmation", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user, save } = setup();
    await user.click(screen.getAllByText("Удалить")[1]);
    expect(save).toHaveBeenCalledWith({ database: resources.database });
    confirm.mockRestore();
  });
  it("does not stage duplicate resource IDs", async () => {
    const { user, save } = setup();
    await user.click(screen.getByText("Добавить БД"));
    await user.type(screen.getByLabelText("Имя БД / схемы"), "database");
    await user.click(screen.getByText("В черновик"));
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeTruthy();
  });
  it("pages the resource list while retaining deployment grouping", async () => {
    const user = userEvent.setup();
    render(
      <ApplicationLibraryResources
        deployments={{ "qa-postgresql": { serviceType: "postgresql" } }}
        resources={{
          ...resources,
          extra: { ...resources.database, parameters: { name: "extra_db" } },
        }}
        bindings={{ pg: { deploymentRef: "qa-postgresql" } }}
        disabled={false}
        onSave={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(screen.queryByText("extra_db")).toBeNull();
    await user.click(screen.getByText("Далее"));
    expect(screen.getByText("extra_db")).toBeTruthy();
    expect(screen.getByText("qa-postgresql")).toBeTruthy();
  });
  it("retains edits and dirty state when staging is rejected", async () => {
    const save = vi.fn(async () => false),
      dirty = vi.fn(),
      user = userEvent.setup();
    render(
      <ApplicationLibraryResources
        deployments={{ "qa-postgresql": { serviceType: "postgresql" } }}
        resources={resources}
        bindings={{ pg: { deploymentRef: "qa-postgresql" } }}
        disabled={false}
        onSave={save}
        onDirtyChange={dirty}
      />,
    );
    await user.click(screen.getAllByText("Настроить")[0]);
    await user.type(screen.getByLabelText("Имя БД / схемы"), "_edited");
    await user.click(screen.getByText("В черновик"));
    expect(screen.getByDisplayValue("app_db_edited")).toBeTruthy();
    expect(dirty).toHaveBeenLastCalledWith(true);
  });
});

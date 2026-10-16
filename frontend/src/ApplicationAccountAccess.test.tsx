import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ApplicationAccountAccess,
  ApplicationRedisAccess,
} from "./ApplicationAccountAccess";

const resources = {
  main: {
    kind: "postgresql.database",
    binding: "pg",
    parameters: { name: "app_main" },
  },
  foreign: { kind: "postgresql.database", binding: "other" },
  analytics: { kind: "clickhouse.database", binding: "ch" },
};
const bindings = {
  pg: { deploymentRef: "qa-pg" },
  other: { deploymentRef: "other-pg" },
  ch: { deploymentRef: "qa-ch" },
};
describe("account database access", () => {
  it("adds database-wide rights using same-provider resources and creator roles", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <ApplicationAccountAccess
        serviceType="postgresql"
        deployment="qa-pg"
        resources={resources}
        bindings={bindings}
        account={{ databaseAccess: [] }}
        inherited={{}}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Добавить доступ/ }),
    );
    expect(screen.queryByRole("option", { name: "foreign" })).toBeNull();
    expect(screen.queryByRole("option", { name: "analytics" })).toBeNull();
    await userEvent.selectOptions(
      screen.getByLabelText("База данных доступа"),
      "main",
    );
    await userEvent.click(screen.getByLabelText("SELECT"));
    await userEvent.click(screen.getByText("Создатели будущих объектов"));
    await userEvent.type(
      screen.getByLabelText("Роли миграций"),
      "app_migrator",
    );
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      databaseAccess: [
        {
          databaseRef: "main",
          privileges: ["SELECT"],
          additionalCreatorRoles: ["app_migrator"],
        },
      ],
    });
  });
  it("requires confirmation before switching precise inherited grants", async () => {
    const save = vi.fn().mockResolvedValue(true),
      confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <ApplicationAccountAccess
        serviceType="postgresql"
        deployment="qa-pg"
        resources={resources}
        bindings={bindings}
        account={{}}
        inherited={{ databaseRef: "main", grants: [] }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Настроить доступ/ }),
    );
    expect(save).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await userEvent.click(
      screen.getByRole("button", { name: /Настроить доступ/ }),
    );
    expect(save).toHaveBeenCalledWith({ databaseAccess: [] });
    confirm.mockRestore();
  });
  it("removes last row without deleting account or database", async () => {
    const save = vi.fn().mockResolvedValue(true),
      confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <ApplicationAccountAccess
        serviceType="postgresql"
        deployment="qa-pg"
        resources={resources}
        bindings={bindings}
        account={{
          databaseAccess: [{ databaseRef: "main", privileges: ["SELECT"] }],
        }}
        inherited={{}}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
    expect(save).toHaveBeenCalledWith({ databaseAccess: [] });
    confirm.mockRestore();
  });
  it("keeps form dirty on rejected stage", async () => {
    const dirty = vi.fn();
    render(
      <ApplicationAccountAccess
        serviceType="clickhouse"
        deployment="qa-ch"
        resources={resources}
        bindings={bindings}
        account={{ grants: [] }}
        inherited={{}}
        disabled={false}
        onSave={vi.fn().mockResolvedValue(false)}
        onDirtyChange={dirty}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /Добавить доступ/ }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("База данных доступа"),
      "analytics",
    );
    await userEvent.click(screen.getByLabelText("SELECT"));
    expect(screen.queryByLabelText("UPDATE")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(screen.getByLabelText("База данных доступа")).toBeTruthy();
    expect(dirty).toHaveBeenLastCalledWith(true);
  });
  it("edits structured Redis ACL and preserves wildcard strings", async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(
      <ApplicationRedisAccess
        value={{ commands: ["get"], keys: ["app:*"] }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText("ACL commands"), ", set");
    await userEvent.type(screen.getByLabelText("ACL channels"), "events:*");
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenCalledWith({
      commands: ["get", "set"],
      keys: ["app:*"],
      channels: ["events:*"],
    });
  });
});

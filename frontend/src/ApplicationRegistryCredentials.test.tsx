import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationRegistryCredentials } from "./ApplicationRegistryCredentials";

describe("library registry credentials", () => {
  it("opens immediately and saves authored sources without loading Core descriptors", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(
      <ApplicationRegistryCredentials
        libraryId="szi"
        projectRevision="saved-revision"
        value={{
          "registry.example": {
            username: {
              source: { kind: "runtime_secret_ref", ref: "registry-user" },
            },
            password: {
              source: { kind: "runtime_secret_ref", ref: "registry-password" },
            },
          },
        }}
        registries={[]}
        disabled={false}
        runtimeDisabled={false}
        onChange={vi.fn()}
        save={save}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Логин и пароль registry" }),
    );
    fireEvent.change(screen.getByLabelText("Логин: registry.example"), {
      target: { value: "operator" },
    });
    fireEvent.change(screen.getByLabelText("Пароль: registry.example"), {
      target: { value: "synthetic-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить в сессии" }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith({
        projectRevision: "saved-revision",
        descriptorSetFingerprint: "",
        serviceDeployment: "",
        applicationLibrary: "szi",
        applicationSourceValues: {
          "registry-user": "operator",
          "registry-password": "synthetic-password",
        },
        values: {},
      }),
    );
    expect(
      await screen.findByText("Логин и пароль сохранены только в сессии"),
    ).toBeTruthy();
    expect(screen.queryByLabelText("Пароль: registry.example")).toBeNull();
  });
  it("stages references and leaves actual values to the runtime session", () => {
    const onChange = vi.fn();
    render(
      <ApplicationRegistryCredentials
        libraryId="sdku-main"
        value={{}}
        registries={["registry.example"]}
        disabled={false}
        runtimeDisabled
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Registry"), {
      target: { value: "registry.example" },
    });
    fireEvent.click(screen.getByText("Настроить runtime-доступ"));
    const pair = onChange.mock.calls[0][0]["registry.example"];
    expect(pair.username.source.kind).toBe("runtime_secret_ref");
    expect(pair.password.source.kind).toBe("runtime_secret_ref");
    expect(pair.password.source.ref).not.toBe(pair.username.source.ref);
    expect(pair.password.source).not.toHaveProperty("value");
  });

  it("removes one registry assignment without modifying the other", () => {
    const onChange = vi.fn();
    render(
      <ApplicationRegistryCredentials
        libraryId="sdku-main"
        value={{ "a.example": { id: "a" }, "b.example": { id: "b" } }}
        registries={[]}
        disabled={false}
        runtimeDisabled
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getAllByText("Убрать назначение")[0]);
    expect(onChange).toHaveBeenCalledWith({ "b.example": { id: "b" } });
  });
});

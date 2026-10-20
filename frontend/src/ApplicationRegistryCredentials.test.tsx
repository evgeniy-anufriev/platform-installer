import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationRegistryCredentials } from "./ApplicationRegistryCredentials";

describe("library registry credentials", () => {
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

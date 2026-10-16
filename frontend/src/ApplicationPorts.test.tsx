import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApplicationPorts, type PortSource } from "./ApplicationPorts";

function setup(
  sources: PortSource[] = [],
  value: Record<string, unknown> = {},
  accept = true,
) {
  const save = vi.fn(async () => accept),
    dirty = vi.fn();
  render(
    <ApplicationPorts
      sources={sources}
      value={value}
      disabled={false}
      onSave={save}
      onDirtyChange={dirty}
    />,
  );
  return { user: userEvent.setup(), save, dirty };
}
describe("ports and sources", () => {
  it("offers an explicit empty state and Add port", () => {
    setup();
    expect(screen.getByText(/Порты не заданы/)).toBeTruthy();
    expect(screen.getByText("Добавить порт")).toBeTruthy();
  });
  it("shows each source separately without merging a partial host override", () => {
    setup([
      { label: "Пакет", ports: { http: { published: 8080, container: 80 } } },
      { label: "Размещение · node1", ports: { http: { published: 9090 } } },
      {
        label: "Core · node1",
        ports: { http: { published: 9090, container: 80 } },
      },
    ]);
    expect(
      within(screen.getByRole("row", { name: /Размещение/ })).getByText(
        "9090 → —",
      ),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("row", { name: /Core/ })).getByText("9090 → 80"),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("row", { name: /Пакет/ })).getByText("8080 → 80"),
    ).toBeTruthy();
  });
  it("stages a complete Host to Container pair", async () => {
    const { user, save, dirty } = setup();
    await user.click(screen.getByText("Добавить порт"));
    await user.type(screen.getByLabelText("Имя порта"), "http");
    await user.type(screen.getByLabelText("Host", { exact: true }), "28481");
    await user.type(
      screen.getByLabelText("Container", { exact: true }),
      "8080",
    );
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith("http", {
      published: 28481,
      container: 8080,
    });
    expect(dirty).toHaveBeenLastCalledWith(false);
  });
  it("keeps ports within contract range", async () => {
    const { user, save } = setup();
    await user.click(screen.getByText("Добавить порт"));
    await user.type(screen.getByLabelText("Имя порта"), "http");
    await user.type(screen.getByLabelText("Host", { exact: true }), "65536");
    await user.type(
      screen.getByLabelText("Container", { exact: true }),
      "8080",
    );
    expect(screen.getByText("В черновик").hasAttribute("disabled")).toBe(true);
    expect(save).not.toHaveBeenCalled();
  });
  it("cannot silently replace an existing authored listener", async () => {
    const { user, save } = setup([], { http: { published: 1, container: 2 } });
    await user.click(screen.getByText("Добавить порт"));
    await user.type(screen.getByLabelText("Имя порта"), "http");
    await user.type(screen.getByLabelText("Host", { exact: true }), "80");
    await user.type(
      screen.getByLabelText("Container", { exact: true }),
      "8080",
    );
    await user.click(screen.getByText("В черновик"));
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(save).not.toHaveBeenCalled();
  });
  it("prefills an inherited pair and keeps it dirty when staging is rejected", async () => {
    const { user, save, dirty } = setup(
      [
        {
          label: "Библиотека",
          ports: { http: { published: 80, container: 8080 } },
        },
      ],
      {},
      false,
    );
    await user.click(screen.getByText("Переопределить"));
    expect(
      (screen.getByLabelText("Host", { exact: true }) as HTMLInputElement)
        .value,
    ).toBe("80");
    await user.click(screen.getByText("В черновик"));
    expect(save).toHaveBeenCalledWith("http", {
      published: 80,
      container: 8080,
    });
    expect(dirty).toHaveBeenLastCalledWith(true);
  });
});

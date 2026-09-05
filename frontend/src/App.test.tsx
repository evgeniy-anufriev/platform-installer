import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("UI-01B read-only shell", () => {
  it("opens and closes a Core snapshot without exposing edit actions", async () => {
    const api = { chooseProject: vi.fn().mockResolvedValue({ status: "OPEN", root: "C:/fixture", snapshot: { status: "PASS", project: { name: "Fixture" }, projectRevision: "sha256:abc", snapshotFingerprint: "sha256:def", hosts: { node1: {} }, serviceDeployments: {}, pki: {}, findings: [], documents: [] } }), closeProject: vi.fn().mockResolvedValue({ status: "NO_PROJECT" }) };
    render(<App api={api} />);
    await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
    expect(await screen.findByRole("heading", { name: "Fixture" })).toBeTruthy();
    expect(screen.getByText("Только чтение")).toBeTruthy();
    expect(screen.queryByText("Сохранить")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Закрыть проект" }));
    expect(await screen.findByText("Откройте существующий проект")).toBeTruthy();
  });
});

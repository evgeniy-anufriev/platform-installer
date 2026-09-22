import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InstallationPage } from "./InstallationPage";

const state = {
  apiVersion: "platform.installer/installation-state/v1alpha1" as const,
  kind: "InstallationState" as const,
  status: "PREREQUISITES_REQUIRED" as const,
  project: {
    id: "project-aaaaaaaaaaaaaaaa",
    revision: "sha256:revision",
    verificationStatus: "UNVERIFIED",
    hasUnsavedChanges: false,
  },
  executionNode: { status: "NOT_PREPARED", safeLabel: "node1 · 192.0.2.10" },
  plan: { status: "NOT_CREATED" as const },
  prerequisites: [{
    code: "EXECUTION_NODE_READY_REQUIRED",
    destination: "servers" as const,
    safeMessage: "A READY Execution Node is required before creating an installation plan.",
  }],
};

describe("InstallationPage", () => {
  it("renders only safe prerequisite state and routes preparation to Servers", async () => {
    const user = userEvent.setup();
    const onOpenServers = vi.fn();
    render(<InstallationPage state={state} tab="summary" onTabChange={vi.fn()} onOpenServers={onOpenServers} />);

    expect(screen.getByText("EXECUTION_NODE_READY_REQUIRED")).toBeTruthy();
    expect(screen.getByText("node1 · 192.0.2.10")).toBeTruthy();
    expect(screen.queryByText("Сформировать свежий план")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Открыть Серверы" }));
    expect(onOpenServers).toHaveBeenCalledOnce();
  });

  it("keeps plan, execution and result as read-only stages in UI-02A", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<InstallationPage state={state} tab="summary" onTabChange={onTabChange} onOpenServers={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "План" }));
    expect(onTabChange).toHaveBeenCalledWith("plan");
    expect(screen.queryByText("Runtime secrets")).toBeNull();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import {
  ApplicationRuntimeSecretField,
  ApplicationSecretAvailabilityBadge,
  type ApplicationSecretSession,
} from "./ApplicationRuntimeSecretField";
import type { RuntimeSecretDescriptorOperation } from "./backend";

const evidence: RuntimeSecretDescriptorOperation = {
  status: "READY",
  projectRevision: "saved",
  descriptorSetFingerprint: "fingerprint",
  applicationSecretAvailability: { requirement: false },
  applicationInputs: [
    {
      requirementRef: "requirement",
      purpose: "APPLICATION_SECRET",
      sourceRef: "resolved-password",
      displayLabel: "Database password",
      providerDeployment: null,
      applicationLibraries: ["library"],
      hosts: ["node"],
      operations: [],
    },
  ],
};
const setup = (overrides: Partial<ApplicationSecretSession> = {}) => ({
  libraryId: "library",
  projectRevision: "saved",
  disabled: false,
  availability: evidence,
  load: vi.fn().mockResolvedValue(evidence),
  save: vi.fn().mockResolvedValue(undefined),
  ...overrides,
});

describe("inline application runtime secret", () => {
  it("reports aggregate presence only when all required resource secrets are present", () => {
    const session = setup();
    const view = render(
      <ApplicationSecretAvailabilityBadge
        session={session}
        sourceRefs={["resolved-password"]}
        resolved
      />,
    );
    expect(screen.getByText("Секрет не задан")).toBeTruthy();
    view.rerender(
      <ApplicationSecretAvailabilityBadge
        session={{
          ...session,
          availability: {
            ...evidence,
            applicationSecretAvailability: { requirement: true },
          },
        }}
        sourceRefs={["resolved-password", "unknown"]}
        resolved
      />,
    );
    expect(screen.getByText("Статус секрета недоступен")).toBeTruthy();
    view.rerender(
      <ApplicationSecretAvailabilityBadge
        session={{
          ...session,
          availability: {
            ...evidence,
            applicationSecretAvailability: { requirement: true },
          },
        }}
        sourceRefs={["resolved-password"]}
        resolved
      />,
    );
    expect(screen.getByText("Секрет задан")).toBeTruthy();
    view.rerender(
      <ApplicationSecretAvailabilityBadge
        session={{ ...session, disabled: true }}
        sourceRefs={["resolved-password"]}
        resolved
      />,
    );
    expect(screen.getByText("Статус секрета недоступен")).toBeTruthy();
  });
  it("submits only the matching Core requirement and clears the input without changing the reference", async () => {
    const session = setup();
    render(
      <ApplicationRuntimeSecretField
        session={session}
        sourceRef="resolved-password"
        label="db password"
      />,
    );
    const input = screen.getByLabelText("db password") as HTMLInputElement;
    expect(input.type).toBe("password");
    await userEvent.type(input, "synthetic-inline-only");
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии: db password" }),
    );
    await waitFor(() =>
      expect(session.save).toHaveBeenCalledWith({
        projectRevision: "saved",
        descriptorSetFingerprint: "fingerprint",
        serviceDeployment: "",
        applicationLibrary: "library",
        applicationRequirementRef: "requirement",
        values: { requirement: "synthetic-inline-only" },
      }),
    );
    expect(input.value).toBe("");
    // A successful call is not authoritative presence evidence.
    expect(screen.queryByText("Секрет задан")).toBeNull();
  });
  it("rejects stale descriptors and clears the secret on failure", async () => {
    const session = setup({
      load: vi.fn().mockResolvedValue({ ...evidence, projectRevision: "old" }),
    });
    render(
      <ApplicationRuntimeSecretField
        session={session}
        sourceRef="resolved-password"
        label="db password"
      />,
    );
    await userEvent.type(screen.getByLabelText("db password"), "synthetic");
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии: db password" }),
    );
    await screen.findByText(/Не удалось сохранить секрет/);
    expect(session.save).not.toHaveBeenCalled();
    expect(
      (screen.getByLabelText("db password") as HTMLInputElement).value,
    ).toBe("");
  });
  it("discards input and positive status on a context change", async () => {
    const session = setup({
      availability: {
        ...evidence,
        applicationSecretAvailability: { requirement: true },
      },
    });
    const view = render(
      <ApplicationRuntimeSecretField
        session={session}
        sourceRef="resolved-password"
        label="db password"
        shared
      />,
    );
    expect(screen.getByText(/несколькими ресурсами/)).toBeTruthy();
    await userEvent.type(screen.getByLabelText("db password"), "synthetic");
    view.rerender(
      <ApplicationRuntimeSecretField
        session={{ ...session, projectRevision: "new" }}
        sourceRef="resolved-password"
        label="db password"
      />,
    );
    expect(
      (screen.getByLabelText("db password") as HTMLInputElement).value,
    ).toBe("");
  });
  it("requires an exact source and library match", async () => {
    const session = setup({ libraryId: "other" });
    render(
      <ApplicationRuntimeSecretField
        session={session}
        sourceRef="resolved-password"
        label="db password"
      />,
    );
    await userEvent.type(screen.getByLabelText("db password"), "synthetic");
    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить в сессии: db password" }),
    );
    await screen.findByText(/Не удалось сохранить секрет/);
    expect(session.save).not.toHaveBeenCalled();
  });
});

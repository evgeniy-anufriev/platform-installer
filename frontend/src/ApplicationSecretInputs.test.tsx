import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationSecretInputs } from "./ApplicationSecretInputs";
import type { RuntimeSecretDescriptorOperation } from "./backend";

const result: RuntimeSecretDescriptorOperation = {
  status: "READY",
  projectRevision: "revision",
  descriptorSetFingerprint: "fingerprint",
  applicationInputs: [
    {
      requirementRef: "application-secret-reference",
      purpose: "APPLICATION_SECRET",
      providerDeployment: null,
      applicationLibraries: ["sdku"],
      hosts: ["node1"],
      operations: [
        "APPLICATION_LIBRARIES_APPLY",
        "APPLICATION_LIBRARIES_VERIFY",
      ],
      sourceRef: "database-password",
      displayLabel: "Database password",
    },
  ],
};

describe("application runtime inputs", () => {
  it("submits the exact Core binding through the existing runtime values API and clears the form", async () => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
    };
    const user = userEvent.setup(),
      load = vi.fn().mockResolvedValue(result),
      save = vi.fn().mockResolvedValue(undefined);
    render(
      <ApplicationSecretInputs disabled={false} load={load} save={save} />,
    );
    await user.click(screen.getByRole("button", { name: "Секреты библиотек" }));
    await user.type(
      await screen.findByLabelText("Database password"),
      "synthetic-only",
    );
    await user.click(
      screen.getByRole("button", { name: "Сохранить в сессии" }),
    );
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith({
        projectRevision: "revision",
        descriptorSetFingerprint: "fingerprint",
        serviceDeployment: "",
        values: { "application-secret-reference": "synthetic-only" },
      }),
    );
    expect(screen.queryByLabelText("Database password")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Секреты библиотек" }));
    expect(
      ((await screen.findByLabelText("Database password")) as HTMLInputElement)
        .value,
    ).toBe("");
  });
  it("does not offer input after Core refuses descriptors", async () => {
    const load = vi.fn().mockResolvedValue({
      status: "UNAVAILABLE",
      error: { message: "Core unavailable" },
    });
    render(
      <ApplicationSecretInputs disabled={false} load={load} save={vi.fn()} />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Секреты библиотек" }),
    );
    expect((await screen.findByRole("status")).textContent).toContain(
      "Core unavailable",
    );
    expect(
      screen.queryByRole("button", { name: "Сохранить в сессии" }),
    ).toBeNull();
  });
});

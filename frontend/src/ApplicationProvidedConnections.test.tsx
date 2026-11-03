import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApplicationProvidedConnections } from "./ApplicationProvidedConnections";
import { ApplicationBindings } from "./ApplicationBindings";

it("submits a provider credential only to the runtime session using Core references", async () => {
  const save = vi.fn().mockResolvedValue(undefined);
  const structuralSave = vi.fn();
  render(
    <ApplicationProvidedConnections
      definitions={{
        sso: {
          application: "keycloak",
          protocol: "https",
          credentials: {
            password: {
              source: { kind: "runtime_secret_ref", ref: "authored-ref" },
            },
          },
        },
      }}
      value={{}}
      resolved={{
        sso: {
          credentials: {
            password: {
              source: { kind: "runtime_secret_ref", ref: "resolved-ref" },
            },
          },
        },
      }}
      disabled={false}
      onSave={structuralSave}
      onDirtyChange={vi.fn()}
      secretSession={{
        projectRevision: "rev",
        libraryId: "szi",
        disabled: false,
        load: async () => ({
          status: "READY",
          projectRevision: "rev",
          descriptorSetFingerprint: "fp",
          applicationInputs: [
            {
              purpose: "APPLICATION_SECRET" as const,
              sourceRef: "resolved-ref",
              requirementRef: "requirement",
              applicationLibraries: ["szi"],
              providerDeployment: null,
              hosts: [],
              operations: [],
              displayLabel: "Provider password",
            },
          ],
        }),
        save,
      }}
    />,
  );
  await userEvent.type(
    screen.getByLabelText("sso · password"),
    "synthetic-test-value",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сохранить в сессии: sso · password" }),
  );
  expect(save).toHaveBeenCalledWith(
    expect.objectContaining({
      applicationRequirementRef: "requirement",
      values: { requirement: "synthetic-test-value" },
    }),
  );
  expect(structuralSave).not.toHaveBeenCalled();
  expect(
    (screen.getByLabelText("sso · password") as HTMLInputElement).value,
  ).toBe("");
  await waitFor(() =>
    expect(
      (screen.getByLabelText("sso · password") as HTMLInputElement).disabled,
    ).toBe(false),
  );
  expect(screen.getByText("Секрет отправлен в сессию")).toBeTruthy();
  await userEvent.type(
    screen.getByLabelText("sso · password"),
    "synthetic-replacement",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Сохранить в сессии: sso · password" }),
  );
  expect(save).toHaveBeenCalledTimes(2);
});

it("shows library connection presence from the same session evidence as application credentials", () => {
  const input = {
    purpose: "APPLICATION_SECRET" as const,
    sourceRef: "admin",
    requirementRef: "requirement",
    applicationLibraries: ["szi"],
    providerDeployment: null,
    hosts: [],
    operations: [],
    displayLabel: "Admin",
  };
  const props = {
    definitions: {
      sso: {
        application: "keycloak",
        credentials: {
          password: { source: { kind: "runtime_secret_ref", ref: "admin" } },
        },
      },
    },
    resolved: {
      sso: {
        credentials: {
          password: { source: { kind: "runtime_secret_ref", ref: "admin" } },
        },
      },
    },
    value: {},
    disabled: false,
    onSave: vi.fn(),
    onDirtyChange: vi.fn(),
    secretSession: {
      projectRevision: "rev",
      libraryId: "szi",
      disabled: false,
      load: vi.fn(),
      save: vi.fn(),
      availability: {
        status: "READY" as const,
        projectRevision: "rev",
        applicationInputs: [input],
        applicationSecretAvailability: { requirement: false },
      },
    },
  };
  const view = render(<ApplicationProvidedConnections {...props} />);
  expect(screen.getByText("Секрет не задан").closest("h3")).toBeTruthy();
  view.rerender(
    <ApplicationProvidedConnections
      {...props}
      secretSession={{
        ...props.secretSession,
        availability: {
          ...props.secretSession.availability,
          applicationSecretAvailability: { requirement: true },
        },
      }}
    />,
  );
  expect(screen.getByText("Секрет задан").closest("h3")).toBeTruthy();
  view.rerender(
    <ApplicationProvidedConnections
      {...props}
      secretSession={{
        ...props.secretSession,
        availability: {
          ...props.secretSession.availability,
          projectRevision: "old",
          applicationSecretAvailability: { requirement: true },
        },
      }}
    />,
  );
  expect(screen.getByText("Статус секрета недоступен")).toBeTruthy();
});

describe("application provided connections", () => {
  it("selects an explicit library export without changing the binding alias or siblings", async () => {
    const save = vi.fn(async () => true),
      user = userEvent.setup();
    render(
      <ApplicationBindings
        value={{
          identity: {
            providedConnectionRef: { libraryId: "provider", name: "previous" },
          },
          storage: { deploymentRef: "vault" },
        }}
        hints={{}}
        deployments={["old", "vault"]}
        profiles={[]}
        providedConnections={["provider/api"]}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      (screen.getByLabelText("Тип подключения identity") as HTMLSelectElement)
        .disabled,
    ).toBe(true);
    await user.selectOptions(
      screen.getByLabelText("Подключение identity"),
      "provider/api",
    );
    await user.click(
      within(screen.getByRole("row", { name: /^identity / })).getByText(
        "В черновик",
      ),
    );
    expect(save).toHaveBeenCalledWith({
      identity: {
        providedConnectionRef: { libraryId: "provider", name: "api" },
      },
      storage: { deploymentRef: "vault" },
    });
  });
  it("keeps unavailable references visible when no current Core candidates exist", () => {
    render(
      <ApplicationBindings
        value={{
          identity: {
            providedConnectionRef: { libraryId: "provider", name: "api" },
          },
        }}
        hints={{}}
        deployments={[]}
        profiles={[]}
        providedConnections={[]}
        disabled={false}
        onSave={vi.fn()}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("option", { name: /provider\/api · недоступно/ }),
    ).toBeTruthy();
  });
  it("allows literal only with non-sensitive metadata and resets one export", async () => {
    const save = vi.fn(async () => true),
      user = userEvent.setup();
    render(
      <ApplicationProvidedConnections
        definitions={{
          api: {
            application: "server",
            protocol: "https",
            parameters: { tenant: "default" },
            credentials: {
              login: {
                sensitive: false,
                source: { kind: "literal", value: "operator" },
              },
              token: { source: { kind: "runtime_secret_ref", ref: "token" } },
            },
          },
        }}
        value={{
          api: { parameters: { tenant: "override" } },
          other: { parameters: { untouched: true } },
        }}
        resolved={{ api: { url: "https://api.example.test" } }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    expect(
      within(screen.getByRole("group", { name: "login" })).getByRole("option", {
        name: "Значение",
      }),
    ).toBeTruthy();
    expect(
      within(screen.getByRole("group", { name: "token" })).queryByRole(
        "option",
        { name: "Значение" },
      ),
    ).toBeNull();
    expect(screen.getByText(/https:\/\/api.example.test/)).toBeTruthy();
    await user.click(screen.getByText("Сбросить подключение api"));
    expect(save).toHaveBeenCalledWith({
      other: { parameters: { untouched: true } },
    });
  });
});

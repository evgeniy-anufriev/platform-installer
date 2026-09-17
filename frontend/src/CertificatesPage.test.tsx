import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { type CertificateIntent, CertificatesPage } from "./CertificatesPage";
import type { OpenResult } from "./backend";

const managed = {
  projectRevision: "sha256:revision",
  servers: {},
  deployments: {},
  pki: {
    authorities: {
      "platform.ca": { mode: "MANAGED", commonName: "Platform CA" },
    },
    profiles: {
      "server.profile": {
        authorityRef: "platform.ca",
        sanPolicy: { includeHostDns: false },
        usages: [],
      },
    },
    tlsProfiles: {
      "infrastructure.tls": {
        certificateProfileRef: "server.profile",
        storePasswordSecretRef: "runtime:actual-secret-name",
      },
    },
    scopes: {},
  },
} as unknown as OpenResult["managed"];

function props(
  overrides: Partial<ComponentProps<typeof CertificatesPage>> = {},
) {
  return {
    managed,
    intents: [] as CertificateIntent[],
    busy: false,
    structuralDisabled: false,
    commandCount: 0,
    sourceOptions: {
      hosts: ["node1"],
      deployments: ["kafka-main"],
      members: [{ deploymentId: "kafka-main", memberId: "kafka-kafka-1" }],
    },
    onAppend: vi.fn().mockResolvedValue(true),
    onReview: vi.fn(),
    onDiscard: vi.fn(),
    ...overrides,
  };
}

describe("UI-01G2 CertificatesPage", () => {
  it("uses typed scope intent for direct source inputs without calculating SAN", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(<CertificatesPage {...props({ onAppend })} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Добавить" })[3],
    );
    await userEvent.type(screen.getByLabelText("ID"), "kafka.scope");
    await userEvent.selectOptions(
      screen.getByLabelText("Certificate profile"),
      "server.profile",
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "node1" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "kafka-main/kafka-kafka-1" }),
    );
    await userEvent.type(
      screen.getByLabelText("Explicit DNS names"),
      "kafka.example.test",
    );
    await userEvent.type(
      screen.getByLabelText("Explicit IP addresses"),
      "192.0.2.10",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(onAppend).toHaveBeenCalledWith({
      operation: "CreateCertificateScope",
      entityId: "kafka.scope",
      entity: {
        profile: "server.profile",
        sources: {
          hosts: ["node1"],
          members: [{ deploymentId: "kafka-main", memberId: "kafka-kafka-1" }],
          explicitDnsNames: ["kafka.example.test"],
          explicitIpAddresses: ["192.0.2.10"],
        },
      },
    });
    expect(screen.queryByText(/SAN preview/i)).toBeNull();
  });

  it("masks stored SecretRef and never renders its runtime name", () => {
    render(<CertificatesPage {...props()} />);
    expect(screen.getByText(/runtime:••••/)).toBeTruthy();
    expect(screen.queryByText("runtime:actual-secret-name")).toBeNull();
  });

  it("retains an explicit empty usages array on complete profile update", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(<CertificatesPage {...props({ onAppend })} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Изменить" })[1],
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить в черновик" }),
    );
    expect(onAppend).toHaveBeenCalledWith({
      operation: "UpdateCertificateProfile",
      entityId: "server.profile",
      entity: {
        authorityRef: "platform.ca",
        sanPolicy: { includeHostDns: false },
        usages: [],
      },
    });
  });

  it("keeps explicit false distinct from inherited SAN policy", async () => {
    render(<CertificatesPage {...props()} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Изменить" })[1],
    );
    const selector = screen.getByLabelText(
      "includeHostDns",
    ) as HTMLSelectElement;
    expect(selector.value).toBe("false");
    await userEvent.selectOptions(selector, "");
    expect(selector.value).toBe("");
  });
});

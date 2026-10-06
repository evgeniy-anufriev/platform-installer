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
  it("sets and replaces the Java-store password in the active session", async () => {
    const user = userEvent.setup();
    const onSetPKIStorePassword = vi.fn().mockResolvedValue({
      status: "PRESENT",
      sudoPasswordStatus: "NOT_PROVIDED",
      pkiStorePasswordStatus: "PRESENT",
    });
    const view = render(
      <CertificatesPage
        {...props({
          credentialStatus: {
            status: "PRESENT",
            sudoPasswordStatus: "NOT_PROVIDED",
            pkiStorePasswordStatus: "MISSING",
          },
          onSetPKIStorePassword,
        })}
      />,
    );
    const input = screen.getByLabelText("Новый пароль хранилищ");
    await user.type(input, "first-test-password");
    await user.click(
      screen.getByRole("button", { name: "Сохранить пароль в сеансе" }),
    );
    expect(onSetPKIStorePassword).toHaveBeenNthCalledWith(
      1,
      "first-test-password",
    );
    expect((input as HTMLInputElement).value).toBe("");

    view.rerender(
      <CertificatesPage
        {...props({
          credentialStatus: {
            status: "PRESENT",
            sudoPasswordStatus: "NOT_PROVIDED",
            pkiStorePasswordStatus: "PRESENT",
          },
          onSetPKIStorePassword,
        })}
      />,
    );
    await user.type(input, "replacement-test-password");
    await user.click(
      screen.getByRole("button", { name: "Заменить пароль в сеансе" }),
    );
    expect(onSetPKIStorePassword).toHaveBeenNthCalledWith(
      2,
      "replacement-test-password",
    );
    expect((input as HTMLInputElement).value).toBe("");
  });

  it("uses typed scope intent for direct source inputs without calculating SAN", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(<CertificatesPage {...props({ onAppend })} />);
    await userEvent.click(
      screen.getAllByRole("button", { name: "Добавить" })[3],
    );
    await userEvent.type(screen.getByLabelText("ID"), "kafka.scope");
    await userEvent.selectOptions(
      screen.getByLabelText("Профиль сертификата"),
      "server.profile",
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "node1" }));
    await userEvent.click(
      screen.getByRole("checkbox", { name: "kafka-main/kafka-kafka-1" }),
    );
    await userEvent.type(
      screen.getByLabelText("Явные DNS-имена"),
      "kafka.example.test",
    );
    await userEvent.type(
      screen.getByLabelText("Явные IP-адреса"),
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
      "DNS-имена серверов",
    ) as HTMLSelectElement;
    expect(selector.value).toBe("false");
    await userEvent.selectOptions(selector, "");
    expect(selector.value).toBe("");
  });

  it("renders only current Core identity evidence and keeps Core findings visible", () => {
    render(
      <CertificatesPage
        {...props({
          verification: { status: "VERIFIED" },
          verifiedPKI: {
            status: "CURRENT",
            identities: [
              {
                id: "platform-tls--kafka-main",
                scope: "DEPLOYMENT",
                tlsProfileId: "platform-tls",
                dnsNames: ["kafka.example.test"],
                ipAddresses: ["192.0.2.44"],
                consumers: [
                  {
                    deploymentId: "kafka-main",
                    memberId: "kafka-kafka-1",
                    hostId: "node1",
                  },
                ],
              },
            ],
          },
        })}
      />,
    );
    expect(screen.getByText("kafka.example.test")).toBeTruthy();
    expect(screen.getByText("192.0.2.44")).toBeTruthy();
    expect(screen.getByText(/kafka-main\/kafka-kafka-1 @ node1/)).toBeTruthy();
  });

  it("does not render identity or SAN rows from invalid evidence", () => {
    render(
      <CertificatesPage
        {...props({
          verification: {
            status: "INVALID",
            findings: [
              {
                code: "CERTIFICATE_REISSUE_REQUIRED",
                severity: "BLOCKED",
                summary: "Certificate reissue is required",
              },
            ],
          },
          verifiedPKI: {
            status: "INVALID",
            findings: [
              {
                code: "CERTIFICATE_REISSUE_REQUIRED",
                severity: "BLOCKED",
                summary: "Certificate reissue is required",
              },
            ],
          },
        })}
      />,
    );
    expect(screen.getByText(/CERTIFICATE_REISSUE_REQUIRED/)).toBeTruthy();
    expect(screen.queryByText("kafka.example.test")).toBeNull();
  });

  it("shows stale saved-revision evidence without a current PKI view", () => {
    render(
      <CertificatesPage
        {...props({
          verification: { status: "STALE" },
          verifiedPKI: undefined,
        })}
      />,
    );
    expect(
      screen.getByText(
        "Проверка устарела: запустите проверку сохранённой ревизии снова.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Проект ещё не проверен Core.")).toBeNull();
  });

  it("shows the safe verification error instead of stale PKI view status", () => {
    render(
      <CertificatesPage
        {...props({
          verification: {
            status: "UNVERIFIED",
            error: {
              code: "PROJECT_SNAPSHOT_FAILED",
              message:
                "Core не смог построить снимок проекта. Проект на диске не изменён.",
            },
          },
          verifiedPKI: { status: "NOT_VERIFIED" },
        })}
      />,
    );

    expect(
      screen.getByText(
        "Core не смог построить снимок проекта. Проект на диске не изменён.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Проект ещё не проверен Core.")).toBeNull();
  });
});

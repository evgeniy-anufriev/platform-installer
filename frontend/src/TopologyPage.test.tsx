import { render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { EndpointPreview, OpenResult } from "./backend";
import {
  type ProviderIntent,
  type TopologyIntent,
  TopologyPage,
} from "./TopologyPage";
import type { ServerIntent } from "./ServersPage";

const managed = {
  projectRevision: "sha256:revision",
  servers: {},
  deployments: {
    alpha: {
      deploymentId: "alpha",
      serviceType: "known",
      mode: "cluster",
    },
    beta: {
      deploymentId: "beta",
      serviceType: "removed-service",
      mode: "removed-mode",
    },
  },
} as unknown as OpenResult["managed"];

const catalog = {
  status: "READY",
  expectedBundleDigest: "sha256:bundle",
  expectedCatalogDigest: "sha256:catalog",
  services: [
    {
      id: "known",
      definitionVersion: "1",
      displayName: "Known service",
      ui: {},
      endpointConsumer: false,
      endpointProvider: false,
      modes: [
        {
          id: "cluster",
          displayName: "Cluster",
          placementKind: "MEMBER_SCOPED",
          roles: [],
          guidance: { minParticipants: 1, distinctHosts: false },
        },
      ],
    },
  ],
} as unknown as OpenResult["catalog"];

const props = () => ({
  managed,
  catalog,
  intents: [] as TopologyIntent[],
  serverIntents: [] as ServerIntent[],
  busy: false,
  structuralDisabled: false,
  commandCount: 0,
  onAppend: vi.fn().mockResolvedValue(true),
  onReview: vi.fn(),
  onDiscard: vi.fn(),
  activeTab: "services" as "services" | "servers" | "entryPoints",
  onActiveTabChange: vi.fn(),
  selectedDeploymentId: "",
  onSelectedDeploymentChange: vi.fn(),
  selectedHostId: "",
  onSelectedHostChange: vi.fn(),
  onConfigureDeployment: vi.fn(),
  onConfigureMember: vi.fn(),
  preview: undefined as EndpointPreview | undefined,
  verificationStatus: "UNVERIFIED" as const,
});

function ControlledTopology(input: ReturnType<typeof props>) {
  const [tab, setTab] = useState<"services" | "servers" | "entryPoints">(
    input.activeTab,
  );
  const [deployment, setDeployment] = useState(input.selectedDeploymentId);
  const [host, setHost] = useState(input.selectedHostId);
  return (
    <TopologyPage
      {...input}
      activeTab={tab}
      onActiveTabChange={(value) => {
        setTab(value);
        input.onActiveTabChange(value);
      }}
      selectedDeploymentId={deployment}
      onSelectedDeploymentChange={(value) => {
        setDeployment(value);
        input.onSelectedDeploymentChange(value);
      }}
      selectedHostId={host}
      onSelectedHostChange={(value) => {
        setHost(value);
        input.onSelectedHostChange(value);
      }}
    />
  );
}

describe("UI-01F3 TopologyPage", () => {
  it("shows host-scoped placement without inventing a member settings target", async () => {
    const onConfigureDeployment = vi.fn();
    const onConfigureMember = vi.fn();
    const hostManaged = {
      ...managed,
      servers: { node1: { hostId: "node1" } },
      hostPlacements: [{ deploymentId: "alpha", hostId: "node1", roles: [], priority: 100 }],
    } as unknown as OpenResult["managed"];
    const hostCatalog = {
      ...catalog,
      services: [{
        ...(catalog!.services![0]),
        modes: [{ id: "cluster", placementKind: "HOST_SCOPED", roles: [], guidance: { minParticipants: 1, distinctHosts: false } }],
      }],
    } as unknown as OpenResult["catalog"];
    render(<ControlledTopology {...props()} managed={hostManaged} catalog={hostCatalog}
      selectedDeploymentId="alpha" onConfigureDeployment={onConfigureDeployment}
      onConfigureMember={onConfigureMember} />);
    expect(screen.getByRole("heading", { name: "Размещение на серверах" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Настроить участника" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Настроить экземпляр" }));
    expect(onConfigureDeployment).toHaveBeenCalledWith("alpha");
    expect(onConfigureMember).not.toHaveBeenCalled();
  });

  it("shows role-first member cards and preserves member and deployment settings routes", async () => {
    const onConfigureDeployment = vi.fn();
    const onConfigureMember = vi.fn();
    const memberManaged = {
      ...managed,
      servers: {
        node1: { hostId: "node1", address: "192.168.56.101" },
        node2: { hostId: "node2", address: "192.168.56.102" },
      },
      memberPlacements: [
        { deploymentId: "alpha", memberId: "alpha-primary", hostId: "node1", roles: ["primary"] },
        { deploymentId: "alpha", memberId: "alpha-secondary", hostId: "node2", roles: ["secondary"] },
      ],
    } as unknown as OpenResult["managed"];
    render(<ControlledTopology {...props()} managed={memberManaged}
      selectedDeploymentId="alpha" onConfigureDeployment={onConfigureDeployment}
      onConfigureMember={onConfigureMember} />);

    expect(screen.getByText("node1")).toBeTruthy();
    expect(screen.getByText("primary")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Очистить размещение" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "По серверам" }));
    expect(screen.getByRole("button", {
      name: "Изменить размещение alpha на сервере node1",
    })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", {
      name: "Настроить участника alpha-primary на сервере node1",
    }));
    expect(onConfigureMember).toHaveBeenCalledWith("alpha", "alpha-primary");
  });

  it("keeps clearing a placement available through the placement editor", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    const memberManaged = {
      ...managed,
      memberPlacements: [
        { deploymentId: "alpha", memberId: "alpha-primary", hostId: "node1", roles: ["primary"] },
      ],
    } as unknown as OpenResult["managed"];
    render(<ControlledTopology {...props()} managed={memberManaged}
      selectedDeploymentId="alpha" onAppend={onAppend} />);

    await userEvent.click(screen.getByRole("button", { name: "Изменить размещение" }));
    await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(onAppend).toHaveBeenCalledWith({
      operation: "ReconcileDeploymentPlacement",
      deploymentId: "alpha",
      members: [],
    });
  });

  it("keeps explicit selection while search temporarily hides it", async () => {
    render(<ControlledTopology {...props()} />);
    await userEvent.click(screen.getByRole("button", { name: /beta/ }));
    expect(
      screen.getByText("Неизвестный сохранённый тип (removed-service)"),
    ).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Поиск"), "alpha");
    expect(
      screen.getByText(
        "Выбранный экземпляр скрыт фильтром. Очистите поиск, чтобы открыть подробности.",
      ),
    ).toBeTruthy();
    await userEvent.clear(screen.getByLabelText("Поиск"));
    expect(
      screen.getByText("Неизвестный сохранённый тип (removed-service)"),
    ).toBeTruthy();
  });

  it("enforces the common 16-command presentation bound", () => {
    render(<ControlledTopology {...props()} commandCount={16} />);
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(screen.getByText("16 / 16 изменений")).toBeTruthy();
  });

  it("shows remaining shared draft capacity on entry points", () => {
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        commandCount={16}
      />,
    );
    expect(screen.getByText("Черновик: 16 из 16 · осталось 0")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Добавить группу" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("edits endpoint groups only through the published endpoint intent", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        onAppend={onAppend}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить группу" }),
    );
    await userEvent.type(screen.getByLabelText("ID"), "edge");
    await userEvent.type(screen.getByLabelText("Домен"), "edge.example.test");
    await userEvent.click(screen.getByRole("button", { name: "Добавить" }));
    expect(onAppend).toHaveBeenCalledWith({
      operation: "CreateEndpointGroup",
      endpointGroupId: "edge",
      endpointGroup: {
        address: { domain: "edge.example.test", wildcard: false },
      },
    });
  });

  it("shows INVALID findings without FQDN or provider preview", () => {
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        preview={{
          status: "INVALID",
          findings: [
            {
              code: "ENDPOINT_INVALID",
              severity: "ERROR",
              summary: "safe finding",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/Адреса и provider\/VIP не показаны/)).toBeTruthy();
    expect(screen.getByText(/ENDPOINT_INVALID: safe finding/)).toBeTruthy();
    expect(screen.queryByText("FQDN")).toBeNull();
  });

  it("appends one complete provider reconcile intent from Entry points", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    const providerManaged = {
      ...managed,
      deployments: {
        provider: {
          deploymentId: "provider",
          serviceType: "keepalived",
          mode: "vrrp",
          providerEditState: "NONE",
        },
      },
      endpointGroups: {
        edge: {
          endpointGroupId: "edge",
          domain: "edge.example.test",
          wildcard: false,
        },
      },
    } as unknown as OpenResult["managed"];
    const providerCatalog = {
      status: "READY",
      expectedBundleDigest: "sha256:bundle",
      expectedCatalogDigest: "sha256:catalog",
      services: [
        {
          id: "keepalived",
          definitionVersion: "1",
          displayName: "Keepalived",
          ui: {},
          endpointConsumer: false,
          endpointProvider: true,
          modes: [
            {
              id: "vrrp",
              displayName: "VRRP",
              placementKind: "HOST_SCOPED",
              roles: [],
              guidance: { minParticipants: 1, distinctHosts: false },
            },
          ],
        },
      ],
    } as unknown as OpenResult["catalog"];
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        managed={providerManaged}
        catalog={providerCatalog}
        onAppend={onAppend}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Настроить" }));
    await userEvent.selectOptions(
      screen.getByLabelText("Endpoint group"),
      "edge",
    );
    await userEvent.type(screen.getByLabelText("VRID"), "42");
    await userEvent.type(screen.getByLabelText("IPv4 1"), "192.0.2.42");
    await userEvent.type(screen.getByLabelText("Interface 1"), "eth0");
    await userEvent.click(
      screen.getByRole("button", { name: "Применить к черновику" }),
    );
    expect(onAppend).toHaveBeenCalledWith({
      operation: "ReconcileEndpointProvider",
      deploymentId: "provider",
      endpointGroupId: "edge",
      virtualRouterId: 42,
      virtualAddresses: [{ address: "192.0.2.42", interface: "eth0" }],
    });
  });

  it("keeps provider clear available when the catalog is unavailable", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        managed={
          {
            ...managed,
            deployments: {
              provider: {
                deploymentId: "provider",
                serviceType: "keepalived",
                mode: "vrrp",
                endpointGroupRef: "edge",
                virtualRouterId: 42,
                virtualAddresses: [
                  { address: "192.0.2.42", interface: "eth0" },
                ],
                providerEditState: "EDITABLE",
              },
            },
          } as unknown as OpenResult["managed"]
        }
        catalog={{ status: "UNAVAILABLE" } as OpenResult["catalog"]}
        onAppend={onAppend}
      />,
    );
    expect(screen.getByRole("button", { name: "Настроить" })).toHaveProperty(
      "disabled",
      true,
    );
    await userEvent.click(screen.getByRole("button", { name: "Очистить" }));
    expect(onAppend).toHaveBeenCalledWith({
      operation: "ClearEndpointProvider",
      deploymentId: "provider",
    });
  });

  it("labels a provider draft as stale without inferring a PKI result", () => {
    render(
      <ControlledTopology
        {...props()}
        activeTab="entryPoints"
        intents={
          [
            {
              operation: "ReconcileEndpointProvider",
              deploymentId: "provider",
              endpointGroupId: "edge",
              virtualRouterId: 42,
              virtualAddresses: [{ address: "192.0.2.42", interface: "eth0" }],
            },
          ] as ProviderIntent[]
        }
        preview={{ status: "STALE" }}
      />,
    );
    expect(
      screen.getByText(/Конфигурация provider изменена в черновике/),
    ).toBeTruthy();
    expect(
      screen.getByText(/влияние на PKI\/SAN определяет только Core/),
    ).toBeTruthy();
  });

  it("blocks all structural CRUD in refresh-required state", () => {
    render(<ControlledTopology {...props()} structuralDisabled />);
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(
      screen.getByRole("button", { name: "Удалить экземпляр" }),
    ).toHaveProperty("disabled", true);
  });

  it("uses one complete member placement intent with an editable generated ID", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(
      <ControlledTopology
        {...props()}
        selectedDeploymentId="alpha"
        serverIntents={
          [
            {
              operation: "CreateServer",
              hostId: "node1",
              type: "linux",
              address: "192.0.2.10",
              desiredHostname: "node1",
            },
          ] as ServerIntent[]
        }
        onAppend={onAppend}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить размещение" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить узел сервиса" }),
    );
    expect(
      (screen.getByLabelText("Member ID 1") as HTMLInputElement).value,
    ).toBe("known-1");
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(onAppend).toHaveBeenCalledWith({
      operation: "ReconcileDeploymentPlacement",
      deploymentId: "alpha",
      members: [{ memberId: "known-1", hostId: "node1", roles: [] }],
    });
  });

  it("opens the same complete editor from the By servers entry point", async () => {
    const onAppend = vi.fn().mockResolvedValue(true);
    render(
      <ControlledTopology
        {...props()}
        activeTab="servers"
        selectedHostId="node1"
        serverIntents={
          [
            {
              operation: "CreateServer",
              hostId: "node1",
              type: "linux",
              address: "192.0.2.10",
              desiredHostname: "node1",
            },
          ] as ServerIntent[]
        }
        onAppend={onAppend}
      />,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Deployment для размещения"),
      "alpha",
    );
    expect(
      screen.getByRole("heading", { name: "Размещение: alpha" }),
    ).toBeTruthy();
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить узел сервиса" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Применить" }));
    expect(onAppend).toHaveBeenCalledWith({
      operation: "ReconcileDeploymentPlacement",
      deploymentId: "alpha",
      members: [{ memberId: "known-1", hostId: "node1", roles: [] }],
    });
  });
});

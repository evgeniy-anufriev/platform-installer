import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { OpenResult } from "./backend";
import { TopologyPage } from "./TopologyPage";

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
  intents: [],
  busy: false,
  structuralDisabled: false,
  commandCount: 0,
  onAppend: vi.fn().mockResolvedValue(true),
  onReview: vi.fn(),
  onDiscard: vi.fn(),
});

describe("UI-01F3 TopologyPage", () => {
  it("keeps explicit selection while search temporarily hides it", async () => {
    render(<TopologyPage {...props()} />);
    await userEvent.click(screen.getByRole("button", { name: /beta/ }));
    expect(
      screen.getByText("Неизвестный сохранённый тип (removed-service)"),
    ).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Поиск"), "alpha");
    expect(
      screen.getByText(
        "Выбранный deployment скрыт фильтром. Очистите поиск, чтобы открыть подробности.",
      ),
    ).toBeTruthy();
    await userEvent.clear(screen.getByLabelText("Поиск"));
    expect(
      screen.getByText("Неизвестный сохранённый тип (removed-service)"),
    ).toBeTruthy();
  });

  it("enforces the common 16-command presentation bound", () => {
    render(<TopologyPage {...props()} commandCount={16} />);
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(screen.getByText("16 / 16 изменений")).toBeTruthy();
  });

  it("blocks all structural CRUD in refresh-required state", () => {
    render(<TopologyPage {...props()} structuralDisabled />);
    expect(
      screen.getByRole("button", { name: "Добавить экземпляр" }),
    ).toHaveProperty("disabled", true);
    expect(
      screen.getByRole("button", { name: "Удалить deployment" }),
    ).toHaveProperty("disabled", true);
  });
});

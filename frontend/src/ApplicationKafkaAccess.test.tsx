import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationKafkaAccess } from "./ApplicationKafkaAccess";
import { ApplicationCredentials } from "./ApplicationCredentials";

const template = "{{ application_instance_id }}";
const coreGrants = [
  { topicRef: "events", operations: ["Read", "Describe"] },
  {
    resourceType: "group",
    name: "actual-consumer",
    patternType: "prefixed",
    operations: ["Read"],
  },
  {
    resourceType: "cluster",
    name: "kafka-cluster",
    operations: ["IdempotentWrite"],
  },
];
const props = () => ({
  account: {},
  inherited: {},
  resolved: { grants: coreGrants },
  resolvedResources: { events: { parameters: { name: "actual-events" } } },
  disabled: false,
  onSave: vi.fn().mockResolvedValue(true),
  onDirtyChange: vi.fn(),
});

describe("Kafka ACL", () => {
  it("immediately displays current Core topics, groups and other grants without saving", () => {
    const p = props();
    render(<ApplicationKafkaAccess {...p} />);
    for (const name of [
      "actual-events",
      "actual-consumer",
      "kafka-cluster",
      "IdempotentWrite",
    ])
      expect(screen.getByRole("cell", { name })).toBeTruthy();
    expect(p.onSave).not.toHaveBeenCalled();
  });
  it("drops the Core display when freshness is revoked", () => {
    const p = props();
    const { rerender } = render(<ApplicationKafkaAccess {...p} />);
    rerender(
      <ApplicationKafkaAccess {...p} resolved={{}} resolvedResources={{}} />,
    );
    expect(screen.queryByRole("cell", { name: "actual-consumer" })).toBeNull();
    expect(screen.getByText(/Нет актуальной проекции Core/)).toBeTruthy();
    expect(
      (
        screen.getByRole("button", {
          name: "Переопределить ACL",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });
  it("copies the Core baseline only on explicit override and retains refs and unrelated ACLs", async () => {
    const p = props();
    const { rerender } = render(<ApplicationKafkaAccess {...p} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить ACL" }),
    );
    // Dirty form invalidates the parent projection; the intentional edit must survive.
    rerender(
      <ApplicationKafkaAccess {...p} resolved={{}} resolvedResources={{}} />,
    );
    await userEvent.clear(screen.getByLabelText("Операции ACL 1"));
    await userEvent.type(
      screen.getByLabelText("Операции ACL 1"),
      "Read, Write",
    );
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(p.onSave).toHaveBeenCalledWith([
      { topicRef: "events", operations: ["Read", "Write"] },
      ...coreGrants.slice(1),
    ]);
  });
  it("edits existing authored templates without replacing them with resolved names", async () => {
    const p = props();
    render(
      <ApplicationKafkaAccess
        {...p}
        account={{
          grants: [
            { resourceType: "group", name: template, operations: ["Read"] },
          ],
        }}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить ACL" }),
    );
    expect(
      (screen.getByLabelText("Имя или ссылка ACL 1") as HTMLInputElement).value,
    ).toBe(template);
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(p.onSave).toHaveBeenCalledWith([
      { resourceType: "group", name: template, operations: ["Read"] },
    ]);
  });
  it("stages empty grants explicitly; reset removes only the grants override", async () => {
    const p = props();
    render(<ApplicationKafkaAccess {...p} account={{ grants: [] }} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить ACL" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(p.onSave).toHaveBeenLastCalledWith([]);
    await userEvent.click(
      screen.getByRole("button", { name: "Сбросить ACL к наследованию" }),
    );
    expect(p.onSave).toHaveBeenLastCalledWith(undefined);
  });
  it("keeps failed edits and cancels without saving", async () => {
    const p = props();
    p.onSave.mockResolvedValue(false);
    render(<ApplicationKafkaAccess {...p} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить ACL" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByLabelText("Операции ACL 1")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Отмена" }));
    expect(p.onSave).toHaveBeenCalledTimes(1);
    expect(p.onDirtyChange).toHaveBeenLastCalledWith(false);
  });
  it("adds a consumer group and preserves the account credentials through the existing parent writer", async () => {
    const save = vi.fn().mockResolvedValue(true);
    const credentials = {
      username: { source: { kind: "literal", value: template } },
    };
    render(
      <ApplicationCredentials
        defaults={{ accounts: { kafka: { mode: "managed", credentials } } }}
        authored={{
          accounts: {
            kafka: { mode: "managed", credentials, grants: coreGrants },
          },
        }}
        resolvedAccounts={{ kafka: { grants: coreGrants } }}
        resolvedResources={props().resolvedResources}
        connections={{ kafka: { library_binding: "messaging" } }}
        bindings={{ messaging: { deploymentRef: "qa-kafka" } }}
        deploymentTypes={{ "qa-kafka": "kafka" }}
        disabled={false}
        onSave={save}
        onDirtyChange={vi.fn()}
      />,
    );
    const block = within(screen.getByRole("group", { name: "ACL Kafka" }));
    await userEvent.click(
      block.getByRole("button", { name: "Переопределить ACL" }),
    );
    await userEvent.click(block.getByRole("button", { name: "Добавить ACL" }));
    await userEvent.selectOptions(
      block.getByLabelText("Ресурс ACL 4"),
      "group",
    );
    await userEvent.type(
      block.getByLabelText("Имя или ссылка ACL 4"),
      "custom-group",
    );
    await userEvent.type(
      block.getByLabelText("Операции ACL 4"),
      "Read, Describe",
    );
    await userEvent.click(block.getByRole("button", { name: "В черновик" }));
    expect(save).toHaveBeenLastCalledWith({
      kafka: {
        mode: "managed",
        credentials,
        grants: [
          ...coreGrants,
          {
            resourceType: "group",
            name: "custom-group",
            patternType: "literal",
            operations: ["Read", "Describe"],
          },
        ],
      },
    });
    await userEvent.click(
      block.getByRole("button", { name: "Сбросить ACL к наследованию" }),
    );
    expect(save).toHaveBeenLastCalledWith({
      kafka: { mode: "managed", credentials },
    });
  });
});

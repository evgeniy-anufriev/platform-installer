import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ApplicationTopicBindings } from "./ApplicationTopicBindings";

it("hides redundant bindings for direct resource keys", () => {
  const { container } = render(
    <ApplicationTopicBindings
      connections={{ kafka: { library_binding: "messaging" } }}
      bindings={{ messaging: { deploymentRef: "cluster" } }}
      deployments={{ cluster: { serviceType: "kafka" } }}
      resources={{}}
      defaults={{}}
      authored={{}}
      disabled={false}
      onSave={vi.fn()}
      onReset={vi.fn()}
    />,
  );
  expect(container.textContent).toBe("");
});

it("selects and clears named roles independently and resets only the authored role", async () => {
  const user = userEvent.setup(),
    save = vi.fn(async () => true),
    reset = vi.fn(async () => true);
  const props = {
    connections: { kafka: { library_binding: "messaging" } },
    bindings: {
      messaging: { deploymentRef: "cluster" },
      other: { deploymentRef: "other" },
    },
    deployments: {
      cluster: { serviceType: "kafka" },
      other: { serviceType: "kafka" },
    },
    resources: {
      events: { kind: "kafka.topic", binding: "messaging", parameters: {} },
      second: { kind: "kafka.topic", binding: "messaging", parameters: {} },
      foreign: { kind: "kafka.topic", binding: "other", parameters: {} },
    },
    defaults: { kafka: { main: "events", alarms: "events" } },
    authored: {},
    resolvedTopics: { second: { name: "sdku-main-2" } },
    disabled: false,
    onSave: save,
    onReset: reset,
  };
  const view = render(<ApplicationTopicBindings {...props} />);
  expect(screen.queryByRole("option", { name: /foreign/ })).toBeNull();
  await user.selectOptions(screen.getByLabelText("Топик kafka.main"), "second");
  expect(save).toHaveBeenLastCalledWith({ kafka: { main: "second" } });
  view.rerender(
    <ApplicationTopicBindings
      {...props}
      authored={{ kafka: { main: "second" } }}
    />,
  );
  await user.selectOptions(screen.getByLabelText("Топик kafka.main"), "");
  expect(save).toHaveBeenLastCalledWith({ kafka: { main: "" } });
  await user.click(screen.getByRole("button", { name: "Сбросить · main" }));
  expect(reset).toHaveBeenCalled();
  expect(screen.getByLabelText("Топик kafka.alarms")).toHaveProperty(
    "value",
    "events",
  );
});

it("selects compatible resource IDs, preserves empty selection and resets inheritance", async () => {
  const user = userEvent.setup(),
    save = vi.fn(async () => true),
    reset = vi.fn(async () => true);
  const props = {
    connections: { kafka: { library_binding: "messaging" } },
    bindings: {
      messaging: { deploymentRef: "cluster" },
      other: { deploymentRef: "single" },
    },
    deployments: {
      cluster: { serviceType: "kafka" },
      single: { serviceType: "kafka" },
    },
    resources: {
      events: {
        kind: "kafka.topic",
        binding: "messaging",
        parameters: { name: "qa.events" },
      },
      foreign: {
        kind: "kafka.topic",
        binding: "other",
        parameters: { name: "other.events" },
      },
    },
    defaults: { kafka: ["events"] },
    authored: {},
    disabled: false,
    onSave: save,
    onReset: reset,
  };
  const view = render(<ApplicationTopicBindings {...props} />);
  expect(screen.queryByText(/other.events/)).toBeNull();
  const selected = screen.getByRole("checkbox");
  expect(selected).toHaveProperty("checked", true);
  await user.click(selected);
  expect(save).toHaveBeenCalledWith({ kafka: [] });
  view.rerender(
    <ApplicationTopicBindings {...props} authored={{ kafka: [] }} />,
  );
  expect(screen.getByRole("checkbox")).toHaveProperty("checked", false);
  await user.click(
    screen.getByRole("button", { name: "Сбросить топики · kafka" }),
  );
  expect(reset).toHaveBeenCalled();
});

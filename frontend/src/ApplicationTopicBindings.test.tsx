import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ApplicationTopicBindings } from "./ApplicationTopicBindings";

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

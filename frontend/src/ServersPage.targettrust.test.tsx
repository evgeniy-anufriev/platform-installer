import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ServersPage } from "./ServersPage";

const props = {
  snapshot: undefined,
  managed: { projectRevision: "sha256:current", servers: { node2: { hostId: "node2", address: "192.0.2.2", sshPort: 2222 } } } as never,
  empty: false,
  intents: [],
  serverTypes: [],
  configError: null,
  busy: false,
  structuralDisabled: false,
  onAppend: async () => true,
  onReview: () => undefined,
  onDiscard: () => undefined,
  commandCount: 0,
  credentialStatus: null,
  onSetCredential: async () => ({ status: "MISSING" }) as never,
  onClearCredential: async () => ({ status: "MISSING" }) as never,
  executionNode: null,
  onSelectExecutionNode: async () => ({ status: "NOT_CONFIGURED" }) as never,
  onCheckExecutionNode: async () => ({ status: "NOT_CONFIGURED" }) as never,
  onPlanExecutionNodePreparation: async () => ({ status: "BLOCKED" }) as never,
  onPrepareExecutionNode: async () => ({ status: "BLOCKED" }) as never,
};

describe("target host trust on the Servers page", () => {
  it("explains why credentials cannot be changed during an active run", async () => {
    render(
      <ServersPage
        {...props}
        onSetCredential={vi
          .fn()
          .mockRejectedValue(new Error("INSTALLATION_RUN_ACTIVE"))}
      />,
    );
    fireEvent.change(screen.getByLabelText("Технический пользователь"), {
      target: { value: "installer" },
    });
    fireEvent.change(screen.getByLabelText("SSH-пароль"), {
      target: { value: "placeholder" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить в сеансе" }));
    expect(
      await screen.findByText(
        "Нельзя изменить или очистить учётные данные, пока выполняется план установки.",
      ),
    ).toBeTruthy();
  });

  it("requires explicit approval of the bounded fingerprint", async () => {
    const onProbe = vi.fn().mockResolvedValue({ status: "APPROVAL_REQUIRED", probeId: "nonce", keyType: "ssh-ed25519", fingerprint: "SHA256:target" });
    const onApprove = vi.fn().mockResolvedValue({ status: "APPROVED", fingerprint: "SHA256:target" });
    render(<ServersPage {...props} onProbeTargetHostKey={onProbe} onApproveTargetHostKey={onApprove} onDeclineTargetHostKey={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Проверить SSH-ключ" }));
    fireEvent.click(screen.getByRole("button", { name: "Получить отпечаток" }));
    expect(await screen.findByText("SHA256:target")).toBeTruthy();
    expect(onApprove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Подтверждаю совпадение" }));
    await waitFor(() => expect(onApprove).toHaveBeenCalledWith("nonce"));
    expect(await screen.findByText(/Ключ подтверждён/)).toBeTruthy();
    expect(onProbe).toHaveBeenCalledWith("node2");
  });

  it("does not offer approval while edits are unsaved", () => {
    render(<ServersPage {...props} commandCount={1} onProbeTargetHostKey={vi.fn()} onApproveTargetHostKey={vi.fn()} onDeclineTargetHostKey={vi.fn()} />);
    expect((screen.getByRole("button", { name: "Проверить SSH-ключ" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

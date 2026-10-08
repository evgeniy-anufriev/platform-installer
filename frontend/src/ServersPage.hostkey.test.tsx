import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ServersPage } from "./ServersPage";

const base = {
  snapshot: undefined,
  managed: undefined,
  empty: true,
  intents: [],
  serverTypes: [],
  configError: null,
  busy: false,
  structuralDisabled: false,
  onAppend: async () => true,
  onReview: () => {},
  onDiscard: () => {},
  commandCount: 0,
  onSetCredential: async () => ({status:"PRESENT", sudoPasswordStatus:"NOT_PROVIDED", pkiStorePasswordStatus:"MISSING"}),
  onClearCredential: async () => ({status:"MISSING", sudoPasswordStatus:"NOT_PROVIDED", pkiStorePasswordStatus:"MISSING"}),
  executionNode: {status:"NOT_PREPARED", selectionKind:"PROJECT_SERVER", selectionSource:"EXPLICIT", selectedHostId:"node1", safeLabel:"node1 · 192.0.2.10", locked:true},
  onSelectExecutionNode: async () => ({status:"NOT_PREPARED", selectionKind:"PROJECT_SERVER", selectionSource:"EXPLICIT", selectedHostId:"node1", safeLabel:"node1", locked:true}),
  onCheckExecutionNode: async () => ({status:"NOT_PREPARED"}),
  onPlanExecutionNodePreparation: async () => ({status:"BLOCKED"}),
  onPrepareExecutionNode: async () => ({status:"BLOCKED"}),
};

describe("Execution Node SSH key approval", () => {
  it("requires explicit fingerprint comparison before binding", async () => {
    const onProbe = vi.fn().mockResolvedValue({status:"APPROVAL_REQUIRED", probeId:"opaque-probe", keyType:"ssh-ed25519", fingerprint:"SHA256:known"});
    const onApprove = vi.fn().mockResolvedValue({status:"APPROVED", fingerprint:"SHA256:known"});
    render(<ServersPage {...base} credentialStatus={{status:"PRESENT", sshMode:"SSH_PRIVATE_KEY", expiresAt:"future", sudoPasswordStatus:"NOT_PROVIDED", pkiStorePasswordStatus:"MISSING"}} onProbeExecutionNodeHostKey={onProbe} onApproveExecutionNodeHostKey={onApprove} />);
    fireEvent.click(screen.getByRole("button",{name:"Получить отпечаток SSH"}));
    expect(screen.getByRole("dialog", { name: "SSH-ключ узла выполнения" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Получить отпечаток" }));
    expect(await screen.findByText("SHA256:known")).toBeTruthy();
    expect(onApprove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Подтверждаю совпадение"}));
    await waitFor(() => expect(onApprove).toHaveBeenCalledWith("opaque-probe"));
    expect(await screen.findByText("Ключ SSH подтверждён для текущего сеанса.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(await screen.findByText("SSH-отпечаток подтверждён")).toBeTruthy();
  });

  it("offers probing with password session credentials", () => {
    render(<ServersPage {...base} credentialStatus={{status:"PRESENT", sshMode:"SSH_PASSWORD", expiresAt:"future", sudoPasswordStatus:"NOT_PROVIDED", pkiStorePasswordStatus:"MISSING"}} onProbeExecutionNodeHostKey={vi.fn()} />);
    expect((screen.getByRole("button",{name:"Получить отпечаток SSH"}) as HTMLButtonElement).disabled).toBe(false);
  });

  it("revokes an unapproved probe when the dialog is closed", async () => {
    const onProbe = vi.fn().mockResolvedValue({status:"APPROVAL_REQUIRED", probeId:"opaque-probe", keyType:"ssh-ed25519", fingerprint:"SHA256:known"});
    const onDecline = vi.fn().mockResolvedValue({status:"DECLINED"});
    render(<ServersPage {...base} credentialStatus={{status:"PRESENT", sshMode:"SSH_PRIVATE_KEY", expiresAt:"future", sudoPasswordStatus:"NOT_PROVIDED", pkiStorePasswordStatus:"MISSING"}} onProbeExecutionNodeHostKey={onProbe} onDeclineExecutionNodeHostKey={onDecline} />);
    fireEvent.click(screen.getByRole("button",{name:"Получить отпечаток SSH"}));
    fireEvent.click(screen.getByRole("button", { name: "Получить отпечаток" }));
    expect(await screen.findByText("SHA256:known")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Закрыть" }));
    await waitFor(() => expect(onDecline).toHaveBeenCalled());
    expect(screen.queryByRole("dialog", { name: "SSH-ключ узла выполнения" })).toBeNull();
  });
});

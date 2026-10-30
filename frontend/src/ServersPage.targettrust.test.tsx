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
  it("requires a check after selection before showing preparation required", async () => {
    render(<ServersPage {...props}
      executionNode={{ status: "NOT_PREPARED", selectionKind: "EXPLICIT_EXTERNAL", selectionSource: "EXPLICIT", safeLabel: "node2", locked: true } as never}
      onCheckExecutionNode={vi.fn().mockResolvedValue({ status: "PREPARATION_REQUIRED" })}
    />);
    expect(screen.getAllByText("Требуется проверка")).toHaveLength(2);
    expect(screen.queryByText("Проверен: Требуется подготовка")).toBeNull();
    const check = screen.getByRole("button", { name: "Проверить узел" });
    expect(check.classList.contains("next-step-hint")).toBe(true);
    await fireEvent.click(check);
    expect(await screen.findByText("Проверен: Требуется подготовка")).toBeTruthy();
    expect(screen.queryByText("Требуется проверка")).toBeNull();
    expect(screen.getByRole("button", { name: "Спланировать подготовку" }).classList.contains("next-step-hint")).toBe(true);
  });
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

  it("shows update required when the active execution runtime differs from the project bundle", async () => {
    const onCheckExecutionNode = vi.fn().mockResolvedValue({
      status: "UPDATE_REQUIRED",
      findings: [{
        code: "EXECUTION_NODE_RUNTIME_BUNDLE_MISMATCH",
        safeMessage: "Активный runtime bundle на узле не совпадает с проверенным bundle проекта; требуется обновление узла.",
      }],
    });
    render(<ServersPage {...props} onCheckExecutionNode={onCheckExecutionNode} />);

    fireEvent.click(screen.getByRole("button", { name: "Проверить узел" }));

    expect(await screen.findByText("Проверен: Требуется обновление")).toBeTruthy();
    expect(await screen.findByText(/Активный runtime bundle на узле не совпадает/)).toBeTruthy();
  });

  it("shows the platform finding returned by preparation planning", async () => {
    render(<ServersPage {...props} onPlanExecutionNodePreparation={vi.fn().mockResolvedValue({
      status: "INCOMPATIBLE",
      findings: [{ code: "EXECUTION_NODE_PLATFORM_INCOMPATIBLE", safeMessage: "Платформа узла redos/8.0/x86_64 не указана в наборе установки; поддерживаются: redos/8.0.3/x86_64." }],
    })} />);

    fireEvent.click(screen.getByRole("button", { name: "Спланировать подготовку" }));

    expect(await screen.findByText("Проверен: Несовместим")).toBeTruthy();
    expect(screen.getByText("Несовместим")).toBeTruthy();
    expect(await screen.findByText(/Платформа узла redos\/8\.0\/x86_64 не указана/)).toBeTruthy();
  });

  it("clears the stale update-required check after preparation succeeds", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onCheckExecutionNode = vi.fn().mockResolvedValue({
      status: "UPDATE_REQUIRED",
      findings: [{
        code: "EXECUTION_NODE_RUNTIME_BUNDLE_MISMATCH",
        safeMessage: "Активный runtime bundle на узле не совпадает с проверенным bundle проекта; требуется обновление узла.",
      }],
    });
    const onPlanExecutionNodePreparation = vi.fn().mockResolvedValue({
      status: "CONFIRMATION_REQUIRED",
      planId: "prepare-1",
      steps: [{ id: "activate", action: "ACTIVATE", mutates: true }],
    });
    const onPrepareExecutionNode = vi.fn().mockResolvedValue({ status: "PREPARED" });
    render(
      <ServersPage
        {...props}
        onCheckExecutionNode={onCheckExecutionNode}
        onPlanExecutionNodePreparation={onPlanExecutionNodePreparation}
        onPrepareExecutionNode={onPrepareExecutionNode}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Проверить узел" }));
    expect(await screen.findByText("Проверен: Требуется обновление")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Спланировать подготовку" }));
    fireEvent.click(await screen.findByRole("button", { name: "Подтвердить подготовку" }));

    await waitFor(() => expect(onPrepareExecutionNode).toHaveBeenCalledWith("prepare-1"));
    expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();
    expect(screen.queryByText(/Проверен: Требуется обновление/)).toBeNull();
    expect(screen.queryByText(/Активный runtime bundle на узле не совпадает/)).toBeNull();
    expect(screen.queryByText(/Проверка:/)).toBeNull();
    expect(screen.queryByText(/Подготовка:/)).toBeNull();
    vi.restoreAllMocks();
  });

  it("shows preparation in progress until the operation returns", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let finishPreparation!: (result: { status: string }) => void;
    const onPrepareExecutionNode = vi.fn(
      () =>
        new Promise<{ status: string }>((resolve) => {
          finishPreparation = resolve;
        }),
    );
    render(
      <ServersPage
        {...props}
        executionNode={{ status: "PREPARATION_REQUIRED", selectionKind: "PROJECT_SERVER", selectionSource: "EXPLICIT", selectedHostId: "node2", safeLabel: "node2" } as never}
        onPlanExecutionNodePreparation={vi.fn().mockResolvedValue({
          status: "CONFIRMATION_REQUIRED",
          planId: "prepare-2",
          steps: [{ id: "activate", action: "ACTIVATE", mutates: true }],
        })}
        onPrepareExecutionNode={onPrepareExecutionNode}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Спланировать подготовку" }));
    fireEvent.click(await screen.findByRole("button", { name: "Подтвердить подготовку" }));

    await waitFor(() => expect(screen.getAllByText("Выполняется подготовка")).toHaveLength(2));
    expect(screen.queryByText("Требуется подготовка")).toBeNull();
    expect(onPrepareExecutionNode).toHaveBeenCalledWith("prepare-2");
    finishPreparation({ status: "PREPARED" });
    expect(await screen.findByText("Проверен: Подготовлен")).toBeTruthy();
    expect(screen.getByText("Подготовлен")).toBeTruthy();
    vi.restoreAllMocks();
  });

  it("does not offer approval while edits are unsaved", () => {
    render(<ServersPage {...props} commandCount={1} onProbeTargetHostKey={vi.fn()} onApproveTargetHostKey={vi.fn()} onDeclineTargetHostKey={vi.fn()} />);
    expect((screen.getByRole("button", { name: "Проверить SSH-ключ" }) as HTMLButtonElement).disabled).toBe(true);
  });
});

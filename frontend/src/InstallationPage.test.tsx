import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { InstallationPage } from "./InstallationPage";

const state = {
  apiVersion: "platform.installer/installation-state/v1alpha1" as const,
  kind: "InstallationState" as const,
  status: "PREREQUISITES_REQUIRED" as const,
  project: {
    id: "project-aaaaaaaaaaaaaaaa",
    revision: "sha256:revision",
    verificationStatus: "UNVERIFIED",
    hasUnsavedChanges: false,
  },
  executionNode: { status: "NOT_PREPARED", safeLabel: "node1 · 192.0.2.10" },
  plan: { status: "NOT_CREATED" as const },
  prerequisites: [{
    code: "EXECUTION_NODE_READY_REQUIRED",
    destination: "servers" as const,
    safeMessage: "A READY Execution Node is required before creating an installation plan.",
  }],
};

describe("InstallationPage", () => {
  it("renders only safe prerequisite state and routes preparation to Servers", async () => {
    const user = userEvent.setup();
    const onOpenServers = vi.fn();
    render(<InstallationPage state={state} tab="summary" onTabChange={vi.fn()} onOpenServers={onOpenServers} busy={false} onCreatePlan={vi.fn()} onApprovePlan={vi.fn()} />);

    expect(screen.getByText("EXECUTION_NODE_READY_REQUIRED")).toBeTruthy();
    expect(screen.getByText("node1 · 192.0.2.10")).toBeTruthy();
    expect(screen.queryByText("Сформировать свежий план")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Открыть Серверы" }));
    expect(onOpenServers).toHaveBeenCalledOnce();
  });

  it("keeps secret material out of Installation navigation", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    render(<InstallationPage state={state} tab="summary" onTabChange={onTabChange} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "План" }));
    expect(onTabChange).toHaveBeenCalledWith("plan");
    expect(screen.queryByText("Runtime secrets")).toBeNull();
  });

  it("shows the bounded plan and requires each exact acknowledgement", async () => {
    const user = userEvent.setup();
    const onApprovePlan = vi.fn();
    render(<InstallationPage state={{ ...state, status: "PLAN_REVIEW", plan: { status: "PLAN_REVIEW", planId: "plan-1" } }} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={onApprovePlan} plan={{ status: "PLAN_REVIEW", plan: { id: "plan-1", status: "EXECUTABLE", projectRevision: "sha256:old", planFingerprint: "sha256:plan", executionNodeId: "node1", runtime: { bundleDigest: "sha256:bundle", coreVersion: "core", catalogDigest: "sha256:catalog", protocol: "protocol" }, expiresAt: "2026-09-22T10:00:00Z", approved: false, acknowledgements: [{ code: "ACK_RISK", summary: "Review the planned change" }], phases: [{ id: "apply", order: 0, actions: [{ id: "apply:kafka-main", type: "SERVICE_APPLY", serviceDeployment: "kafka-main", targets: ["node1"], dependsOn: [], mutating: true, reboot: "NONE", summary: "Apply Kafka" }] }] } }} />);

    expect(screen.getByText("Apply Kafka")).toBeTruthy();
    const approve = screen.getByRole("button", { name: "Одобрить план" });
    expect(approve).toHaveProperty("disabled", true);
    await user.click(screen.getByRole("checkbox"));
    await user.click(approve);
    expect(onApprovePlan).toHaveBeenCalledWith("plan-1", ["ACK_RISK"]);
  });

  it("starts only an already approved plan and renders safe execution state", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const plan = { status: "PLAN_APPROVED" as const, plan: { id: "plan-1", status: "EXECUTABLE" as const, projectRevision: "sha256:old", planFingerprint: "sha256:plan", executionNodeId: "node1", runtime: { bundleDigest: "sha256:bundle", coreVersion: "core", catalogDigest: "sha256:catalog", protocol: "protocol" }, expiresAt: "2026-09-22T10:00:00Z", approved: true, acknowledgements: [], phases: [] } };
    render(<InstallationPage state={state} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={vi.fn()} onStart={onStart} plan={plan} />);
    await user.click(screen.getByRole("button", { name: "Начать выполнение" }));
    expect(onStart).toHaveBeenCalledWith("plan-1");
  });

  it("requires a write-only PKI password before starting a plan that needs it", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const onSetPKIStorePassword = vi.fn().mockResolvedValue({ status: "PRESENT", sudoPasswordStatus: "NOT_PROVIDED", pkiStorePasswordStatus: "PRESENT" });
    const plan = { status: "PLAN_APPROVED" as const, plan: { id: "plan-pki", status: "EXECUTABLE" as const, projectRevision: "sha256:old", planFingerprint: "sha256:plan", executionNodeId: "node1", runtime: { bundleDigest: "sha256:bundle", coreVersion: "core", catalogDigest: "sha256:catalog", protocol: "protocol" }, expiresAt: "2026-09-22T10:00:00Z", approved: true, pkiStorePasswordRequired: true, acknowledgements: [], phases: [] } };
    render(<InstallationPage state={state} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={vi.fn()} onStart={onStart} plan={plan} credentialStatus={{ status: "PRESENT", sudoPasswordStatus: "NOT_PROVIDED", pkiStorePasswordStatus: "MISSING" }} onSetPKIStorePassword={onSetPKIStorePassword} />);
    expect(screen.getByRole("button", { name: "Начать выполнение" })).toHaveProperty("disabled", true);
    await user.type(screen.getByLabelText("Пароль хранилища PKI"), "write-only");
    await user.click(screen.getByRole("button", { name: "Добавить пароль в сеанс" }));
    expect(onSetPKIStorePassword).toHaveBeenCalledWith("write-only");
    expect(onStart).not.toHaveBeenCalled();
  });

  it("requires the common output password and uses the default secrets folder before plan approval", async () => {
    const user = userEvent.setup();
    const onApprovePlan = vi.fn();
    const setOutputPassword = vi.fn().mockResolvedValue(undefined);
    const plan = { status: "PLAN_REVIEW" as const, plan: { id: "plan-vault", status: "EXECUTABLE" as const, projectRevision: "sha256:revision", planFingerprint: "sha256:plan", executionNodeId: "node1", runtime: { bundleDigest: "sha256:bundle", coreVersion: "core", catalogDigest: "sha256:catalog", protocol: "protocol" }, expiresAt: "2026-09-26T10:00:00Z", approved: false, secretOutputEncryptionRequired: true, secretOutputEncryptionPasswordPresent: false, acknowledgements: [{ code: "ACK_RISK", summary: "Review changes" }], phases: [] } };
    const view = render(<InstallationPage state={state} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={onApprovePlan} plan={plan} onSetOutputEncryptionPassword={setOutputPassword} />);
    const approve = screen.getByRole("button", { name: "Одобрить план" });
    expect(approve).toHaveProperty("disabled", true);
    await user.type(screen.getByLabelText("Пароль шифрования"), "session-only");
    await user.type(screen.getByLabelText("Повторите пароль"), "session-only");
    await user.click(screen.getByRole("button", { name: "Сохранить пароль в сеансе" }));
    await user.click(screen.getByRole("checkbox"));
    expect(approve).toHaveProperty("disabled", false);
    await user.click(approve);
    expect(setOutputPassword).toHaveBeenCalledWith("session-only", "session-only");
    expect(onApprovePlan).toHaveBeenCalledWith("plan-vault", ["ACK_RISK"]);
    // Fresh backend state after expiry must override the previous local ACK.
    view.rerender(<InstallationPage state={state} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={onApprovePlan} plan={{ ...plan, plan: { ...plan.plan, secretOutputEncryptionPasswordPresent: false } }} onSetOutputEncryptionPassword={setOutputPassword} />);
    expect(screen.getByLabelText("Пароль шифрования")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Одобрить план" })).toHaveProperty("disabled", true);
    view.rerender(<InstallationPage state={state} tab="plan" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={onApprovePlan} plan={{ ...plan, plan: { ...plan.plan, id: "replacement-plan", secretOutputEncryptionPasswordPresent: false } }} onSetOutputEncryptionPassword={setOutputPassword} />);
    expect(screen.getByLabelText("Пароль шифрования")).toBeTruthy();
  });

  it("shows only safe output-delivery status and package metadata", async () => {
    const user = userEvent.setup();
    const refresh = vi.fn();
    const deliver = vi.fn();
    render(<InstallationPage state={state} tab="result" onTabChange={vi.fn()} onOpenServers={vi.fn()} busy={false} onCreatePlan={vi.fn()} onApprovePlan={vi.fn()} secretOutputPackages={{ status: "READY", packages: [{ protocol: "SecretOutputDelivery/v1alpha1", packageId: "pkg-safe", projectId: "project-1", deploymentId: "vault-ha", sourceRunId: "run-safe", runtimeDigest: "sha256:runtime", generation: 1, state: "READY", entries: ["admin-token", "unseal-shares"] }] }} outputDelivery={{ status: "DELIVERED", directory: "C:\\VaultSecrets\\vault-ha" }} onRefreshSecretOutputs={refresh} onDeliverSecretOutput={deliver} />);
    expect(screen.getByText("Зашифрованные файлы сохранены: C:\\VaultSecrets\\vault-ha")).toBeTruthy();
    expect(screen.getByText(/Защищённый пакет · vault-ha/)).toBeTruthy();
    expect(screen.queryByText(/root token|unseal key/i)).toBeNull();
    await user.click(screen.getByRole("button", { name: "Проверить ожидающие файлы" }));
    await user.click(screen.getByRole("button", { name: "Получить и сохранить зашифрованно" }));
    expect(refresh).toHaveBeenCalledOnce();
    expect(deliver).toHaveBeenCalledWith("pkg-safe");
  });
});

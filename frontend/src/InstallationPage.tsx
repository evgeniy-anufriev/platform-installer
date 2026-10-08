import { useEffect, useMemo, useRef, useState } from "react";
import type {
  InstallationEventView,
  InstallationPlanOperation,
  InstallationPlanView,
  InstallationRunOperation,
  InstallationState,
  SessionCredentialStatus,
  SecretOutputPackagesOperation,
  SecretOutputDeliveryOperation,
} from "./backend";
import {
  actionResultLabel,
  installationDisplay,
  type RunProgress,
} from "./installationPresentation";
import { executionNodeStatusLabel } from "./executionNodeLabels";
import { eventTimestampLabel, taskNameWithoutRole } from "./event-format";

type InstallationTab = "summary" | "plan" | "execution" | "result";

const tabLabels: Array<{ id: InstallationTab; label: string }> = [
  { id: "summary", label: "Сводка" },
  { id: "plan", label: "План" },
  { id: "execution", label: "Выполнение" },
  { id: "result", label: "Результат" },
];
const executionEventWindowSize = 512;

export type ServicePriorityInput = {
  serviceType: string;
  priority: number | null;
};

export type ServiceDeploymentInput = {
  deploymentId: string;
  serviceType: string;
};

export function deploymentOrderFromPriorities(
  deployments: ServiceDeploymentInput[],
  priorities: ServicePriorityInput[],
): { order: string[]; missingTypes: string[] } {
  const byType = new Map(
    priorities.map((item, index) => [item.serviceType, { ...item, index }]),
  );
  const missingTypes = [
    ...new Set(
      deployments
        .filter(
          (item) =>
            !byType.has(item.serviceType) ||
            byType.get(item.serviceType)?.priority == null,
        )
        .map((item) => item.serviceType),
    ),
  ].sort();
  if (missingTypes.length) return { order: [], missingTypes };
  return {
    order: [...deployments]
      .sort((left, right) => {
        const leftPriority = byType.get(left.serviceType)!;
        const rightPriority = byType.get(right.serviceType)!;
        return (
          leftPriority.priority! - rightPriority.priority! ||
          leftPriority.index - rightPriority.index ||
          (left.deploymentId < right.deploymentId
            ? -1
            : left.deploymentId > right.deploymentId
              ? 1
              : 0)
        );
      })
      .map((item) => item.deploymentId),
    missingTypes: [],
  };
}

const verificationLabel = (status: string) => {
  switch (status) {
    case "VERIFIED":
      return "Проверено";
    case "INVALID":
      return "Ошибки проверки";
    case "STALE":
      return "Проверка устарела";
    case "UNAVAILABLE":
      return "Проверка недоступна";
    default:
      return "Не проверено";
  }
};

const planOperationStatusLabel = (status: string) => {
  switch (status) {
    case "BLOCKED":
    case "PLAN_BLOCKED":
      return "План заблокирован";
    case "PLAN_REVIEW":
      return "План готов к рассмотрению";
    case "PLAN_APPROVED":
      return "План одобрен";
    default:
      return "Состояние плана недоступно";
  }
};

const runStatusLabel = (status: string) => {
  switch (status) {
    case "STARTING":
      return "Запуск начинается";
    case "RUNNING":
      return "Выполняется";
    case "CANCELLING":
      return "Выполняется отмена";
    case "SUCCEEDED":
      return "Успешно завершено";
    case "FAILED":
      return "Завершено с ошибкой";
    case "CANCELLED":
      return "Отменено";
    case "INTERRUPTED":
      return "Прервано";
    case "CORRUPT_ORPHANED":
      return "Состояние требует проверки";
    default:
      return "Состояние выполнения недоступно";
  }
};

const outputPackageStateLabel = (status: string) => {
  switch (status) {
    case "READY":
      return "Ожидает получения";
    case "ACKED_CLEANUP_PENDING":
      return "Получен; ожидается очистка узла";
    default:
      return "Состояние файла недоступно";
  }
};

const outputDeliveryStatusLabel = (status: string) => {
  switch (status) {
    case "DELIVERED":
      return "Файлы получены";
    case "STAGING_RETAINED":
      return "Временные файлы сохранены для безопасной очистки";
    case "ACK_PENDING":
      return "Файлы сохранены; подтверждение узла ожидается";
    case "UNAVAILABLE":
      return "Получение файлов недоступно";
    default:
      return "Состояние получения файлов недоступно";
  }
};

const planFindingMessages: Record<string, string> = {
  "Service deployment has fewer participating hosts than the selected mode requires":
    "В размещении сервиса меньше серверов, чем требует выбранный режим.",
  "Endpoint provider deployment requires endpointGroupRef":
    "Для сервиса-поставщика укажите группу точек входа.",
  "Host-scoped services use inventory host placement and must not define logical members":
    "Сервис с размещением по серверам не должен содержать логические узлы.",
  "Endpoint provider deployment requires virtualAddresses":
    "Для сервиса-поставщика укажите виртуальные IP-адреса.",
  "Endpoint provider deployment requires virtualRouterId":
    "Для сервиса-поставщика укажите ID виртуального маршрутизатора.",
  "Service secret input placement is unavailable":
    "Размещение для ввода секрета сервиса недоступно.",
  "Service deployment has fewer members than the selected mode requires":
    "В размещении сервиса меньше узлов, чем требует выбранный режим.",
  "Service deployment has fewer members with a required role than the selected mode permits":
    "В размещении сервиса не хватает узлов с обязательной ролью.",
  "Authoritative project validation is blocked":
    "Проверка проекта выявила ошибки; план установки заблокирован.",
};

const planFindingMessage = (message: string) =>
  planFindingMessages[message] || message;

export function InstallationPage({
  state,
  draftActive = false,
  tab,
  onTabChange,
  onOpenServers,
  plan,
  busy,
  onCreatePlan,
  serviceDeployments = [],
  serviceExecutionPriorities = [],
  onApprovePlan,
  approvalErrorAttempt = 0,
  run,
  runPlan,
  runProgress,
  events = [],
  onStart = () => {},
  onCancel = () => {},
  credentialStatus = null,
  onSetOutputEncryptionPassword = async () => {
    throw new Error("SECRET_OUTPUT_UNAVAILABLE");
  },
  secretOutputPackages,
  outputDelivery,
  onRefreshSecretOutputs = () => {},
  onDeliverSecretOutput = () => {},
}: {
  state?: InstallationState;
  draftActive?: boolean;
  tab: InstallationTab;
  onTabChange: (tab: InstallationTab) => void;
  onOpenServers: () => void;
  plan?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: (deploymentOrder: string[]) => void;
  serviceDeployments?: ServiceDeploymentInput[];
  serviceExecutionPriorities?: ServicePriorityInput[];
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
  approvalErrorAttempt?: number;
  run?: InstallationRunOperation;
  runPlan?: InstallationPlanView;
  runProgress?: RunProgress;
  events?: InstallationEventView[];
  onStart?: (planId: string) => void;
  onCancel?: (runId: string) => void;
  credentialStatus?: SessionCredentialStatus | null;
  onSetOutputEncryptionPassword?: (
    password: string,
    confirm: string,
  ) => Promise<void>;
  secretOutputPackages?: SecretOutputPackagesOperation;
  outputDelivery?: SecretOutputDeliveryOperation;
  onRefreshSecretOutputs?: () => void;
  onDeliverSecretOutput?: (packageId: string) => void;
}) {
  const [orderError, setOrderError] = useState("");
  const deploymentOrder = useMemo(
    () => deploymentOrderFromPriorities(serviceDeployments, serviceExecutionPriorities),
    [serviceDeployments, serviceExecutionPriorities],
  );
  const createPlan = () => {
    if (deploymentOrder.missingTypes.length) {
      setOrderError(
        "Для типов сервисов " +
          deploymentOrder.missingTypes.join(", ") +
          " не задан приоритет в application.yml.",
      );
      return;
    }
    setOrderError("");
    onCreatePlan(deploymentOrder.order);
  };
  const node = state?.executionNode;
  const presentation = installationDisplay(state, run, runProgress);
  return (
    <section className="installation-page">
      <div className="title">
        <div>
          <h1>Установка</h1>
          <p>Готовность, свежий план и выполнение сохранённой конфигурации.</p>
        </div>
        <span
          className={`readonly installation-status-pill ${presentation.tone}`}
          role="status"
        >
          <span>Текущий этап: </span>
          <strong>
            {presentation.stage === "plan"
              ? "План"
              : presentation.stage === "execution"
                ? "Выполнение"
                : "Результат"}
          </strong>
          {` · ${presentation.label}`}
          {presentation.percent !== undefined
            ? ` · ${presentation.percent}%`
            : ""}
        </span>
      </div>
      <nav
        className="installation-tabs"
        role="tablist"
        aria-label="Разделы установки"
        onKeyDown={(event) => {
          const index = tabLabels.findIndex((item) => item.id === tab);
          const next =
            event.key === "ArrowRight"
              ? (index + 1) % tabLabels.length
              : event.key === "ArrowLeft"
                ? (index - 1 + tabLabels.length) % tabLabels.length
                : event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? tabLabels.length - 1
                    : -1;
          if (next < 0) return;
          event.preventDefault();
          onTabChange(tabLabels[next].id);
          (
            event.currentTarget.querySelectorAll('[role="tab"]')[
              next
            ] as HTMLButtonElement
          )?.focus();
        }}
      >
        {tabLabels.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "active" : "outline"}
            role="tab"
            id={`installation-tab-${item.id}`}
            aria-controls={`installation-panel-${item.id}`}
            aria-selected={tab === item.id}
            tabIndex={tab === item.id ? 0 : -1}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div
        className="installation-body"
        role="tabpanel"
        id={`installation-panel-${tab}`}
        aria-labelledby={`installation-tab-${tab}`}
        tabIndex={0}
      >
        {tab === "summary" && (
          <section className="installation-summary">
            <article className="card">
              <h2>Узел выполнения · необходимое условие</h2>
              <dl>
                <dt>Состояние</dt>
                <dd>
                  {executionNodeStatusLabel(node?.status || "NOT_CONFIGURED")}
                </dd>
                <dt>Узел</dt>
                <dd>{node?.safeLabel || "Не выбран"}</dd>
                <dt>Подготовка</dt>
                <dd>Доступна только на странице «Серверы».</dd>
              </dl>
              <p>
                <button className="outline" onClick={onOpenServers}>
                  Открыть Серверы
                </button>
              </p>
            </article>
            <article className="card">
              <h2>Сохранённый проект</h2>
              {state?.project ? (
                <dl>
                  <dt>Ревизия</dt>
                  <dd>{state.project.revision}</dd>
                  <dt>Проверка</dt>
                  <dd>{verificationLabel(state.project.verificationStatus)}</dd>
                  <dt>Изменения</dt>
                  <dd>
                    {state.project.hasUnsavedChanges
                      ? "Есть несохранённые"
                      : "Сохранено"}
                  </dd>
                </dl>
              ) : (
                <p>Сохранённый проект пока недоступен.</p>
              )}
            </article>
            <article className="card installation-summary-plan">
              <div className="installation-summary-plan-heading">
                <div>
                  <h2>План установки</h2>
                  <div className="installation-summary-plan-meta">
                    <span>
                      <b>
                        {plan?.plan
                          ? plan.plan.phases.reduce(
                              (count, phase) => count + phase.actions.length,
                              0,
                            )
                          : 0}
                      </b>{" "}
                      действий
                    </span>
                    <span>Ревизия: {plan?.plan?.projectRevision || "—"}</span>
                    <span>
                      Статус:{" "}
                      {plan
                        ? planOperationStatusLabel(plan.status)
                        : "План не сформирован"}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="primary"
                  onClick={() => onTabChange("plan")}
                >
                  Открыть план
                </button>
              </div>
              {plan?.plan ? (
                <div className="installation-summary-plan-actions">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">#</th>
                        <th scope="col">Действие</th>
                        <th scope="col">Целевые узлы</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.plan.phases
                        .flatMap((phase) => phase.actions)
                        .map((action, index) => (
                          <tr key={action.id}>
                            <td>{index + 1}</td>
                            <td>{action.summary}</td>
                            <td>
                              {action.targets.join(", ") || "без целевых узлов"}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  {plan.plan.phases.every(
                    (phase) => phase.actions.length === 0,
                  ) && <p>В плане пока нет действий.</p>}
                </div>
              ) : (
                <p className="muted">
                  Предварительный список действий появится после формирования
                  свежего плана.
                </p>
              )}
            </article>
          </section>
        )}
        {tab === "plan" && (
          <PlanStage
            state={state}
            draftActive={draftActive}
            operation={plan}
            busy={busy}
            onCreatePlan={createPlan}
            orderError={orderError}
            onApprovePlan={onApprovePlan}
            approvalErrorAttempt={approvalErrorAttempt}
            onStart={onStart}
            run={run}
            credentialStatus={credentialStatus}
            onSetOutputEncryptionPassword={onSetOutputEncryptionPassword}
          />
        )}
        {tab === "execution" && (
          <ExecutionStage
            run={run}
            plan={runPlan}
            progress={runProgress}
            events={events}
            busy={busy}
            onCancel={onCancel}
            onOpenPendingOutputs={() => {
              onTabChange("result");
              onRefreshSecretOutputs();
            }}
          />
        )}
        {tab === "result" && (
          <ResultStage
            run={run}
            plan={runPlan}
            progress={runProgress}
            events={events}
            secretOutputPackages={secretOutputPackages}
            outputDelivery={outputDelivery}
            onRefreshSecretOutputs={onRefreshSecretOutputs}
            onOpenPendingOutputs={onRefreshSecretOutputs}
            onDeliverSecretOutput={onDeliverSecretOutput}
          />
        )}
      </div>
    </section>
  );
}

function PlanStage({
  state,
  draftActive,
  operation,
  busy,
  onCreatePlan,
  orderError,
  onApprovePlan,
  approvalErrorAttempt,
  onStart,
  run,
  credentialStatus,
  onSetOutputEncryptionPassword,
}: {
  state?: InstallationState;
  draftActive: boolean;
  operation?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: () => void;
  orderError: string;
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
  approvalErrorAttempt: number;
  onStart: (planId: string) => void;
  run?: InstallationRunOperation;
  credentialStatus: SessionCredentialStatus | null;
  onSetOutputEncryptionPassword: (
    password: string,
    confirm: string,
  ) => Promise<void>;
}) {
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [expandedActions, setExpandedActions] = useState<
    Record<string, boolean>
  >({});
  const [outputPasswordAcknowledgement, setOutputPasswordAcknowledgement] =
    useState<InstallationPlanOperation>();
  const outputPasswordPresent =
    !!operation?.plan?.secretOutputEncryptionPasswordPresent ||
    (!!operation && outputPasswordAcknowledgement === operation);
  const [outputPassword, setOutputPassword] = useState("");
  const [outputConfirm, setOutputConfirm] = useState("");
  const [outputError, setOutputError] = useState("");
  const errorsRef = useRef<HTMLElement>(null);
  const handledApprovalErrorAttempt = useRef(approvalErrorAttempt);
  useEffect(() => {
    if (
      approvalErrorAttempt > handledApprovalErrorAttempt.current &&
      operation?.error
    ) {
      handledApprovalErrorAttempt.current = approvalErrorAttempt;
      errorsRef.current?.focus();
    }
  }, [approvalErrorAttempt, operation?.error]);
  const plan = operation?.plan;
  if (!plan) {
    return (
      <article className="card installation-empty">
        <h2>План</h2>
        <p>{operation?.error?.message || "Свежий план ещё не создан."}</p>
        {orderError && <p className="error" role="alert">{orderError}</p>}
        <button onClick={onCreatePlan} disabled={busy}>
          Сформировать свежий план
        </button>
      </article>
    );
  }
  const requiredCodes = plan.acknowledgements.map((item) => item.code);
  const required = !!plan.pkiStorePasswordRequired;
  const present = credentialStatus?.pkiStorePasswordStatus === "PRESENT";
  const outputRequired = !!plan.secretOutputEncryptionRequired;
  const outputReady = !outputRequired || outputPasswordPresent;
  const currentPlan =
    !draftActive &&
    !state?.project?.hasUnsavedChanges &&
    state?.executionNode.status === "READY" &&
    state?.project?.revision === plan.projectRevision &&
    state?.plan.planId === plan.id;
  const canApprove =
    currentPlan &&
    state?.status === "PLAN_REVIEW" &&
    state.plan.status === "PLAN_REVIEW" &&
    plan.status === "EXECUTABLE" &&
    !plan.approved &&
    requiredCodes.every((code) => acknowledged.includes(code)) &&
    outputReady;
  const canStart =
    currentPlan &&
    !["STARTING", "RUNNING", "CANCELLING"].includes(run?.run?.state || "") &&
    state?.status === "PLAN_APPROVED" &&
    state.plan.status === "PLAN_APPROVED" &&
    plan.status === "EXECUTABLE" &&
    plan.approved;
  const startBlockers: Array<{ code: string; message: string }> = [];
  const addStartBlocker = (code: string, message: string) => {
    if (!startBlockers.some((item) => item.code === code && item.message === message))
      startBlockers.push({ code, message });
  };
  for (const prerequisite of state?.prerequisites || []) {
    const message =
      prerequisite.code === "EXECUTION_NODE_READY_REQUIRED"
        ? "Узел выполнения не готов. Откройте «Серверы» и проверьте его состояние."
        : planFindingMessage(prerequisite.safeMessage);
    addStartBlocker(prerequisite.code, message);
  }
  for (const finding of plan.findings || []) {
    addStartBlocker(finding.code, planFindingMessage(finding.safeMessage));
  }
  if (draftActive || state?.project?.hasUnsavedChanges) {
    addStartBlocker(
      "PROJECT_HAS_UNSAVED_CHANGES",
      "Есть несохранённые изменения проекта. Сохраните или отмените их и сформируйте новый план.",
    );
  }
  if (state?.executionNode.status !== "READY") {
    addStartBlocker(
      "EXECUTION_NODE_READY_REQUIRED",
      "Узел выполнения не готов. Откройте «Серверы» и проверьте его состояние.",
    );
  }
  if (state?.project?.revision !== plan.projectRevision) {
    addStartBlocker(
      "PLAN_PROJECT_REVISION_MISMATCH",
      "План создан для другой ревизии проекта. Сформируйте свежий план.",
    );
  }
  if (state?.plan.planId !== plan.id) {
    addStartBlocker(
      "PLAN_NOT_CURRENT",
      "Этот план больше не является текущим. Сформируйте свежий план.",
    );
  }
  if (
    state?.status !== "PLAN_APPROVED" ||
    state?.plan.status !== "PLAN_APPROVED"
  ) {
    addStartBlocker(
      "PLAN_APPROVAL_REQUIRED",
      "Текущий план не находится в состоянии «Одобрен». Одобрите свежий план.",
    );
  }
  if (plan.status !== "EXECUTABLE") {
    addStartBlocker(
      "PLAN_NOT_EXECUTABLE",
      "План заблокирован. Исправьте перечисленные замечания и сформируйте его заново.",
    );
  }
  if (required && !present) {
    addStartBlocker(
      "PKI_STORE_PASSWORD_REQUIRED",
      "В сеансе не задан пароль хранилищ PKCS#12, необходимый плану.",
    );
  }
  if (!outputReady) {
    addStartBlocker(
      "SECRET_OUTPUT_ENCRYPTION_PASSWORD_REQUIRED",
      "Для защищённых выходных файлов задайте пароль шифрования в настройках плана.",
    );
  }
  if (!canStart && startBlockers.length === 0) {
    addStartBlocker(
      "START_PREREQUISITES_UNAVAILABLE",
      "Проверьте актуальность плана и готовность узла выполнения.",
    );
  }
  const hasActions = plan.phases.some((phase) => phase.actions.length > 0);
  const saveOutputPassword = async () => {
    setOutputError("");
    try {
      await onSetOutputEncryptionPassword(outputPassword, outputConfirm);
      setOutputPassword("");
      setOutputConfirm("");
      setOutputPasswordAcknowledgement(operation);
    } catch (reason) {
      const code =
        typeof reason === "string" ? reason : "SECRET_OUTPUT_PASSWORD_INVALID";
      setOutputError(
        code === "SECRET_OUTPUT_PASSWORD_INVALID"
          ? "Пароли шифрования не совпадают или не подходят. Проверьте оба поля."
          : code,
      );
    }
  };
  return (
    <section className="installation-plan-content">
      <div className="installation-plan-scroll">
        <article className="card">
          <h2>Новый план установки</h2>
          <dl>
            <dt>Статус</dt>
            <dd>{planOperationStatusLabel(operation.status)}</dd>
            <dt>Ревизия проекта</dt>
            <dd>{plan.projectRevision}</dd>
            <dt>Узел выполнения</dt>
            <dd>{plan.executionNodeId}</dd>
            <dt>Истекает</dt>
            <dd>{plan.expiresAt}</dd>
          </dl>
        </article>
        {(operation.error || run?.error) && (
          <article
            className="card installation-plan-errors"
            role="alert"
            tabIndex={-1}
            ref={errorsRef}
          >
            <h2>Ошибки плана</h2>
            <ul>
              {operation.error && (
                <li>
                  <code>{operation.error.code}</code> — {operation.error.message}
                </li>
              )}
              {run?.error && (
                <li>
                  <code>{run.error.code}</code> — {run.error.message}
                  {!!run.error.diagnosticCodes?.length && (
                    <span> Диагностика Core: {run.error.diagnosticCodes.join(", ")}</span>
                  )}
                </li>
              )}
            </ul>
          </article>
        )}
        {!currentPlan && (
          <article className="card">
            <p role="status">
              Этот план нельзя использовать для текущего состояния проекта.
              Сохраните или отмените черновик и сформируйте свежий план.
            </p>
            {state?.status === "READY_TO_PLAN" && (
              <>
              {orderError && <p className="error" role="alert">{orderError}</p>}
              <button onClick={onCreatePlan} disabled={busy}>
                Сформировать свежий план
              </button>
              </>
            )}
          </article>
        )}
        {plan.findings && plan.findings.length > 0 && (
          <article className="card">
            <h2>Замечания</h2>
            <ul className="safe-findings">
              {plan.findings.map((item, index) => (
                <li key={`${item.code}:${index}`}>
                  <code>{item.code}</code>{" "}
                  {planFindingMessage(item.safeMessage)}
                </li>
              ))}
            </ul>
          </article>
        )}
        {outputRequired && (
          <details
            className="card secret-output-setup"
            open={!outputPasswordPresent}
          >
            <summary>
              Защищённые выходные файлы
              {outputPasswordPresent
                ? " · пароль задан"
                : " · требуется пароль"}
            </summary>
            <div className="secret-output-details">
              <p>
                Чувствительные результаты будут зашифрованы на этом компьютере.
                Пароль не отправляется на узел выполнения и хранится только в
                памяти сеанса.
              </p>
              {!outputPasswordPresent && (
                <>
                  <label>
                    Пароль шифрования
                    <input
                      type="password"
                      value={outputPassword}
                      onChange={(event) =>
                        setOutputPassword(event.target.value)
                      }
                      disabled={busy}
                      autoComplete="new-password"
                    />
                  </label>
                  <label>
                    Повторите пароль
                    <input
                      type="password"
                      value={outputConfirm}
                      onChange={(event) => setOutputConfirm(event.target.value)}
                      disabled={busy}
                      autoComplete="new-password"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={saveOutputPassword}
                    disabled={busy || !outputPassword || !outputConfirm}
                  >
                    Сохранить пароль в сеансе
                  </button>
                </>
              )}
              <p>
                Файлы сохраняются в каталоге secrets/&lt;ID развёртывания&gt;/
                текущего проекта.
              </p>
              {outputError && (
                <p className="field-error" role="alert">
                  {outputError}
                </p>
              )}
            </div>
          </details>
        )}
        <article className="card installation-plan-phases">
          <h2>Этапы плана</h2>
          {!hasActions && (
            <p role="status">
              В плане нет действий по развёртыванию сервисов. Проверьте состав и
              размещение сервисов в проекте.
            </p>
          )}
          {plan.phases.map((phase) => (
            <details
              className="plan-phase-card"
              key={phase.id}
              open={phase.order < 2}
            >
              <summary>
                <span className="plan-phase-number">{phase.order + 1}</span>
                <span className="plan-phase-title">
                  <b>
                    {phase.id === "pki"
                      ? "Сертификаты"
                      : phase.id === "apply"
                        ? "Применение"
                        : phase.id === "verify"
                          ? "Проверка и завершение"
                          : phase.id}
                  </b>
                  <small>
                    {phase.actions.length}{" "}
                    {phase.actions.length === 1 ? "действие" : "действий"}
                    {phase.actions.length > 0 &&
                      ` · ${[...new Set(phase.actions.flatMap((action) => action.targets))].join(", ") || "без целевых узлов"}`}
                  </small>
                </span>
                <span className="plan-phase-state">
                  {plan.status !== "EXECUTABLE"
                    ? "Есть замечания"
                    : plan.approved
                      ? "Готово к выполнению"
                      : "Ожидает одобрения"}
                </span>
              </summary>
              <div className="plan-phase-actions">
                {phase.actions
                  .slice(
                    0,
                    expandedActions[phase.id]
                      ? phase.actions.length
                      : Math.min(3, phase.actions.length),
                  )
                  .map((action, index) => (
                    <div className="plan-action-row" key={action.id}>
                      <span className="plan-action-number">{index + 1}</span>
                      <span className="plan-action-description">
                        <b>{action.summary}</b>
                        {action.serviceDeployment && (
                          <small>
                            Развёртывание: {action.serviceDeployment}
                          </small>
                        )}
                      </span>
                      <span className="plan-action-targets">
                        {action.targets.join(", ") || "без целевых серверов"}
                      </span>
                      <span className="plan-action-impact">
                        {action.mutating ? "Инфраструктура" : "Проверка"}
                      </span>
                    </div>
                  ))}
                {phase.actions.length > 3 && (
                  <button
                    type="button"
                    className="link plan-show-more"
                    aria-expanded={!!expandedActions[phase.id]}
                    onClick={() =>
                      setExpandedActions((current) => ({
                        ...current,
                        [phase.id]: !current[phase.id],
                      }))
                    }
                  >
                    {expandedActions[phase.id]
                      ? "Скрыть дополнительные действия"
                      : `Показать ещё ${phase.actions.length - 3} действий`}
                  </button>
                )}
              </div>
            </details>
          ))}
        </article>
        {plan.status === "EXECUTABLE" && !plan.approved && (
          <article className="card">
            <h2>Подтверждение</h2>
            {plan.acknowledgements.map((item) => (
              <label className="acknowledgement" key={item.code}>
                <input
                  type="checkbox"
                  checked={acknowledged.includes(item.code)}
                  onChange={(event) =>
                    setAcknowledged((current) =>
                      event.target.checked
                        ? [...current, item.code]
                        : current.filter((code) => code !== item.code),
                    )
                  }
                />{" "}
                <span>
                  <b>{item.code}</b>
                  <br />
                  {item.summary}
                </span>
              </label>
            ))}
          </article>
        )}
      </div>
      {plan.status === "EXECUTABLE" && !plan.approved && (
        <footer
          className="installation-plan-actions"
          aria-label="Подтверждение плана"
        >
          <span className="muted" role="status">
            {canApprove
              ? "План проверен и готов к одобрению."
              : "Отметьте обязательные подтверждения, чтобы одобрить план."}
          </span>
          <button
            type="button"
            onClick={() => onApprovePlan(plan.id, requiredCodes)}
            disabled={busy || !canApprove}
          >
            Одобрить план
          </button>
        </footer>
      )}
      {plan.approved && (
        <StartApproval
          plan={plan}
          busy={busy}
          canStart={canStart}
          onStart={onStart}
          credentialStatus={credentialStatus}
          outputReady={outputReady}
          startBlockers={startBlockers}
          runActive={["STARTING", "RUNNING", "CANCELLING"].includes(
            run?.run?.state || "",
          )}
        />
      )}
    </section>
  );
}

function StartApproval({
  plan,
  busy,
  canStart,
  onStart,
  credentialStatus,
  outputReady,
  startBlockers,
  runActive,
}: {
  plan: NonNullable<InstallationPlanOperation["plan"]>;
  busy: boolean;
  canStart: boolean;
  onStart: (planId: string) => void;
  credentialStatus: SessionCredentialStatus | null;
  outputReady: boolean;
  startBlockers: Array<{ code: string; message: string }>;
  runActive: boolean;
}) {
  const required = plan.pkiStorePasswordRequired;
  const present = credentialStatus?.pkiStorePasswordStatus === "PRESENT";
  return (
    <footer
      className="installation-plan-actions"
      aria-label="Действия с планом"
    >
      <div className="installation-start-gate">
        <span className="muted" role="status">
          {runActive
            ? "Выполнение этого плана уже запущено."
            : canStart && (!required || present) && outputReady
              ? "Одобренный план готов к запуску."
              : "Запуск пока недоступен. Устраните причины ниже:"}
        </span>
        {!runActive && startBlockers.length > 0 && (
          <ul className="safe-findings" aria-label="Причины недоступности запуска">
            {startBlockers.map((item, index) => (
              <li key={`${item.code}:${index}`}>
                <code>{item.code}</code> {item.message}
              </li>
            ))}
          </ul>
        )}
      </div>
      <button
        type="button"
        className="primary"
        onClick={() => onStart(plan.id)}
        disabled={
          busy ||
          !canStart ||
          (required && !present) ||
          !outputReady ||
          runActive
        }
      >
        Начать выполнение
      </button>
    </footer>
  );
}

function ExecutionStage({
  run,
  plan,
  progress,
  events,
  busy,
  onCancel,
  onOpenPendingOutputs,
}: {
  run?: InstallationRunOperation;
  plan?: InstallationPlanView;
  progress?: RunProgress;
  events: InstallationEventView[];
  busy: boolean;
  onCancel: (runId: string) => void;
  onOpenPendingOutputs: () => void;
}) {
  const [selectedSequence, setSelectedSequence] = useState<number>();
  const eventScrollRef = useRef<HTMLDivElement>(null);
  const visibleEvents = events.slice(-executionEventWindowSize);
  const selectedEvent =
    events.find((event) => event.sequence === selectedSequence) ||
    events.at(-1);
  const outputBusy =
    run?.error?.code === "OUTPUT_BUSY" ||
    events.some(
      (event) => executionDiagnosticCode(event.safeMessage) === "OUTPUT_BUSY",
    );
  useEffect(() => {
    setSelectedSequence(undefined);
  }, [run?.run?.runId]);
  useEffect(() => {
    const scrollContainer = eventScrollRef.current;
    if (scrollContainer)
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
  }, [events.length]);
  if (!run?.run)
    return (
      <article className="card installation-empty">
        <h2>Выполнение</h2>
        {run?.error ? (
          <p className="field-error" role="alert">
            Запуск не начался: <code>{run.error.code}</code> {run.error.message}
            {!!run.error.diagnosticCodes?.length && (
              <> Диагностика Core: {run.error.diagnosticCodes.join(", ")}</>
            )}
          </p>
        ) : (
          <p>В этом сеансе запуск ещё не начат.</p>
        )}
        {outputBusy && (
          <OutputBusyNotice onOpenPendingOutputs={onOpenPendingOutputs} />
        )}
      </article>
    );
  const display = installationDisplay(undefined, run, progress);
  const currentAction = plan?.phases
    .flatMap((phase) => phase.actions)
    .find((action) => action.id === progress?.activeActionId);
  const lastTask = [...events]
    .reverse()
    .find((event) => event.eventType === "TASK_COMPLETED" && event.task?.name);
  return (
    <section className="execution-stage-content">
      <article className="card execution-overview">
        {outputBusy && (
          <OutputBusyNotice onOpenPendingOutputs={onOpenPendingOutputs} />
        )}
        <div className="installation-stage-heading">
          <div>
            <h2>{display.label}</h2>
            <p>
              Запуск: {run.run.runId} · {runStatusLabel(run.run.state)}
            </p>
          </div>
          {["STARTING", "RUNNING", "CANCELLING"].includes(run.run.state) && (
            <button
              className="outline"
              disabled={busy}
              onClick={() => onCancel(run.run!.runId)}
            >
              Отменить выполнение
            </button>
          )}
        </div>
        {display.percent !== undefined && progress && (
          <div className="installation-progress">
            <div>
              <span>
                {progress.completedActionIds.length} из{" "}
                {progress.actionIds.length} действий плана подтверждены
              </span>
              <strong>{display.percent}%</strong>
            </div>
            <progress
              max={100}
              value={display.percent}
              aria-label="Прогресс подтверждённых действий плана"
            />
          </div>
        )}
        {display.percent === undefined && (
          <p className="installation-progress-unavailable">
            Точный процент недоступен: нет полного подтверждённого потока
            действий плана.
          </p>
        )}
        <p className="installation-current-action">
          {currentAction ? (
            <>
              Текущее действие: <b>{currentAction.summary}</b> ·{" "}
              {currentAction.targets.join(", ") || "без целевых серверов"}
            </>
          ) : (
            "Активное действие пока не подтверждено."
          )}
        </p>
        {lastTask && (
          <p className="installation-current-task">
            Последняя завершённая задача: {taskNameWithoutRole(lastTask)}{" "}
            {lastTask.host ? `· ${lastTask.host}` : ""} ·{" "}
            {eventStatusLabel(lastTask.status)}
          </p>
        )}
      </article>
      <div className="execution-event-workspace">
        <article className="card execution-event-table-card">
          <div className="execution-event-title">
            <h2>События выполнения</h2>
            <span>
              {events.length > executionEventWindowSize
                ? `Показаны последние ${executionEventWindowSize}; всего ${events.length}`
                : `Всего событий: ${events.length}`}
            </span>
          </div>
          {events.length === 0 ? (
            <p>События ещё не получены.</p>
          ) : (
            <>
              <div
                className="execution-event-table-scroll"
                ref={eventScrollRef}
              >
                <table className="execution-event-table">
                  <thead>
                    <tr>
                      <th scope="col">Время</th>
                      <th scope="col">Событие / задача</th>
                      <th scope="col">Развёртывание</th>
                      <th scope="col">Узел</th>
                      <th scope="col">Результат</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleEvents.map((event) => (
                      <tr
                        key={`${event.runId}-${event.sequence}`}
                        className={
                          selectedEvent?.sequence === event.sequence
                            ? "is-selected"
                            : ""
                        }
                      >
                        <td>
                          <time dateTime={event.timestamp || undefined}>
                            {eventTimestampLabel(event.timestamp)}
                          </time>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="execution-event-select"
                            aria-pressed={
                              selectedEvent?.sequence === event.sequence
                            }
                            onClick={() => setSelectedSequence(event.sequence)}
                          >
                            {taskNameWithoutRole(event) ||
                              eventMessageLabel(event.safeMessage) ||
                              event.eventType}
                          </button>
                          <small>{eventMessageLabel(event.safeMessage)}</small>
                        </td>
                        <td>{event.serviceDeployment || "—"}</td>
                        <td>{event.host || "—"}</td>
                        <td>{eventStatusLabel(event.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </article>
        <EventDetails event={selectedEvent} />
      </div>
    </section>
  );
}

function ResultStage({
  run,
  plan,
  progress,
  events,
  secretOutputPackages,
  outputDelivery,
  onRefreshSecretOutputs,
  onOpenPendingOutputs,
  onDeliverSecretOutput,
}: {
  run?: InstallationRunOperation;
  plan?: InstallationPlanView;
  progress?: RunProgress;
  events: InstallationEventView[];
  secretOutputPackages?: SecretOutputPackagesOperation;
  outputDelivery?: SecretOutputDeliveryOperation;
  onRefreshSecretOutputs: () => void;
  onOpenPendingOutputs: () => void;
  onDeliverSecretOutput: (packageId: string) => void;
}) {
  const terminal =
    !!run?.run &&
    ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(run.run.state);
  const outputBusy =
    run?.error?.code === "OUTPUT_BUSY" ||
    events.some(
      (event) => executionDiagnosticCode(event.safeMessage) === "OUTPUT_BUSY",
    );
  const actions = plan?.phases.flatMap((phase) => phase.actions) || [];
  return (
    <section className="installation-stage-content">
      <article className="card">
        <h2>Результат</h2>
        {!terminal ? (
          <p role="status">
            {run?.run
              ? "Выполнение продолжается. Итог ещё не определён; потеря связи с наблюдателем не означает ошибку."
              : "Нет завершённого запуска в текущем сеансе."}
          </p>
        ) : (
          <>
            <p
              role="status"
              className={
                run?.run?.state === "SUCCEEDED" ? "success" : "field-error"
              }
            >
              {runStatusLabel(run!.run!.state)} · запуск {run!.run!.runId}
            </p>
            {actions.length > 0 && (
              <div
                className="action-result-table"
                role="region"
                aria-label="Итог по действиям плана"
                tabIndex={0}
              >
                <table>
                  <thead>
                    <tr>
                      <th>Действие плана</th>
                      <th>Развёртывание</th>
                      <th>Серверы</th>
                      <th>Подтверждённый исход</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actions.map((action) => (
                      <tr key={action.id}>
                        <td>{action.summary}</td>
                        <td>{action.serviceDeployment || "—"}</td>
                        <td>{action.targets.join(", ") || "—"}</td>
                        <td>
                          {actionResultLabel(
                            action.id,
                            run!.run!.state,
                            progress,
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!actions.length && (
              <p>
                Подробный план действий для этого запуска недоступен. Общий итог
                получен от узла выполнения.
              </p>
            )}
          </>
        )}
        {outputBusy && (
          <OutputBusyNotice onOpenPendingOutputs={onOpenPendingOutputs} />
        )}
        <h3>Защищённые выходные файлы</h3>
        <p>
          Здесь отображается только состояние доставки. Содержимое секретов в
          интерфейс не передаётся.
        </p>
        <button className="outline" onClick={onRefreshSecretOutputs}>
          Проверить ожидающие файлы
        </button>
        {secretOutputPackages?.error && (
          <p className="field-error" role="alert">
            {secretOutputPackages.error.message}
          </p>
        )}
        {outputDelivery && (
          <p
            role={
              outputDelivery.status === "UNAVAILABLE" ? "alert" : "status"
            }
            className={
              outputDelivery.status === "DELIVERED"
                ? "success"
                : outputDelivery.status === "UNAVAILABLE"
                  ? "field-error"
                  : "muted"
            }
          >
            {outputDelivery.status === "DELIVERED"
              ? `Зашифрованные файлы сохранены: ${outputDelivery.directory}`
              : outputDelivery.error?.message ||
                outputDeliveryStatusLabel(outputDelivery.status)}
            {outputDelivery.stagingPath
              ? ` Временная папка сохранена: ${outputDelivery.stagingPath}`
              : ""}
          </p>
        )}
        {secretOutputPackages?.packages?.map((item) => (
          <div className="plan-action-row" key={item.packageId}>
            <b>Защищённый пакет · {item.deploymentId}</b>
            <span>
              Состояние: {outputPackageStateLabel(item.state)}; файлов:{" "}
              {item.entries.length}
            </span>
            <small>Запуск: {item.sourceRunId} · Поколение: {item.generation}</small>
            <button onClick={() => onDeliverSecretOutput(item.packageId)}>
              Получить и сохранить зашифрованно
            </button>
          </div>
        ))}
      </article>
      <EventList events={events} />
    </section>
  );
}

function OutputBusyNotice({
  onOpenPendingOutputs,
}: {
  onOpenPendingOutputs: () => void;
}) {
  return (
    <div className="notice execution-output-busy" role="alert">
      <strong>Запуск остановлен до выполнения задач</strong>
      <p>
        Пакет защищённых выходных файлов занят: он может ожидать получения после
        предыдущего запуска или подтверждения очистки узла. Текущий запуск
        остановлен до задач Ansible, чтобы не перезаписать файлы; план не
        применён.
      </p>
      <p>
        В списке проверьте состояние и ID исходного запуска: наличие файлов от
        другого запуска не снимает блокировку. Не удаляйте файлы на узле
        вручную.
      </p>
      <button className="outline" onClick={onOpenPendingOutputs}>
        Проверить и получить файлы
      </button>
      <small>Код диагностики: OUTPUT_BUSY</small>
    </div>
  );
}

function executionDiagnosticCode(message: string): string | undefined {
  return message.match(/\bdiagnostic:\s*([A-Z][A-Z0-9_]{2,79})\b/)?.[1];
}

function eventStatusLabel(status: string): string {
  switch (status) {
    case "PENDING":
      return "ожидает";
    case "SUCCESS":
      return "успешно";
    case "CHANGED":
      return "изменено";
    case "SKIPPED":
      return "пропущено";
    case "FAILED":
      return "ошибка";
    case "RUNNING":
      return "выполняется";
    case "CANCELLED":
      return "отменено";
    case "INTERRUPTED":
      return "прервано";
    default:
      return "ожидает";
  }
}

function eventTypeLabel(eventType: string): string {
  const labels: Record<string, string> = {
    RUN_STARTED: "Запуск начат",
    PHASE_STARTED: "Этап начат",
    ACTION_STARTED: "Действие начато",
    TASK_STARTED: "Задача начата",
    TASK_COMPLETED: "Задача завершена",
    ACTION_COMPLETED: "Действие завершено",
    PHASE_COMPLETED: "Этап завершён",
    RUN_COMPLETED: "Запуск завершён",
    DIAGNOSTIC: "Диагностика",
  };
  return labels[eventType] || eventType;
}

function eventMessageLabel(message: string): string {
  if (executionDiagnosticCode(message) === "OUTPUT_BUSY") {
    return "Пакет защищённых выходных файлов занят; план остановлен до задач Ansible";
  }
  const labels: Record<string, string> = {
    "Detached controller accepted": "Контроллер принят",
    "Fixed Core controller started": "Контроллер Core запущен",
    "Execution controller is running": "Контроллер выполнения работает",
    "Trusted operation started": "Доверенная операция начата",
    "Ansible task started": "Задача Ansible начата",
    "Ansible task completed": "Задача Ansible завершена",
    "Ansible operation failed": "Операция Ansible завершилась ошибкой",
    "Detailed task observability was truncated":
      "Подробная запись событий задач ограничена",
    "Detailed task observability was degraded":
      "Подробная запись событий задач неполна",
  };
  return labels[message] || message;
}

function EventDetails({ event }: { event?: InstallationEventView }) {
  return (
    <article className="card execution-event-details">
      <h2>Детали события</h2>
      {!event ? (
        <p>Выберите событие, чтобы посмотреть подробности.</p>
      ) : (
        <>
          <strong>
            {eventTypeLabel(event.eventType)} · {eventStatusLabel(event.status)}
          </strong>
          <p>{eventMessageLabel(event.safeMessage)}</p>
          <dl>
            <dt>Время</dt>
            <dd>{eventTimestampLabel(event.timestamp)}</dd>
            <dt>Событие</dt>
            <dd>{eventTypeLabel(event.eventType)}</dd>
            <dt>Этап</dt>
            <dd>{event.phaseId || "—"}</dd>
            <dt>Действие</dt>
            <dd>{event.actionId || "—"}</dd>
            <dt>Развёртывание</dt>
            <dd>{event.serviceDeployment || "—"}</dd>
            <dt>Узел</dt>
            <dd>{event.host || "—"}</dd>
            <dt>Роль задачи</dt>
            <dd>{event.task?.role || "—"}</dd>
            <dt>Задача</dt>
            <dd>{taskNameWithoutRole(event) || "—"}</dd>
            <dt>ID задачи</dt>
            <dd>{event.task?.uuid || "—"}</dd>
            <dt>Длительность</dt>
            <dd>
              {event.elapsedMilliseconds === undefined
                ? "—"
                : `${event.elapsedMilliseconds} мс`}
            </dd>
            <dt>Ошибка</dt>
            <dd>
              {[event.errorCode, event.errorSummary]
                .filter(Boolean)
                .join(" · ") || "—"}
            </dd>
          </dl>
        </>
      )}
    </article>
  );
}

function EventList({ events }: { events: InstallationEventView[] }) {
  return (
    <article className="card installation-event-card">
      <h2>Подробные события</h2>
      {events.length === 0 ? (
        <p>События ещё не получены.</p>
      ) : (
        <ol className="installation-events">
          {events.map((event) => (
            <li key={event.sequence}>
              <span className="installation-event-sequence">
                {event.sequence}
              </span>
              <span>
                <b>
                  {taskNameWithoutRole(event) ||
                    eventTypeLabel(event.eventType)}
                </b>
                <small>{eventMessageLabel(event.safeMessage)}</small>
                <small>
                  <time
                    className="installation-event-time"
                    dateTime={event.timestamp || undefined}
                    title={event.timestamp || undefined}
                  >
                    {eventTimestampLabel(event.timestamp)}
                  </time>
                  {event.host ? ` · ${event.host}` : ""}
                  {event.serviceDeployment
                    ? ` · ${event.serviceDeployment}`
                    : ""}
                  {` · ${eventStatusLabel(event.status)}`}
                </small>
              </span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

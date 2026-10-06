import { useState } from "react";
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

type InstallationTab = "summary" | "plan" | "execution" | "result";

const tabLabels: Array<{ id: InstallationTab; label: string }> = [
  { id: "summary", label: "Сводка" },
  { id: "plan", label: "План" },
  { id: "execution", label: "Выполнение" },
  { id: "result", label: "Результат" },
];

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
  onOpenCertificates = () => {},
  plan,
  busy,
  onCreatePlan,
  onApprovePlan,
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
  onOpenCertificates?: () => void;
  plan?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: () => void;
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
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
  const prerequisites = state?.prerequisites || [];
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
          {presentation.label}
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
      <div className="workflow-strip" aria-label="Стадии установки">
        <div
          className={presentation.stage === "plan" ? "workflow-current" : ""}
        >
          1. План
        </div>
        <div
          className={
            presentation.stage === "execution" ? "workflow-current" : ""
          }
        >
          2. Выполнение
        </div>
        <div
          className={presentation.stage === "result" ? "workflow-current" : ""}
        >
          3. Результат
        </div>
      </div>
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
            <article className="card">
              <h2>Следующее действие</h2>
              {state?.status === "READY_TO_PLAN" ? (
                <>
                  <p>
                    Условия для нового плана выполнены. Проверка проекта не
                    заменяет построение нового плана установки.
                  </p>
                  <button onClick={onCreatePlan} disabled={busy}>
                    Сформировать свежий план
                  </button>
                </>
              ) : (
                <ul className="safe-findings">
                  {prerequisites.map((item) => (
                    <li key={item.code}>
                      <code>{item.code}</code> {item.safeMessage}
                    </li>
                  ))}
                </ul>
              )}
            </article>
            <article className="card installation-summary-plan">
              <div className="installation-summary-plan-heading">
                <div>
                  <h2>План установки</h2>
                  <p className="muted">
                    {plan?.plan
                      ? `Для ревизии ${plan.plan.projectRevision}`
                      : "Свежий план появится после его построения."}
                  </p>
                </div>
                <span className="readonly">
                  {plan
                    ? planOperationStatusLabel(plan.status)
                    : "План ещё не сформирован"}
                </span>
              </div>
              {plan?.plan ? (
                <div className="installation-summary-plan-actions">
                  {plan.plan.phases.flatMap((phase) =>
                    phase.actions.map((action) => (
                      <div
                        className="installation-summary-plan-action"
                        key={action.id}
                      >
                        <b>{action.summary}</b>
                        <span>
                          {action.serviceDeployment
                            ? `Развёртывание: ${action.serviceDeployment} · `
                            : ""}
                          {action.targets.join(", ") || "без целевых серверов"}
                        </span>
                      </div>
                    )),
                  )}
                  {plan.plan.phases.every(
                    (phase) => phase.actions.length === 0,
                  ) && <p>В плане пока нет действий.</p>}
                </div>
              ) : (
                <p className="muted">
                  Построение плана проверит сохранённую конфигурацию, выбранный
                  узел выполнения и целевые серверы.
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
            onCreatePlan={onCreatePlan}
            onApprovePlan={onApprovePlan}
            onStart={onStart}
            credentialStatus={credentialStatus}
            onOpenCertificates={onOpenCertificates}
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
  onApprovePlan,
  onStart,
  credentialStatus,
  onOpenCertificates,
  onSetOutputEncryptionPassword,
}: {
  state?: InstallationState;
  draftActive: boolean;
  operation?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: () => void;
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
  onStart: (planId: string) => void;
  credentialStatus: SessionCredentialStatus | null;
  onOpenCertificates: () => void;
  onSetOutputEncryptionPassword: (
    password: string,
    confirm: string,
  ) => Promise<void>;
}) {
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [outputPasswordAcknowledgement, setOutputPasswordAcknowledgement] =
    useState<InstallationPlanOperation>();
  const outputPasswordPresent =
    !!operation?.plan?.secretOutputEncryptionPasswordPresent ||
    (!!operation && outputPasswordAcknowledgement === operation);
  const [outputPassword, setOutputPassword] = useState("");
  const [outputConfirm, setOutputConfirm] = useState("");
  const [outputError, setOutputError] = useState("");
  const plan = operation?.plan;
  if (!plan) {
    return (
      <article className="card installation-empty">
        <h2>План</h2>
        <p>{operation?.error?.message || "Свежий план ещё не создан."}</p>
        <button onClick={onCreatePlan} disabled={busy}>
          Сформировать свежий план
        </button>
      </article>
    );
  }
  const requiredCodes = plan.acknowledgements.map((item) => item.code);
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
    state?.status === "PLAN_APPROVED" &&
    state.plan.status === "PLAN_APPROVED" &&
    plan.status === "EXECUTABLE" &&
    plan.approved;
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
      {!currentPlan && (
        <article className="card">
          <p role="status">
            Этот план нельзя использовать для текущего состояния проекта.
            Сохраните или отмените черновик и сформируйте свежий план.
          </p>
          {state?.status === "READY_TO_PLAN" && (
            <button onClick={onCreatePlan} disabled={busy}>
              Сформировать свежий план
            </button>
          )}
        </article>
      )}
      {plan.findings && plan.findings.length > 0 && (
        <article className="card">
          <h2>Замечания</h2>
          <ul className="safe-findings">
            {plan.findings.map((item, index) => (
              <li key={`${item.code}:${index}`}>
                <code>{item.code}</code> {planFindingMessage(item.safeMessage)}
              </li>
            ))}
          </ul>
        </article>
      )}
      {outputRequired && (
        <article className="card secret-output-setup">
          <h2>Защищённые выходные файлы</h2>
          <p>
            Чувствительные результаты после выполнения будут зашифрованы на этом
            компьютере. Пароль не отправляется на узел выполнения и хранится
            только в памяти сеанса.
          </p>
          {outputPasswordPresent ? (
            <p className="success">
              Пароль шифрования задан для текущего сеанса.
            </p>
          ) : (
            <>
              <label>
                Пароль шифрования
                <input
                  type="password"
                  value={outputPassword}
                  onChange={(event) => setOutputPassword(event.target.value)}
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
        </article>
      )}
      <article className="card">
        <h2>Этапы плана</h2>
        {!hasActions && (
          <p role="status">
            В плане нет действий по развёртыванию сервисов. Проверьте состав и
            размещение сервисов в проекте.
          </p>
        )}
        {plan.phases.map((phase) => (
          <section className="plan-phase" key={phase.id}>
            <h3>
              {phase.order + 1}.{" "}
              {phase.id === "pki"
                ? "Сертификаты"
                : phase.id === "apply"
                  ? "Применение"
                  : phase.id === "verify"
                    ? "Проверка"
                    : phase.id}
            </h3>
            {phase.actions.map((action) => (
              <div className="plan-action-row" key={action.id}>
                <b>{action.summary}</b>
                {action.serviceDeployment && (
                  <span>Развёртывание: {action.serviceDeployment}</span>
                )}
                <span>
                  {action.targets.join(", ") || "без целевых серверов"}
                </span>
                <small>
                  {action.mutating ? "изменяет инфраструктуру" : "проверка"}
                  {action.dependsOn.length
                    ? ` · после ${action.dependsOn.join(", ")}`
                    : ""}
                </small>
              </div>
            ))}
          </section>
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
          <p>
            <button
              onClick={() => onApprovePlan(plan.id, requiredCodes)}
              disabled={busy || !canApprove}
            >
              Одобрить план
            </button>
          </p>
        </article>
      )}
      {plan.approved && (
        <StartApproval
          plan={plan}
          busy={busy}
          canStart={canStart}
          onStart={onStart}
          credentialStatus={credentialStatus}
          onOpenCertificates={onOpenCertificates}
          outputReady={outputReady}
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
  onOpenCertificates,
  outputReady,
}: {
  plan: NonNullable<InstallationPlanOperation["plan"]>;
  busy: boolean;
  canStart: boolean;
  onStart: (planId: string) => void;
  credentialStatus: SessionCredentialStatus | null;
  onOpenCertificates: () => void;
  outputReady: boolean;
}) {
  const required = plan.pkiStorePasswordRequired;
  const present = credentialStatus?.pkiStorePasswordStatus === "PRESENT";
  return (
    <article className="card">
      <h2>План одобрен</h2>
      <p>Запуск создаёт один идентификатор выполнения на выбранном узле.</p>
      {required && (
        <>
          <p role="status" className="muted">
            Пароль Java-хранилищ PKCS#12:{" "}
            {present ? "задан в текущем сеансе" : "не задан"}.
          </p>
          <button
            type="button"
            className="outline"
            onClick={onOpenCertificates}
          >
            Открыть «Сертификаты»
          </button>
        </>
      )}
      <button
        onClick={() => onStart(plan.id)}
        disabled={busy || !canStart || (required && !present) || !outputReady}
      >
        Начать выполнение
      </button>
    </article>
  );
}

function ExecutionStage({
  run,
  plan,
  progress,
  events,
  busy,
  onCancel,
}: {
  run?: InstallationRunOperation;
  plan?: InstallationPlanView;
  progress?: RunProgress;
  events: InstallationEventView[];
  busy: boolean;
  onCancel: (runId: string) => void;
}) {
  if (!run?.run)
    return (
      <article className="card installation-empty">
        <h2>Выполнение</h2>
        {run?.error ? (
          <p className="field-error" role="alert">
            Запуск не начался: <code>{run.error.code}</code> {run.error.message}
          </p>
        ) : (
          <p>В этом сеансе запуск ещё не начат.</p>
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
    <section className="installation-stage-content">
      <article className="card">
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
            Последняя завершённая задача: {lastTask.task?.name}{" "}
            {lastTask.host ? `· ${lastTask.host}` : ""} ·{" "}
            {eventStatusLabel(lastTask.status)}
          </p>
        )}
      </article>
      <EventList events={events} />
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
  onDeliverSecretOutput,
}: {
  run?: InstallationRunOperation;
  plan?: InstallationPlanView;
  progress?: RunProgress;
  events: InstallationEventView[];
  secretOutputPackages?: SecretOutputPackagesOperation;
  outputDelivery?: SecretOutputDeliveryOperation;
  onRefreshSecretOutputs: () => void;
  onDeliverSecretOutput: (packageId: string) => void;
}) {
  const terminal =
    !!run?.run &&
    ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(run.run.state);
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
            role="status"
            className={
              outputDelivery.status === "DELIVERED" ? "success" : "muted"
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
            <small>Запуск: {item.sourceRunId}</small>
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

function eventStatusLabel(status: string): string {
  switch (status) {
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
    default:
      return "ожидает";
  }
}

function eventTimestampLabel(timestamp: string): string {
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return "время неизвестно";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
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
                  {event.task?.name || event.safeMessage || event.eventType}
                </b>
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

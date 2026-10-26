import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type {
  InstallationEventView,
  InstallationPlanOperation,
  InstallationPlanRequest,
  InstallationPlanView,
  InstallationExecutionMode,
  InfrastructureVerificationView,
  InstallationRunOperation,
  InstallationState,
  SessionCredentialStatus,
  SecretOutputPackagesOperation,
  SecretOutputDeliveryOperation,
} from "./backend";
import {
  actionResultLabel,
  installationDisplay,
  installationActionRows,
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

function planActionLabel(action: {
  type: string;
  summary: string;
  serviceDeployment?: string;
}): string {
  const deployment = action.serviceDeployment
    ? ` ${action.serviceDeployment}`
    : "";
  switch (action.type) {
    case "PKI_APPLY":
      return "Подготовить утверждённые сертификаты";
    case "SERVICE_APPLY":
      return `Установить сервис${deployment}`;
    case "SERVICE_VERIFY":
      return `Проверить сервис${deployment}`;
    case "SERVICE_CLEAR":
      return `Очистить установленный сервис${deployment}`;
    case "APPLICATION_LIBRARIES_APPLY":
      return "Установить библиотеки приложений";
    case "APPLICATION_LIBRARIES_VERIFY":
      return "Проверить библиотеки приложений";
    case "APPLICATION_LIBRARIES_POST_INSTALL":
      return "Выполнить действия после установки";
    default:
      return action.summary;
  }
}

export type ServicePriorityInput = {
  serviceType: string;
  priority: number | null;
};

export type ServiceDeploymentInput = {
  deploymentId: string;
  serviceType: string;
};

export type LibraryPriorityInput = {
  libraryName: string;
  priority: number | null;
};
export type LibraryDeploymentInput = {
  deploymentId: string;
  libraryRef: string;
};

export function libraryOrderFromPriorities(
  deployments: LibraryDeploymentInput[],
  priorities: LibraryPriorityInput[],
): { order: string[]; missingNames: string[] } {
  const byName = new Map(
    priorities.map((item, index) => [item.libraryName, { ...item, index }]),
  );
  const nameOf = (item: LibraryDeploymentInput) =>
    item.libraryRef.split("@", 1)[0];
  const missingNames = [
    ...new Set(
      deployments
        .filter((item) => byName.get(nameOf(item))?.priority == null)
        .map(nameOf),
    ),
  ].sort();
  if (missingNames.length) return { order: [], missingNames };
  return {
    order: [...deployments]
      .sort((left, right) => {
        const a = byName.get(nameOf(left))!;
        const b = byName.get(nameOf(right))!;
        return (
          a.priority! - b.priority! ||
          a.index - b.index ||
          (left.deploymentId < right.deploymentId
            ? -1
            : left.deploymentId > right.deploymentId
              ? 1
              : 0)
        );
      })
      .map((item) => item.deploymentId),
    missingNames: [],
  };
}

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
    case "LOCAL_DELIVERED":
      return "Сохранён на инсталлере";
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
  infrastructureObservation,
  selectedExecutionMode,
  onExecutionModeChange,
  serviceDeployments = [],
  applicationVaultSources = {},
  onApplicationVaultSourcesChange,
  serviceExecutionPriorities = [],
  libraryDeployments = [],
  libraryExecutionPriorities = [],
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
  onCollectSecretOutputs = async () => {},
}: {
  state?: InstallationState;
  draftActive?: boolean;
  tab: InstallationTab;
  onTabChange: (tab: InstallationTab) => void;
  onOpenServers: () => void;
  plan?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: (
    deploymentOrder: string[],
    mode?: InstallationExecutionMode,
    skipInfrastructureVerify?: boolean,
    applicationLibraryOrder?: string[],
    skipApplicationLibraries?: string[],
  ) => void;
  infrastructureObservation?: InfrastructureVerificationView;
  selectedExecutionMode?: InstallationExecutionMode;
  onExecutionModeChange?: (mode: InstallationExecutionMode) => void;
  serviceDeployments?: ServiceDeploymentInput[];
  applicationVaultSources?: InstallationPlanRequest["applicationVaultSources"];
  onApplicationVaultSourcesChange?: (
    sources: InstallationPlanRequest["applicationVaultSources"],
  ) => void;
  serviceExecutionPriorities?: ServicePriorityInput[];
  libraryDeployments?: LibraryDeploymentInput[];
  libraryExecutionPriorities?: LibraryPriorityInput[];
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
  onCollectSecretOutputs?: () => Promise<void>;
}) {
  const [orderError, setOrderError] = useState("");
  const [skippedLibraries, setSkippedLibraries] = useState<string[]>([]);
  const selectionPlanId = useRef<string | undefined>(undefined);
  useEffect(() => setSkippedLibraries([]), [state?.project?.id]);
  useEffect(() => {
    if (selectionPlanId.current !== plan?.plan?.id) {
      selectionPlanId.current = plan?.plan?.id;
      setSkippedLibraries(plan?.plan?.skipApplicationLibraries || []);
    }
  }, [plan?.plan?.id, plan?.plan?.skipApplicationLibraries]);
  const [skipInfrastructureVerify, setSkipInfrastructureVerify] =
    useState(false);
  useEffect(() => setSkipInfrastructureVerify(false), [state?.project?.id]);
  const [localExecutionMode, setLocalExecutionMode] =
    useState<InstallationExecutionMode>("FULL_PROJECT");
  const executionMode = selectedExecutionMode || localExecutionMode;
  const setExecutionMode = (mode: InstallationExecutionMode) => {
    setSkipInfrastructureVerify(false);
    setSkippedLibraries([]);
    setLocalExecutionMode(mode);
    onExecutionModeChange?.(mode);
  };
  useEffect(() => {
    if (
      !selectedExecutionMode &&
      (plan?.plan?.executionMode === "FULL_PROJECT" ||
        plan?.plan?.executionMode === "APPLICATION_LIBRARIES_ONLY")
    )
      setLocalExecutionMode(plan.plan.executionMode);
  }, [plan?.plan?.id, plan?.plan?.executionMode, selectedExecutionMode]);
  const skipChanged =
    !!plan?.plan &&
    (!!plan.plan.skipInfrastructureVerify !== skipInfrastructureVerify ||
      JSON.stringify([...(plan.plan.skipApplicationLibraries || [])].sort()) !==
        JSON.stringify([...skippedLibraries].sort()));
  const scopeChanged =
    !!plan?.plan &&
    ((plan.plan.executionMode || "FULL_PROJECT") !== executionMode ||
      skipChanged);
  const deploymentOrder = useMemo(
    () =>
      deploymentOrderFromPriorities(
        serviceDeployments,
        serviceExecutionPriorities,
      ),
    [serviceDeployments, serviceExecutionPriorities],
  );
  const libraryOrder = useMemo(
    () =>
      libraryOrderFromPriorities(
        libraryDeployments,
        libraryExecutionPriorities,
      ),
    [libraryDeployments, libraryExecutionPriorities],
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
    if (libraryOrder.missingNames.length) {
      setOrderError(
        "Для библиотек " +
          libraryOrder.missingNames.join(", ") +
          " не задан приоритет в application.yml.",
      );
      return;
    }
    setOrderError("");
    const skip =
      executionMode === "APPLICATION_LIBRARIES_ONLY" &&
      skipInfrastructureVerify;
    if (skippedLibraries.length)
      onCreatePlan(
        deploymentOrder.order,
        executionMode,
        skip,
        libraryOrder.order,
        skippedLibraries,
      );
    else if (libraryOrder.order.length)
      onCreatePlan(
        deploymentOrder.order,
        executionMode,
        skip,
        libraryOrder.order,
      );
    else if (skip) onCreatePlan(deploymentOrder.order, executionMode, true);
    else onCreatePlan(deploymentOrder.order, executionMode);
  };
  const node = state?.executionNode;
  const runActive = ["STARTING", "RUNNING", "CANCELLING"].includes(
    run?.run?.state || "",
  );
  const displayedPlan: InstallationPlanOperation | undefined =
    runActive && runPlan ? { status: "PLAN_APPROVED", plan: runPlan } : plan;
  const presentation = installationDisplay(state, run, runProgress);
  const cachedObservation = (
    <>
      {!plan?.plan?.infrastructureVerification && infrastructureObservation && (
        <p role="status">
          Предыдущее наблюдение инфраструктуры: UNKNOWN
          {infrastructureObservation.observedAt
            ? ` · ${infrastructureObservation.observedAt}`
            : ""}
          . Для разрешения запуска нужен свежий план Core.
        </p>
      )}
    </>
  );
  const servicesControl = (
    <div aria-label="services">
      <div
        data-state={
          executionMode === "APPLICATION_LIBRARIES_ONLY"
            ? "excluded"
            : "included"
        }
        className={
          executionMode === "APPLICATION_LIBRARIES_ONLY" ? "muted" : undefined
        }
      >
        <label>
          <input
            type="checkbox"
            aria-label="Устанавливать инфраструктуру"
            checked={executionMode === "FULL_PROJECT"}
            disabled={busy || runActive}
            onChange={(event) =>
              setExecutionMode(
                event.target.checked
                  ? "FULL_PROJECT"
                  : "APPLICATION_LIBRARIES_ONLY",
              )
            }
          />
          Инфраструктура
        </label>
        <p>
          {executionMode === "FULL_PROJECT"
            ? "Полный цикл Apply → Verify инфраструктуры."
            : skipInfrastructureVerify
              ? "Infra Verify явно пропущен. Пользователь принимает риски запуска библиотек без проверки инфраструктуры."
              : "Установка инфраструктуры исключена. При отсутствии актуального Verify Core включит проверку инфраструктуры в этот план перед библиотеками."}
        </p>
      </div>
      {executionMode === "APPLICATION_LIBRARIES_ONLY" && (
        <label>
          <input
            type="checkbox"
            checked={skipInfrastructureVerify}
            disabled={busy || runActive}
            onChange={(event) =>
              setSkipInfrastructureVerify(event.target.checked)
            }
          />
          Пропустить проверку инфраструктуры — принимаю риски
        </label>
      )}
      {executionMode === "APPLICATION_LIBRARIES_ONLY" &&
        !skipInfrastructureVerify && (
          <p>
            Действия Apply инфраструктуры скрыты только в этом представлении.
            При одобрении Core сформирует точный план; если Verify отсутствует,
            он добавит его перед полным циклом библиотек.
          </p>
        )}
      {cachedObservation}
      {scopeChanged && (
        <p role="status">
          {skipChanged
            ? "Параметры пропуска изменены. Сформируйте свежий план перед одобрением."
            : "Состав запуска изменён. Актуальный план будет сформирован при одобрении перед запуском."}
        </p>
      )}
    </div>
  );
  const librariesControl =
    libraryDeployments.length > 0 ? (
      <div aria-label="Настройки библиотек">
        <div>
          <strong>Библиотеки</strong>
          <p>Полный цикл Apply → Verify.</p>
        </div>
        {executionMode === "FULL_PROJECT" &&
          libraryDeployments.length > 0 &&
          onApplicationVaultSourcesChange &&
          serviceDeployments
            .filter((service) => service.serviceType === "vault")
            .map((service) => (
              <label key={service.deploymentId}>
                Источник токена Vault для приложений · {service.deploymentId}
                <select
                  aria-label={"Источник токена Vault · " + service.deploymentId}
                  disabled={busy || runActive}
                  value={
                    applicationVaultSources[service.deploymentId] ||
                    "RUNTIME_INPUT"
                  }
                  onChange={(event) => {
                    const sources = { ...applicationVaultSources };
                    if (event.target.value === "CURRENT_RUN_BOOTSTRAP")
                      sources[service.deploymentId] = "CURRENT_RUN_BOOTSTRAP";
                    else delete sources[service.deploymentId];
                    onApplicationVaultSourcesChange(sources);
                  }}
                >
                  <option value="RUNTIME_INPUT">
                    Из секретов инфраструктурного Vault
                  </option>
                  <option value="CURRENT_RUN_BOOTSTRAP">
                    Из текущей установки Vault
                  </option>
                </select>
              </label>
            ))}
        {libraryDeployments.length > 0 && (
          <div aria-label="Выбор библиотек">
            <table>
              <thead>
                <tr>
                  <th>Библиотека</th>
                  <th>Установить</th>
                </tr>
              </thead>
              <tbody>
                {libraryDeployments.map((library) => (
                  <tr key={library.deploymentId}>
                    <td>{library.deploymentId}</td>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={
                          "Установить библиотеку " + library.deploymentId
                        }
                        checked={
                          !skippedLibraries.includes(library.deploymentId)
                        }
                        disabled={
                          busy ||
                          runActive ||
                          executionMode === "INFRASTRUCTURE_VERIFY_ONLY"
                        }
                        onChange={(event) =>
                          setSkippedLibraries((current) =>
                            !event.target.checked
                              ? [...current, library.deploymentId]
                              : current.filter(
                                  (id) => id !== library.deploymentId,
                                ),
                          )
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">
              Установка и проверка библиотек со снятым флажком пропускаются. Их
              подключения остаются доступны интеграциям устанавливаемых
              приложений.
            </p>
          </div>
        )}
      </div>
    ) : null;
  return (
    <section className="installation-page">
      {!!displayedPlan?.plan?.skipApplicationLibraries?.length && (
        <p role="status">
          Установка библиотек пропущена:{" "}
          {displayedPlan.plan.skipApplicationLibraries.join(", ")}. Необходимые
          интеграции сохраняются.
        </p>
      )}
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
              <h2>Состав запуска</h2>
              {servicesControl}
              {librariesControl}
              <div className="installation-summary-plan-heading">
                <div>
                  <h2>План установки</h2>
                  <div className="installation-summary-plan-meta">
                    <span>
                      <b>
                        {displayedPlan?.plan
                          ? displayedPlan.plan.phases.reduce(
                              (count, phase) => count + phase.actions.length,
                              0,
                            )
                          : 0}
                      </b>{" "}
                      действий
                    </span>
                    <span>
                      Ревизия: {displayedPlan?.plan?.projectRevision || "—"}
                    </span>
                    <span>
                      Статус:{" "}
                      {displayedPlan
                        ? runActive
                          ? "Выполняется"
                          : planOperationStatusLabel(displayedPlan.status)
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
              {displayedPlan?.plan ? (
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
                      {displayedPlan.plan.phases
                        .flatMap((phase) => phase.actions)
                        .map((action, index) => (
                          <tr key={action.id}>
                            <td>{index + 1}</td>
                            <td>{planActionLabel(action)}</td>
                            <td>
                              {action.targets.join(", ") || "без целевых узлов"}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  {displayedPlan.plan.phases.every(
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
          <>
            <PlanStage
              key={plan?.plan?.id || "no-plan"}
              servicesControl={servicesControl}
              librariesControl={librariesControl}
              scopeChanged={!runActive && scopeChanged}
              skipChanged={!runActive && skipChanged}
              infrastructureExcluded={
                executionMode === "APPLICATION_LIBRARIES_ONLY"
              }
              state={state}
              draftActive={draftActive}
              operation={
                ["STARTING", "RUNNING", "CANCELLING"].includes(
                  run?.run?.state || "",
                ) && runPlan
                  ? { status: "PLAN_APPROVED", plan: runPlan }
                  : plan
              }
              busy={
                busy ||
                ["STARTING", "RUNNING", "CANCELLING"].includes(
                  run?.run?.state || "",
                )
              }
              onCreatePlan={createPlan}
              orderError={orderError}
              onApprovePlan={onApprovePlan}
              approvalErrorAttempt={approvalErrorAttempt}
              onStart={onStart}
              run={run}
              credentialStatus={credentialStatus}
              onSetOutputEncryptionPassword={onSetOutputEncryptionPassword}
            />
          </>
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
            onOpenPendingOutputs={onRefreshSecretOutputs}
            onCollectSecretOutputs={onCollectSecretOutputs}
          />
        )}
      </div>
    </section>
  );
}

function PlanStage({
  servicesControl,
  librariesControl,
  scopeChanged,
  skipChanged,
  infrastructureExcluded,
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
  servicesControl: ReactNode;
  librariesControl: ReactNode;
  scopeChanged: boolean;
  skipChanged: boolean;
  infrastructureExcluded: boolean;
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
        {servicesControl}
        {librariesControl}
        <p>
          {operation?.error && (
            <>
              <code>{operation.error.code}</code> —{" "}
            </>
          )}
          {operation?.error?.message || "Свежий план ещё не создан."}
          {!!operation?.error?.diagnosticCodes?.length && (
            <> Диагностика Core: {operation.error.diagnosticCodes.join(", ")}</>
          )}
        </p>
        {orderError && (
          <p className="error" role="alert">
            {orderError}
          </p>
        )}
        <button onClick={onCreatePlan} disabled={busy}>
          {busy ? "Подготовка образов и плана…" : "Сформировать свежий план"}
        </button>
      </article>
    );
  }
  const requiredCodes = plan.acknowledgements.map((item) => item.code);
  const required = !!plan.pkiStorePasswordRequired;
  const present = credentialStatus?.pkiStorePasswordStatus === "PRESENT";
  const outputRequired = !!plan.secretOutputEncryptionRequired;
  const outputReady = !outputRequired || outputPasswordPresent;
  const displayedPhases =
    infrastructureExcluded && scopeChanged
      ? plan.phases.map((phase) =>
          phase.id === "services"
            ? {
                ...phase,
                actions: phase.actions.filter(
                  (action) => action.type !== "SERVICE_APPLY",
                ),
              }
            : phase,
        )
      : plan.phases;
  const runActive = ["STARTING", "RUNNING", "CANCELLING"].includes(
    run?.run?.state || "",
  );
  const currentPlan =
    !skipChanged &&
    !runActive &&
    !draftActive &&
    !state?.project?.hasUnsavedChanges &&
    state?.executionNode.status === "READY" &&
    state?.project?.revision === plan.projectRevision &&
    state?.plan.planId === plan.id;
  const canApprove =
    currentPlan &&
    (scopeChanged || state?.status === "PLAN_REVIEW") &&
    (scopeChanged || state?.plan.status === "PLAN_REVIEW") &&
    plan.status === "EXECUTABLE" &&
    (scopeChanged || !plan.approved) &&
    requiredCodes.every((code) => acknowledged.includes(code)) &&
    outputReady;
  const canStart =
    !scopeChanged &&
    currentPlan &&
    !["STARTING", "RUNNING", "CANCELLING"].includes(run?.run?.state || "") &&
    state?.status === "PLAN_APPROVED" &&
    state.plan.status === "PLAN_APPROVED" &&
    plan.status === "EXECUTABLE" &&
    plan.approved;
  const startBlockers: Array<{ code: string; message: string }> = [];
  const addStartBlocker = (code: string, message: string) => {
    if (
      !startBlockers.some(
        (item) => item.code === code && item.message === message,
      )
    )
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
  const hasActions = displayedPhases.some((phase) => phase.actions.length > 0);
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
          {plan.skipInfrastructureVerify && (
            <p role="alert">
              Проверка инфраструктуры явно пропущена. Риски приняты
              пользователем; успешный Verify не подтверждён этим запуском.
            </p>
          )}
          {plan.executionMode === "APPLICATION_LIBRARIES_ONLY" &&
            !plan.skipInfrastructureVerify &&
            plan.infrastructureVerification && (
              <section aria-label="Проверка инфраструктуры">
                <h3>
                  {plan.infrastructureVerification.status === "PASS"
                    ? "Инфраструктура проверена"
                    : "Проверка инфраструктуры не подтверждена"}
                </h3>
                <p>
                  {plan.infrastructureVerification.status}
                  {plan.infrastructureVerification.code
                    ? ` · ${plan.infrastructureVerification.code}`
                    : ""}
                </p>
                {plan.infrastructureObservedAt && (
                  <p>Получено: {plan.infrastructureObservedAt}</p>
                )}
                <ul>
                  {plan.infrastructureVerification.deployments.map((item) => (
                    <li key={item.deploymentId}>
                      {item.deploymentId} · Verify {item.verifiedAt}
                    </li>
                  ))}
                </ul>
                {plan.infrastructureCacheWarning && (
                  <p role="status">
                    Локальное наблюдение не сохранено. Решение текущего плана
                    получено от Core.
                  </p>
                )}
              </section>
            )}

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
                  <code>{operation.error.code}</code> —{" "}
                  {operation.error.message}
                </li>
              )}
              {run?.error && (
                <li>
                  <code>{run.error.code}</code> — {run.error.message}
                  {!!run.error.diagnosticCodes?.length && (
                    <span>
                      {" "}
                      Диагностика Core: {run.error.diagnosticCodes.join(", ")}
                    </span>
                  )}
                </li>
              )}
            </ul>
          </article>
        )}
        {!currentPlan && !runActive && (
          <article className="card">
            <p role="status">
              Этот план нельзя использовать для текущего состояния проекта.
              Сохраните или отмените черновик и сформируйте свежий план.
            </p>
            {(state?.status === "READY_TO_PLAN" || scopeChanged) && (
              <>
                {orderError && (
                  <p className="error" role="alert">
                    {orderError}
                  </p>
                )}
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
          {!displayedPhases.some((phase) => phase.id === "services") && (
            <section className="plan-phase-card">
              <h3>services · Инфраструктура</h3>
              {servicesControl}
            </section>
          )}
          {librariesControl &&
            !displayedPhases.some((phase) => phase.id === "applications") && (
              <section className="plan-phase-card">
                <h3>Библиотеки</h3>
                {librariesControl}
              </section>
            )}
          {!hasActions && (
            <p role="status">
              В плане нет действий по развёртыванию сервисов. Проверьте состав и
              размещение сервисов в проекте.
            </p>
          )}
          {displayedPhases.map((phase) => (
            <details
              className={`plan-phase-card${phase.id === "services" && infrastructureExcluded ? " installation-phase-excluded" : ""}`}
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
                          : phase.id === "services"
                            ? "services · Инфраструктура"
                            : phase.id === "applications"
                              ? "Библиотеки"
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
                  {phase.id === "services" && infrastructureExcluded
                    ? "Исключено из выбранного запуска"
                    : scopeChanged
                      ? "Требуется свежий план"
                      : plan.status !== "EXECUTABLE"
                        ? "Есть замечания"
                        : plan.approved
                          ? "Готово к выполнению"
                          : "Ожидает одобрения"}
                </span>
              </summary>
              {phase.id === "services" && servicesControl}
              {phase.id === "applications" && librariesControl}
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
                        <b>{planActionLabel(action)}</b>
                        {!!action.progressSteps?.length && (
                          <ul className="plan-progress-steps">
                            {action.progressSteps.map((step) => (
                              <li key={step.id}>{step.summary}</li>
                            ))}
                          </ul>
                        )}
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
        {plan.status === "EXECUTABLE" && (scopeChanged || !plan.approved) && (
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
      {plan.status === "EXECUTABLE" && (scopeChanged || !plan.approved) && (
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
      {plan.approved && !scopeChanged && (
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
          <ul
            className="safe-findings"
            aria-label="Причины недоступности запуска"
          >
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
  const eventScrollRef = useRef<HTMLDivElement>(null);
  const visibleEvents = events.slice(-executionEventWindowSize);
  const outputBusy =
    run?.error?.code === "OUTPUT_BUSY" ||
    events.some(
      (event) => executionDiagnosticCode(event.safeMessage) === "OUTPUT_BUSY",
    );
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
  const currentAction = installationActionRows(plan).find(
    (action) =>
      action.id === progress?.activeActionId &&
      ["STARTING", "RUNNING", "CANCELLING"].includes(run.run!.state),
  );
  const lastTask = [...events]
    .reverse()
    .find((event) => event.eventType === "TASK_COMPLETED" && event.task?.name);
  const runEvents = events.filter((event) => event.runId === run.run!.runId);
  const started = runEvents
    .filter((event) => event.eventType === "RUN_STARTED")
    .reduce<InstallationEventView | undefined>(
      (first, event) =>
        !first || event.sequence < first.sequence ? event : first,
      undefined,
    );
  const terminalStatus: Record<string, string> = {
    SUCCEEDED: "SUCCESS",
    FAILED: "FAILED",
    CANCELLED: "CANCELLED",
    INTERRUPTED: "INTERRUPTED",
  };
  const completed = terminalStatus[run.run.state]
    ? runEvents.find(
        (event) =>
          event.sequence === run.run!.sequence &&
          event.eventType === "DIAGNOSTIC" &&
          event.status === terminalStatus[run.run!.state] &&
          !event.actionId &&
          !event.task,
      )
    : undefined;
  const runTime = (timestamp?: string) => {
    const date = new Date(timestamp || "");
    return Number.isFinite(date.getTime())
      ? new Intl.DateTimeFormat("ru-RU", {
          dateStyle: "short",
          timeStyle: "medium",
          timeZone: "Europe/Moscow",
        }).format(date)
      : undefined;
  };
  const startedTime = runTime(started?.timestamp);
  const completedTime = runTime(completed?.timestamp);
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
            {run.reconnected && (
              <p>
                Переподключено к прежнему запуску. Ревизия:{" "}
                {run.projectRevision}
              </p>
            )}
          </div>
          {(["STARTING", "RUNNING", "CANCELLING"].includes(run.run.state) ||
            run.cancelUnconfirmed) && (
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
              Текущее действие: <b>{planActionLabel(currentAction)}</b> ·{" "}
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
                      <tr key={`${event.runId}-${event.sequence}`}>
                        <td>
                          <time dateTime={event.timestamp || undefined}>
                            {eventTimestampLabel(event.timestamp)}
                          </time>
                        </td>
                        <td>
                          <span className="execution-event-select">
                            {taskNameWithoutRole(event) ||
                              eventMessageLabel(event.safeMessage) ||
                              event.eventType}
                          </span>
                          <small>{eventMessageLabel(event.safeMessage)}</small>
                          {event.errorCode && (
                            <small className="field-error">
                              <code>{event.errorCode}</code>{" "}
                              {event.errorSummary}
                            </small>
                          )}
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
        <article className="card execution-plan-card">
          <div className="execution-event-title">
            <h2>Действия плана</h2>
            {progress && (
              <span>
                {progress.completedActionIds.length} из{" "}
                {progress.actionIds.length} завершено
              </span>
            )}
          </div>
          <p className="execution-plan-timestamp">
            Начало установки:{" "}
            {startedTime ? (
              <time dateTime={started!.timestamp}>{startedTime} МСК</time>
            ) : (
              "время ещё не получено"
            )}
          </p>
          <div className="execution-plan-scroll">
            {!plan?.phases.some((phase) => phase.actions.length) ? (
              <p>Действия плана для этого запуска недоступны.</p>
            ) : (
              <ol className="execution-plan-actions">
                {installationActionRows(plan).map((action) => {
                  const outcome = progress?.actionOutcomes[action.id];
                  const completion = events.find(
                    (event) =>
                      event.runId === run.run!.runId &&
                      event.actionId === action.id &&
                      event.eventType === "ACTION_COMPLETED" &&
                      event.sequence ===
                        progress?.actionOutcomeSequences[action.id],
                  );
                  const completedDate = new Date(completion?.timestamp || "");
                  const completedTime = Number.isFinite(completedDate.getTime())
                    ? new Intl.DateTimeFormat("ru-RU", {
                        timeZone: "Europe/Moscow",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      }).format(completedDate)
                    : "Время неизвестно";
                  const active =
                    (progress?.activeActionId === action.id ||
                      (!!action.progressSteps?.length &&
                        progress?.stepParents[progress.activeActionId || ""] ===
                          action.id)) &&
                    ["STARTING", "RUNNING", "CANCELLING"].includes(
                      run.run!.state,
                    );
                  const waiting =
                    !outcome &&
                    !active &&
                    progress?.complete &&
                    ["STARTING", "RUNNING", "CANCELLING"].includes(
                      run.run!.state,
                    );
                  const label = active
                    ? "Выполняется"
                    : waiting
                      ? "Ожидает"
                      : actionResultLabel(action.id, run.run!.state, progress);
                  const tone = active
                    ? "running"
                    : ["SUCCESS", "CHANGED"].includes(outcome || "")
                      ? "success"
                      : outcome === "FAILED"
                        ? "error"
                        : "neutral";
                  const symbol = active
                    ? "◌"
                    : tone === "success"
                      ? "✓"
                      : tone === "error"
                        ? "!"
                        : outcome === "SKIPPED"
                          ? "↷"
                          : "◷";
                  return (
                    <li
                      key={action.id}
                      className={`execution-plan-action is-${tone}${action.parentId ? " is-progress-step" : ""}${action.progressSteps?.length ? " is-progress-group" : ""}`}
                      aria-current={
                        active && !action.progressSteps?.length
                          ? "step"
                          : undefined
                      }
                    >
                      {action.number !== undefined && (
                        <span
                          className="execution-plan-number"
                          aria-hidden="true"
                        >
                          {action.number}
                        </span>
                      )}
                      <span
                        className="execution-plan-symbol"
                        aria-hidden="true"
                      >
                        {symbol}
                      </span>
                      <div className="execution-plan-description">
                        <strong>{planActionLabel(action)}</strong>
                        <small>
                          {action.targets.join(", ") || "Без целевых серверов"}
                          {action.serviceDeployment
                            ? ` · ${action.serviceDeployment}`
                            : ""}
                        </small>
                      </div>
                      <span
                        className="execution-plan-status"
                        title={
                          tone === "success" ? `${label} · МСК` : undefined
                        }
                      >
                        {tone === "success" ? completedTime : label}
                      </span>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
          {completedTime && (
            <p className="execution-plan-timestamp">
              Завершение установки:{" "}
              <time dateTime={completed!.timestamp}>{completedTime} МСК</time>
            </p>
          )}
        </article>
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
  onOpenPendingOutputs,
  onCollectSecretOutputs,
}: {
  run?: InstallationRunOperation;
  plan?: InstallationPlanView;
  progress?: RunProgress;
  events: InstallationEventView[];
  secretOutputPackages?: SecretOutputPackagesOperation;
  outputDelivery?: SecretOutputDeliveryOperation;
  onOpenPendingOutputs: () => void;
  onCollectSecretOutputs: () => Promise<void>;
}) {
  const [collectingOutputs, setCollectingOutputs] = useState(false);
  const terminal =
    !!run?.run &&
    ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(run.run.state);
  const outputBusy =
    run?.error?.code === "OUTPUT_BUSY" ||
    events.some(
      (event) => executionDiagnosticCode(event.safeMessage) === "OUTPUT_BUSY",
    );
  const actions = installationActionRows(plan);
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
                        <td>{planActionLabel(action)}</td>
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
        {(!secretOutputPackages ||
          secretOutputPackages.status !== "READY" ||
          secretOutputPackages.nextCursor ||
          secretOutputPackages.packages?.some(
            (item) => item.state !== "LOCAL_DELIVERED",
          )) && (
          <button
            className="outline"
            disabled={collectingOutputs}
            onClick={async () => {
              setCollectingOutputs(true);
              try {
                await onCollectSecretOutputs();
              } finally {
                setCollectingOutputs(false);
              }
            }}
          >
            Проверить и сохранить зашифрованные файлы
          </button>
        )}
        {secretOutputPackages?.error && (
          <p className="field-error" role="alert">
            {secretOutputPackages.error.message}
          </p>
        )}
        {outputDelivery && (
          <p
            role={outputDelivery.status === "UNAVAILABLE" ? "alert" : "status"}
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
            <small>
              Запуск: {item.sourceRunId} · Поколение: {item.generation}
            </small>
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
                {event.errorCode && (
                  <small className="field-error">
                    <code>{event.errorCode}</code> {event.errorSummary}
                  </small>
                )}
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

import { useEffect, useRef, useState } from "react";
import type {
  EditResult,
  ExecutionNodeContext,
  ExecutionNodePreparation,
  ExecutionNodeReadiness,
  EndpointPreview,
  OpenResult,
  ProjectBackend,
  SessionCredentialInput,
  SessionCredentialStatus,
  VerifiedPKIView,
} from "./backend";
import { backend } from "./backend";
import { type ServerIntent, ServersPage } from "./ServersPage";
import {
  type CertificateIntent,
  type CertificateSourceOptions,
  CertificatesPage,
} from "./CertificatesPage";
import {
  type DeploymentIntent,
  type EndpointIntent,
  type PlacementIntent,
  type ProviderIntent,
  TopologyPage,
} from "./TopologyPage";
import { type ConfigurationIntent, ServicesPage } from "./ServicesPage";
import "./edit.css";

type Page =
  | "project"
  | "servers"
  | "topology"
  | "certificates"
  | "services"
  | "installation";
type StructuralIntent =
  | ServerIntent
  | DeploymentIntent
  | PlacementIntent
  | EndpointIntent
  | ProviderIntent
  | CertificateIntent
  | ConfigurationIntent;
const navigation: Array<{ id: Page | string; label: string }> = [
  { id: "project", label: "Проект" },
  { id: "servers", label: "Серверы" },
  { id: "topology", label: "Топология" },
  { id: "certificates", label: "Сертификаты" },
  { id: "services", label: "Сервисы" },
  { id: "installation", label: "Установка" },
  { id: "logs", label: "Логи" },
  { id: "help", label: "Справка" },
  { id: "about", label: "О программе" },
  { id: "settings", label: "Настройки" },
];
const count = (value: unknown) =>
  value && typeof value === "object" ? Object.keys(value).length : 0;
const verificationLabel = (status: string) => {
  switch (status) {
    case "VERIFIED":
      return "Проверено";
    case "INVALID":
      return "Ошибки проверки";
    case "VERIFYING":
      return "Проверяется";
    default:
      return "Не проверено";
  }
};

function certificateSourceOptions(
  managed: OpenResult["managed"],
  intents: StructuralIntent[],
): CertificateSourceOptions {
  const hosts = new Set(Object.keys(managed?.servers || {}));
  const deployments = new Set(Object.keys(managed?.deployments || {}));
  const members = new Map<string, { deploymentId: string; memberId: string }>();
  for (const placement of managed?.memberPlacements || [])
    members.set(`${placement.deploymentId}\u0000${placement.memberId}`, {
      deploymentId: placement.deploymentId,
      memberId: placement.memberId,
    });
  for (const intent of intents) {
    if (intent.operation === "CreateServer") hosts.add(intent.hostId);
    if (intent.operation === "DeleteServer") hosts.delete(intent.hostId);
    if (intent.operation === "CreateServiceDeployment")
      deployments.add(intent.deploymentId);
    if (intent.operation === "DeleteServiceDeployment") {
      deployments.delete(intent.deploymentId);
      for (const [key, member] of members)
        if (member.deploymentId === intent.deploymentId) members.delete(key);
    }
    if (intent.operation === "ReconcileDeploymentPlacement") {
      for (const [key, member] of members)
        if (member.deploymentId === intent.deploymentId) members.delete(key);
      for (const member of intent.members)
        members.set(`${intent.deploymentId}\u0000${member.memberId}`, {
          deploymentId: intent.deploymentId,
          memberId: member.memberId,
        });
    }
  }
  return {
    hosts: [...hosts].sort(),
    deployments: [...deployments].sort(),
    members: [...members.values()]
      .filter((member) => deployments.has(member.deploymentId))
      .sort((left, right) =>
        `${left.deploymentId}\u0000${left.memberId}`.localeCompare(
          `${right.deploymentId}\u0000${right.memberId}`,
        ),
      ),
  };
}

export function App({ api = backend }: { api?: ProjectBackend }) {
  const [result, setResult] = useState<OpenResult>({
    status: "NO_PROJECT",
  } as OpenResult);
  const [page, setPage] = useState<Page>("project");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [projectDialog, setProjectDialog] = useState(false);
  const [name, setName] = useState("");
  const [root, setRoot] = useState("");
  const [parent, setParent] = useState("");
  const [separator, setSeparator] = useState("\\");
  const [nameRequired, setNameRequired] = useState(false);
  const [edit, setEdit] = useState<EditResult | null>(null);
  const [editError, setEditError] = useState<EditResult["error"] | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [commandCount, setCommandCount] = useState(0);
  const [intents, setIntents] = useState<StructuralIntent[]>([]);
  const [topologyTab, setTopologyTab] = useState<
    "services" | "servers" | "entryPoints"
  >("services");
  const [selectedTopologyDeployment, setSelectedTopologyDeployment] =
    useState("");
  const [selectedTopologyHost, setSelectedTopologyHost] = useState("");
  const [servicesView, setServicesView] = useState<"list" | "detail">("list");
  const [selectedServiceDeployment, setSelectedServiceDeployment] =
    useState("");
  const [selectedServiceMember, setSelectedServiceMember] = useState("");
  const [certificateReturn, setCertificateReturn] = useState<{
    deploymentId: string;
    memberId?: string;
  } | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [refreshRequired, setRefreshRequired] = useState(false);
  const [refreshRoot, setRefreshRoot] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const [serverTypes, setServerTypes] = useState<
    Array<{ id: string; displayName: string }>
  >([]);
  const [configError, setConfigError] = useState<string | null>(null);
  const [credentialStatus, setCredentialStatus] =
    useState<SessionCredentialStatus | null>(null);
  const [executionNode, setExecutionNode] =
    useState<ExecutionNodeContext | null>(null);
  const [endpointPreview, setEndpointPreview] = useState<
    EndpointPreview | undefined
  >(undefined);
  const [verifiedPKI, setVerifiedPKI] = useState<VerifiedPKIView | undefined>(
    undefined,
  );
  const endpointPreviewRequest = useRef(0);
  const destination = parent ? `${parent}${separator}${name.trim()}` : root;
  const snapshot = result.snapshot;
  const managed = result.managed;
  const verification = result.verification || { status: "UNVERIFIED" };
  const local = result.project;
  const project = snapshot?.project as Record<string, unknown> | undefined;
  const empty =
    result.status === "OPEN" &&
    result.classification === "EMPTY_MANAGED_PROJECT" &&
    local &&
    !snapshot;
  const projectOpen = result.status === "OPEN";
  const topologyAvailable =
    projectOpen &&
    (result.classification === "EMPTY_MANAGED_PROJECT" ||
      result.classification === "MANAGED_PROJECT");
  const executionReady = executionNode?.status === "READY";
  const title = empty
    ? local.name
    : project?.name
      ? String(project.name)
      : local?.name || "Проект не открыт";
  const certificateSources = certificateSourceOptions(managed, intents);

  useEffect(() => {
    let live = true;
    api
      .getApplicationConfig()
      .then((value) => {
        if (!live) return;
        if (value.status === "READY" && value.config) {
          setServerTypes(value.config.serverTypes || []);
          setConfigError(null);
        } else {
          setServerTypes([]);
          setConfigError(
            value.error?.message || "Конфигурация типов серверов недоступна.",
          );
        }
      })
      .catch(
        () => live && setConfigError("Конфигурация типов серверов недоступна."),
      );
    return () => {
      live = false;
    };
  }, [api]);

  useEffect(() => {
    let live = true;
    if (!projectOpen) {
      setCredentialStatus(null);
      return () => {
        live = false;
      };
    }
    if (!api.getSessionCredentialStatus)
      return () => {
        live = false;
      };
    api
      .getSessionCredentialStatus()
      .then((value) => live && setCredentialStatus(value))
      .catch(() => live && setCredentialStatus(null));
    return () => {
      live = false;
    };
  }, [api, projectOpen, result.root]);

  useEffect(() => {
    let live = true;
    if (!projectOpen || !api.getExecutionNodeContext) {
      setExecutionNode(null);
      return () => {
        live = false;
      };
    }
    api
      .getExecutionNodeContext()
      .then((value) => live && setExecutionNode(value))
      .catch(() => live && setExecutionNode(null));
    return () => {
      live = false;
    };
  }, [api, projectOpen, result.root, commandCount]);

  const clearDraft = () => {
    setEdit(null);
    setEditError(null);
    setSessionId("");
    setCommandCount(0);
    setIntents([]);
    setReviewOpen(false);
  };
  const resetTopologySelection = () => {
    setTopologyTab("services");
    setSelectedTopologyDeployment("");
    setSelectedTopologyHost("");
    setServicesView("list");
    setSelectedServiceDeployment("");
    setSelectedServiceMember("");
    setCertificateReturn(null);
    endpointPreviewRequest.current += 1;
    setEndpointPreview(undefined);
    setVerifiedPKI(undefined);
  };
  const clearRefreshFailure = () => {
    setRefreshRequired(false);
    setRefreshRoot("");
    setRefreshError("");
  };
  const open = async () => {
    setLoading(true);
    try {
      const next = await api.chooseProject();
      setResult(next);
      clearRefreshFailure();
      resetTopologySelection();
      setPage("project");
    } finally {
      setLoading(false);
    }
  };
  const chooseParent = async () => {
    const selected = await api.chooseProjectParent();
    if (selected) {
      setParent(selected);
      setSeparator("\\");
    }
  };
  const updateDestination = (value: string) => {
    setParent("");
    setRoot(value);
  };
  const adoptDestinationParent = () => {
    const index = Math.max(root.lastIndexOf("\\"), root.lastIndexOf("/"));
    if (index >= 0) {
      setParent(root.slice(0, index));
      setSeparator(root[index]);
    }
  };
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setNameRequired(true);
      return;
    }
    setCreating(true);
    try {
      const next = await api.createProject({
        projectRoot: destination,
        displayName: name,
        compatibilitySourceId: "default",
      });
      setResult(next);
      clearRefreshFailure();
      resetTopologySelection();
      setProjectDialog(false);
      setPage("project");
      if (next.status === "OPEN") {
        setName("");
        setRoot("");
        setParent("");
        setSeparator("\\");
        setNameRequired(false);
      }
    } finally {
      setCreating(false);
    }
  };
  const close = async () => {
    setResult(await api.closeProject());
    clearRefreshFailure();
    resetTopologySelection();
    setPage("project");
  };

  const appendStructuralIntent = async (
    intent: StructuralIntent,
  ): Promise<boolean> => {
    if (commandCount >= 16) {
      setEditError({
        code: "EDIT_COMMAND_LIMIT_EXCEEDED",
        message: "В одном черновике допускается не более 16 изменений.",
      });
      return false;
    }
    setEditBusy(true);
    let id = sessionId;
    let created = false;
    try {
      if (!id) {
        const started = await api.startEditSession();
        if (started.error || !started.session?.sessionId) {
          setEdit(started);
          setEditError(
            started.error || {
              code: "EDIT_SESSION_UNAVAILABLE",
              message: "Не удалось начать черновик изменений.",
            },
          );
          return false;
        }
        id = started.session.sessionId;
        created = true;
        setEdit(started);
        setSessionId(id);
      }
      const next = await api.appendEditCommand(id, intent);
      if (next.error || !next.session) {
        if (created) {
          await api.discardEditSession(id);
          clearDraft();
        } else {
          setEdit(next);
          setEditError(
            next.error || {
              code: "EDIT_COMMAND_BLOCKED",
              message: "Изменение не добавлено в черновик.",
            },
          );
        }
        return false;
      }
      setEdit(next);
      setEditError(null);
      setSessionId(id);
      setCommandCount(next.session.commandCount);
      setIntents((current) => [...current, intent]);
      endpointPreviewRequest.current += 1;
      setEndpointPreview({ status: "STALE" });
      setVerifiedPKI({ status: "STALE" });
      return true;
    } finally {
      setEditBusy(false);
    }
  };
  const review = async () => {
    if (!sessionId || commandCount === 0) return;
    setEditBusy(true);
    setReviewOpen(true);
    try {
      const next = await api.reviewEditSession(sessionId);
      setEdit(next);
      setEditError(next.error || null);
    } finally {
      setEditBusy(false);
    }
  };
  const save = async () => {
    const planId = edit?.plan?.planId;
    if (!sessionId || !planId) return;
    setEditBusy(true);
    try {
      const next = await api.commitEditPlan(sessionId, planId);
      if (next.error) {
        setEdit(next);
        setEditError(next.error);
        return;
      }
      if (next.status === "COMMITTED") {
        if (next.current) setResult(next.current);
        setEndpointPreview(undefined);
        setVerifiedPKI(undefined);
        clearDraft();
        return;
      }
      if (next.status === "COMMITTED_REFRESH_FAILED") {
        const rootToRefresh = next.current?.root || result.root || "";
        setResult({
          ...(next.current || result),
          snapshot: undefined,
          managed: undefined,
        } as OpenResult);
        clearDraft();
        resetTopologySelection();
        setRefreshRequired(true);
        setRefreshRoot(rootToRefresh);
        setRefreshError("");
        return;
      }
      setEdit(next);
      setEditError(
        next.commit?.finding
          ? {
              code: next.commit.finding.code,
              message: next.commit.finding.safeMessage,
            }
          : {
              code: "WRITE_FAILED",
              message: "Сохранение изменений заблокировано.",
            },
      );
    } finally {
      setEditBusy(false);
    }
  };
  const refreshCommittedProject = async () => {
    if (!refreshRoot) return;
    setEditBusy(true);
    setRefreshError("");
    try {
      const next = await api.openProject(refreshRoot);
      if (
        next.status === "OPEN" &&
        (next.classification === "EMPTY_MANAGED_PROJECT" || !!next.managed)
      ) {
        setResult(next);
        clearRefreshFailure();
        return;
      }
      setRefreshError(
        next.error?.message || "Текущее представление проекта не обновлено.",
      );
    } catch {
      setRefreshError("Текущее представление проекта не обновлено.");
    } finally {
      setEditBusy(false);
    }
  };
  const discard = async () => {
    if (!sessionId) return;
    setEditBusy(true);
    try {
      await api.discardEditSession(sessionId);
      clearDraft();
      endpointPreviewRequest.current += 1;
      setEndpointPreview({ status: "STALE" });
      setVerifiedPKI({ status: "STALE" });
    } finally {
      setEditBusy(false);
    }
  };
  const verify = async () => {
    if (!api.verifyProject) return;
    const requestToken = ++endpointPreviewRequest.current;
    setEditBusy(true);
    setResult(
      (current) =>
        ({ ...current, verification: { status: "VERIFYING" } }) as OpenResult,
    );
    try {
      const next = await api.verifyProject();
      if (requestToken !== endpointPreviewRequest.current) return;
      setResult(
        (current) => ({ ...current, verification: next }) as OpenResult,
      );
      if (api.getEndpointPreview) {
        const preview = await api.getEndpointPreview();
        if (requestToken !== endpointPreviewRequest.current) return;
        setEndpointPreview(preview);
      }
      if (api.getVerifiedPKIView) {
        const view = await api.getVerifiedPKIView();
        if (requestToken !== endpointPreviewRequest.current) return;
        setVerifiedPKI(view);
      }
    } finally {
      setEditBusy(false);
    }
  };
  const setSessionCredential = async (input: SessionCredentialInput) => {
    if (!api.setSessionCredential)
      throw new Error("SESSION_CREDENTIAL_UNAVAILABLE");
    const status = await api.setSessionCredential(input);
    setCredentialStatus(status);
    return status;
  };
  const clearSessionCredential = async () => {
    if (!api.clearSessionCredential)
      throw new Error("SESSION_CREDENTIAL_UNAVAILABLE");
    const status = await api.clearSessionCredential();
    setCredentialStatus(status);
    return status;
  };
  const selectExecutionNode = async (hostId: string) => {
    if (!api.selectExecutionNode)
      throw new Error("EXECUTION_NODE_SELECTION_UNAVAILABLE");
    const context = await api.selectExecutionNode(hostId);
    setExecutionNode(context);
    endpointPreviewRequest.current += 1;
    setEndpointPreview({ status: "STALE" });
    setVerifiedPKI({ status: "STALE" });
    return context;
  };
  const checkExecutionNode = async (): Promise<ExecutionNodeReadiness> => {
    if (!api.checkExecutionNode)
      throw new Error("EXECUTION_NODE_CHECK_UNAVAILABLE");
    const readiness = await api.checkExecutionNode();
    setExecutionNode((current) =>
      current ? { ...current, status: readiness.status } : current,
    );
    return readiness;
  };
  const planExecutionNodePreparation =
    async (): Promise<ExecutionNodePreparation> => {
      if (!api.planExecutionNodePreparation)
        throw new Error("EXECUTION_NODE_PREPARATION_UNAVAILABLE");
      return api.planExecutionNodePreparation();
    };
  const prepareExecutionNode = async (
    planId: string,
  ): Promise<ExecutionNodePreparation> => {
    if (!api.prepareExecutionNode)
      throw new Error("EXECUTION_NODE_PREPARATION_UNAVAILABLE");
    const preparation = await api.prepareExecutionNode(planId);
    if (preparation.verification) {
      setResult(
        (current) =>
          ({
            ...current,
            verification: preparation.verification,
          }) as OpenResult,
      );
      if (api.getVerifiedPKIView) {
        const view = await api.getVerifiedPKIView();
        setVerifiedPKI(view);
      }
    }
    setExecutionNode((current) =>
      current
        ? {
            ...current,
            status:
              preparation.status === "PREPARED" ? "READY" : preparation.status,
          }
        : current,
    );
    return preparation;
  };

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          Platform
          <br />
          <span>Installer</span>
        </div>
        <nav>
          {navigation.map((item) => {
            const enabled =
              item.id === "project" ||
              (item.id === "servers" && projectOpen) ||
              (item.id === "topology" && topologyAvailable) ||
              (item.id === "certificates" && topologyAvailable) ||
              (item.id === "services" && topologyAvailable) ||
              (item.id === "installation" && projectOpen && executionReady);
            return (
              <button
                key={item.id}
                className={item.id === page ? "active" : "future"}
                disabled={!enabled}
                onClick={() => {
                  if (
                    item.id !== "project" &&
                    item.id !== "servers" &&
                    item.id !== "topology" &&
                    item.id !== "certificates" &&
                    item.id !== "services" &&
                    item.id !== "installation"
                  )
                    return;
                  setPage(item.id);
                  if (item.id === "services") setServicesView("list");
                }}
              >
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>
      <main>
        <header>
          <div>
            <strong>{title}</strong>
            <span>
              {result.root || "Выберите существующий проект или создайте новый"}
            </span>
          </div>
          {sessionId && (
            <div className="unsaved">Есть несохранённые изменения</div>
          )}
          {projectOpen && (
            <div className="readonly">
              {sessionId ? "Есть изменения" : "Сохранено"}
            </div>
          )}
          {projectOpen && (
            <div className="readonly">
              {verificationLabel(verification.status)}
            </div>
          )}
          {projectOpen && (
            <button
              className="execution-node-badge"
              aria-label="Открыть Execution Node"
              onClick={() => setPage("servers")}
              title="Открыть Execution Node на странице Серверы"
            >
              Execution Node: {executionNode?.status || "NOT_CONFIGURED"}
              {executionNode?.safeLabel ? ` · ${executionNode.safeLabel}` : ""}
            </button>
          )}
          <button
            className="outline"
            onClick={() => setProjectDialog(true)}
            disabled={loading || creating || !!sessionId || refreshRequired}
          >
            Создать проект
          </button>
          <button
            className="outline"
            onClick={open}
            disabled={loading || creating || !!sessionId || refreshRequired}
          >
            Открыть проект
          </button>
          {sessionId && commandCount > 0 && (
            <button onClick={review} disabled={editBusy}>
              Сохранить
            </button>
          )}
          {projectOpen && (
            <button
              className="outline"
              onClick={verify}
              disabled={
                editBusy ||
                refreshRequired ||
                verification.status === "VERIFYING"
              }
            >
              Проверить
            </button>
          )}
        </header>
        <section className="banner">
          Сохранение выполняется локально. Проверка последней сохранённой
          ревизии через Core запускается отдельно.
        </section>
        {refreshRequired && (
          <section className="card refresh-required" role="alert">
            <h2>Проект сохранён, но текущее представление не обновлено</h2>
            <p>
              Канонические файлы уже записаны. Повторное сохранение недоступно,
              пока проект не будет безопасно перечитан.
            </p>
            {refreshError && <p className="field-error">{refreshError}</p>}
            <button
              onClick={refreshCommittedProject}
              disabled={editBusy || !refreshRoot}
            >
              Обновить проект
            </button>
          </section>
        )}
        {(loading || creating) && (
          <section className="card">
            {creating ? "Безопасное создание проекта…" : "Открытие проекта…"}
          </section>
        )}
        {!loading && !creating && result.status === "NO_PROJECT" && (
          <section className="empty card">
            <h1>Создайте или откройте проект</h1>
            <p>
              Новый проект содержит только metadata и compatibility locks из
              verified local bundle.
            </p>
            <button onClick={() => setProjectDialog(true)}>
              Создать проект
            </button>
            <button className="outline" onClick={open}>
              Открыть папку проекта
            </button>
          </section>
        )}
        {!loading && !creating && result.status === "ERROR" && (
          <section className="error card">
            <h1>Проект не открыт</h1>
            <p>{result.error?.message}</p>
            <code>{result.error?.code}</code>
            <button onClick={() => setProjectDialog(true)}>
              Создать проект
            </button>
            <button className="outline" onClick={open}>
              Открыть другой проект
            </button>
          </section>
        )}
        {!loading && !creating && projectOpen && page === "project" && (
          <ProjectPage
            empty={!!empty}
            snapshot={snapshot}
            managed={managed}
            verification={verification}
            local={local}
            onClose={close}
            onServers={() => setPage("servers")}
            closeDisabled={!!sessionId || refreshRequired}
          />
        )}
        {!loading && !creating && projectOpen && page === "servers" && (
          <ServersPage
            snapshot={snapshot}
            managed={managed}
            empty={!!empty}
            intents={intents.filter(
              (intent): intent is ServerIntent =>
                intent.operation === "CreateServer" ||
                intent.operation === "UpdateServer" ||
                intent.operation === "DeleteServer",
            )}
            serverTypes={serverTypes}
            configError={configError}
            busy={editBusy}
            structuralDisabled={refreshRequired}
            onAppend={appendStructuralIntent}
            onReview={review}
            onDiscard={discard}
            commandCount={commandCount}
            credentialStatus={credentialStatus}
            onSetCredential={setSessionCredential}
            onClearCredential={clearSessionCredential}
            executionNode={executionNode}
            onSelectExecutionNode={selectExecutionNode}
            onCheckExecutionNode={checkExecutionNode}
            onPlanExecutionNodePreparation={planExecutionNodePreparation}
            onPrepareExecutionNode={prepareExecutionNode}
          />
        )}
        {!loading && !creating && projectOpen && page === "topology" && (
          <TopologyPage
            managed={managed}
            catalog={result.catalog}
            intents={intents.filter(
              (
                intent,
              ): intent is
                | DeploymentIntent
                | PlacementIntent
                | EndpointIntent
                | ProviderIntent =>
                intent.operation === "CreateServiceDeployment" ||
                intent.operation === "DeleteServiceDeployment" ||
                intent.operation === "ReconcileDeploymentPlacement" ||
                intent.operation === "ReconcileHostScopedDeploymentPlacement" ||
                intent.operation === "CreateEndpointGroup" ||
                intent.operation === "UpdateEndpointGroup" ||
                intent.operation === "DeleteEndpointGroup" ||
                intent.operation === "SetServiceEndpointGroup" ||
                intent.operation === "ClearServiceEndpointGroup" ||
                intent.operation === "ReconcileEndpointProvider" ||
                intent.operation === "ClearEndpointProvider",
            )}
            serverIntents={intents.filter(
              (intent): intent is ServerIntent =>
                intent.operation === "CreateServer" ||
                intent.operation === "UpdateServer" ||
                intent.operation === "DeleteServer",
            )}
            busy={editBusy}
            structuralDisabled={refreshRequired}
            commandCount={commandCount}
            onAppend={appendStructuralIntent}
            onReview={review}
            onDiscard={discard}
            activeTab={topologyTab}
            onActiveTabChange={setTopologyTab}
            selectedDeploymentId={selectedTopologyDeployment}
            onSelectedDeploymentChange={setSelectedTopologyDeployment}
            selectedHostId={selectedTopologyHost}
            onSelectedHostChange={setSelectedTopologyHost}
            onConfigureDeployment={(deploymentId) => {
              setSelectedTopologyDeployment(deploymentId);
              setSelectedServiceDeployment(deploymentId);
              setServicesView("detail");
              setPage("services");
            }}
            preview={endpointPreview}
            verificationStatus={verification.status}
          />
        )}
        {!loading && !creating && projectOpen && page === "services" && (
          <ServicesPage
            managed={managed}
            catalog={result.catalog}
            deploymentIntents={intents.filter(
              (intent): intent is DeploymentIntent =>
                intent.operation === "CreateServiceDeployment" ||
                intent.operation === "DeleteServiceDeployment",
            )}
            placementIntents={intents.filter(
              (intent): intent is PlacementIntent =>
                intent.operation === "ReconcileDeploymentPlacement" ||
                intent.operation === "ReconcileHostScopedDeploymentPlacement",
            )}
            certificateIntents={intents.filter(
              (intent): intent is CertificateIntent =>
                intent.operation === "CreateCertificateAuthority" ||
                intent.operation === "UpdateCertificateAuthority" ||
                intent.operation === "DeleteCertificateAuthority" ||
                intent.operation === "CreateCertificateProfile" ||
                intent.operation === "UpdateCertificateProfile" ||
                intent.operation === "DeleteCertificateProfile" ||
                intent.operation === "CreateTLSProfile" ||
                intent.operation === "UpdateTLSProfile" ||
                intent.operation === "DeleteTLSProfile" ||
                intent.operation === "CreateCertificateScope" ||
                intent.operation === "UpdateCertificateScope" ||
                intent.operation === "DeleteCertificateScope",
            )}
            configurationIntents={intents.filter(
              (intent): intent is ConfigurationIntent =>
                intent.operation === "SetServiceConfigurationValue" ||
                intent.operation === "RemoveServiceConfigurationOverride",
            )}
            busy={editBusy}
            structuralDisabled={refreshRequired}
            commandCount={commandCount}
            error={editError?.message}
            view={servicesView}
            selectedDeploymentId={selectedServiceDeployment}
            selectedMemberId={selectedServiceMember}
            onSelectedMemberChange={setSelectedServiceMember}
            onOpenDeployment={(deploymentId) => {
              setSelectedServiceDeployment(deploymentId);
              setSelectedServiceMember("");
              setServicesView("detail");
            }}
            onBackToList={() => {
              setServicesView("list");
              setSelectedServiceDeployment("");
              setSelectedServiceMember("");
            }}
            onOpenTopology={() => setPage("topology")}
            onManageCertificates={(memberId) => {
              setCertificateReturn({
                deploymentId: selectedServiceDeployment,
                memberId,
              });
              setPage("certificates");
            }}
            onAppend={appendStructuralIntent}
            onReview={review}
            onDiscard={discard}
          />
        )}
        {!loading && !creating && projectOpen && page === "certificates" && (
          <CertificatesPage
            managed={managed}
            intents={intents.filter(
              (intent): intent is CertificateIntent =>
                intent.operation === "CreateCertificateAuthority" ||
                intent.operation === "UpdateCertificateAuthority" ||
                intent.operation === "DeleteCertificateAuthority" ||
                intent.operation === "CreateCertificateProfile" ||
                intent.operation === "UpdateCertificateProfile" ||
                intent.operation === "DeleteCertificateProfile" ||
                intent.operation === "CreateTLSProfile" ||
                intent.operation === "UpdateTLSProfile" ||
                intent.operation === "DeleteTLSProfile" ||
                intent.operation === "CreateCertificateScope" ||
                intent.operation === "UpdateCertificateScope" ||
                intent.operation === "DeleteCertificateScope",
            )}
            busy={editBusy}
            structuralDisabled={refreshRequired}
            commandCount={commandCount}
            sourceOptions={certificateSources}
            verification={verification}
            verifiedPKI={verifiedPKI}
            onAppend={appendStructuralIntent}
            onReview={review}
            onDiscard={discard}
            onVerify={verify}
            onReturnToServices={
              certificateReturn
                ? () => {
                    setSelectedServiceDeployment(
                      certificateReturn.deploymentId,
                    );
                    setSelectedServiceMember(certificateReturn.memberId || "");
                    setServicesView("detail");
                    setPage("services");
                    setCertificateReturn(null);
                  }
                : undefined
            }
          />
        )}
        {!loading && !creating && projectOpen && page === "installation" && (
          <section className="card">
            <h1>Установка</h1>
            <p>
              Execution Node: <b>{executionNode?.status || "NOT_CONFIGURED"}</b>
              {executionNode?.safeLabel ? ` · ${executionNode.safeLabel}` : ""}
            </p>
            <p>
              Проверка проекта: <b>{verificationLabel(verification.status)}</b>.
              Проверка не является разрешением на запуск.
            </p>
            <p className="muted">
              Перед выполнением будет обязателен свежий authoritative
              DeploymentPlan для сохранённой ревизии и текущего runtime.
              Подготовка Execution Node доступна только на странице Серверы.
            </p>
            <button className="outline" onClick={() => setPage("servers")}>
              Открыть Execution Node
            </button>
          </section>
        )}
        {projectDialog && (
          <div className="modal" role="presentation">
            <form className="card dialog" onSubmit={create}>
              <h1>Создать проект</h1>
              <label>
                Название проекта
                <input
                  maxLength={256}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    setNameRequired(false);
                  }}
                  autoFocus
                  aria-invalid={nameRequired}
                />
              </label>
              {nameRequired && (
                <p className="field-error" role="alert">
                  Заполните «Название проекта»: оно задаёт новую папку проекта.
                </p>
              )}
              <label>
                Новая папка проекта
                <input
                  required
                  value={destination}
                  onChange={(event) => updateDestination(event.target.value)}
                  onBlur={adoptDestinationParent}
                  placeholder="C:\\Projects\\production"
                />
              </label>
              <div className="actions">
                <button
                  type="button"
                  className="outline"
                  onClick={chooseParent}
                >
                  Выбрать parent
                </button>
                <button
                  type="button"
                  className="outline"
                  onClick={() => setProjectDialog(false)}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={creating || !destination.trim()}
                >
                  Создать проект
                </button>
              </div>
              <p>
                Название проекта всегда задаёт последнюю папку в пути. Будет
                создан только <code>project.yml</code>.
              </p>
            </form>
          </div>
        )}
        {reviewOpen && (
          <ReviewDialog
            edit={edit}
            error={editError}
            busy={editBusy}
            onClose={() => setReviewOpen(false)}
            onReview={review}
            onSave={save}
            onDiscard={discard}
          />
        )}
      </main>
    </div>
  );
}

function ProjectPage({
  empty,
  snapshot,
  managed,
  verification,
  local,
  onClose,
  onServers,
  closeDisabled,
}: {
  empty: boolean;
  snapshot: OpenResult["snapshot"];
  managed: OpenResult["managed"];
  verification: NonNullable<OpenResult["verification"]>;
  local: OpenResult["project"];
  onClose: () => void;
  onServers: () => void;
  closeDisabled: boolean;
}) {
  if (empty && local)
    return (
      <>
        <section className="title">
          <div>
            <h1>Проект ещё не настроен</h1>
            <p>
              Это корректный metadata-only проект. Добавьте серверы, затем
              проверьте и сохраните проект.
            </p>
          </div>
          <button
            className="outline"
            onClick={onClose}
            disabled={closeDisabled}
          >
            Закрыть проект
          </button>
        </section>
        <section className="grid">
          <Stat label="Серверы" value={0} />
          <Stat label="Deployments / Сервисы" value={0} />
          <Stat label="Выполнения" value={0} />
          <Stat label="Inventory" value="Не создан" />
        </section>
        <section className="card">
          <h2>Сведения проекта</h2>
          <dl>
            <dt>Название</dt>
            <dd>{local.name}</dd>
            <dt>Project ID</dt>
            <dd>{local.id}</dd>
            <dt>Compatibility source</dt>
            <dd>{local.source?.bundleDigest}</dd>
          </dl>
          <button onClick={onServers}>Добавить первый сервер</button>
        </section>
      </>
    );
  return (
    <>
      <section className="title">
        <div>
          <h1>
            {(snapshot?.project as Record<string, unknown> | undefined)?.name
              ? String((snapshot?.project as Record<string, unknown>).name)
              : "Проект"}
          </h1>
          <p>Сохранённые Installer-managed поля проекта.</p>
        </div>
        <button className="outline" onClick={onClose} disabled={closeDisabled}>
          Закрыть проект
        </button>
      </section>
      <section className="grid">
        <Stat
          label="Хосты"
          value={count(managed?.servers || snapshot?.hosts)}
        />
        <Stat
          label="Развёртывания"
          value={count(managed?.deployments || snapshot?.serviceDeployments)}
        />
        <Stat label="PKI профили" value={count(snapshot?.pki)} />
        <Stat label="Findings" value={snapshot?.findings?.length ?? 0} />
      </section>
      <section className="card">
        <h2>Состояние проекта</h2>
        <dl>
          <dt>Статус</dt>
          <dd>{verificationLabel(verification.status)}</dd>
          <dt>Revision</dt>
          <dd>{managed?.projectRevision || snapshot?.projectRevision}</dd>
        </dl>
        <button onClick={onServers}>Открыть серверы</button>
      </section>
    </>
  );
}
function ReviewDialog({
  edit,
  error,
  busy,
  onClose,
  onReview,
  onSave,
  onDiscard,
}: {
  edit: EditResult | null;
  error: EditResult["error"] | null;
  busy: boolean;
  onClose: () => void;
  onReview: () => void;
  onSave: () => void;
  onDiscard: () => void;
}) {
  const plan = edit?.plan;
  const conflict =
    error?.code === "EDIT_COMMAND_CONFLICT" ||
    plan?.finding?.code === "EDIT_COMMAND_CONFLICT";
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog review-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-title"
      >
        <h1 id="review-title">Изменения конфигурации</h1>
        {error && (
          <p className="field-error" role="alert">
            <code>{error.code}</code> {error.message}
          </p>
        )}
        {plan ? (
          <>
            {plan.finding && (
              <p className="field-error" role="alert">
                <code>{plan.finding.code}</code> {plan.finding.safeMessage}
              </p>
            )}
            <p>
              Локальная структурная проверка завершена. Документов:{" "}
              {plan.affectedDocuments?.length ?? 0}.
            </p>
            <ul>
              {plan.semanticChanges?.map((change, index) => (
                <li key={index}>{change.safeSummary}</li>
              ))}
            </ul>
            {plan.affectedDocuments && plan.affectedDocuments.length > 0 && (
              <>
                <h2>Затрагиваемые документы</h2>
                <ul>
                  {plan.affectedDocuments.map((document) => (
                    <li key={document.logicalPath}>
                      {document.logicalPath}: {document.before?.state} →{" "}
                      {document.after?.state}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        ) : (
          <p>Проверка черновика ещё не вернула план.</p>
        )}
        <div className="actions">
          <button className="outline" onClick={onClose}>
            Вернуться к редактированию
          </button>
          <button className="outline" onClick={onDiscard} disabled={busy}>
            Отменить все изменения
          </button>
          {plan?.saveAllowed ? (
            <button onClick={onSave} disabled={busy}>
              Сохранить проект
            </button>
          ) : !conflict ? (
            <button onClick={onReview} disabled={busy}>
              Повторить проверку
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}
function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {value === 0 && <small>Нет данных</small>}
    </article>
  );
}

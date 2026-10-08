import { useCallback, useEffect, useRef, useState } from "react";
import type {
  EditResult,
  ExecutionNodeContext,
  ExecutionNodePreparation,
  ExecutionNodeReadiness,
  HostKeyProbeResult,
  EndpointPreview,
  InstallationState,
  InstallationPlanOperation,
  InstallationRunOperation,
  InstallationEventView,
  OpenResult,
  ProjectExportOperationResult,
  ProjectBackend,
  RuntimeBundleUpdate,
  OrphanRunRecovery,
  SessionCredentialInput,
  SessionCredentialStatus,
  VerifiedPKIView,
  SecretOutputPackagesOperation,
  SecretOutputDeliveryOperation,
  ServiceConfigurationPreview,
} from "./backend";
import {
  backend,
  secretOutputDeliveryUnavailable,
  secretOutputListingUnavailable,
} from "./backend";
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
import { InstallationPage } from "./InstallationPage";
import { UtilityPages } from "./UtilityPages";
import {
  beginRunProgress,
  installationDisplay,
  observeRunEvent,
  type RunProgress,
} from "./installationPresentation";
import { executionNodeStatusLabel } from "./executionNodeLabels";
import "./edit.css";

type Page =
  | "project"
  | "servers"
  | "topology"
  | "certificates"
  | "services"
  | "installation"
  | "logs"
  | "help"
  | "about"
  | "settings";
type StructuralIntent =
  | ServerIntent
  | DeploymentIntent
  | PlacementIntent
  | EndpointIntent
  | ProviderIntent
  | CertificateIntent
  | ConfigurationIntent;
type ServicePreviewObservation = {
  value: ServiceConfigurationPreview;
  root: string;
  selectionKind: string;
  selectedHostId?: string;
  safeLabel?: string;
};
const navigation: Array<{ id: Page | string; label: string }> = [
  { id: "project", label: "Проект" },
  { id: "servers", label: "Серверы" },
  { id: "topology", label: "Топология" },
  { id: "certificates", label: "Сертификаты" },
  { id: "services", label: "Сервисы" },
  { id: "installation", label: "Установка" },
  { id: "logs", label: "Журналы" },
  { id: "help", label: "Справка" },
  { id: "about", label: "О программе" },
  { id: "settings", label: "Настройки" },
];
const count = (value: unknown) =>
  value && typeof value === "object" ? Object.keys(value).length : 0;
const exportExclusionLabels: Record<string, string> = {
  DRAFT: "черновики",
  RUNTIME_CREDENTIALS: "учётные данные сеанса",
  GENERATED_STATE: "созданное системой состояние",
  RUNTIME_STATE: "состояние выполнения",
  PLANS: "планы",
  FACTS: "обнаруженные сведения",
  LOGS: "журналы",
  RESULTS: "результаты",
  VERIFICATION_EVIDENCE: "данные проверки",
};
const exportExclusionLabel = (category: string) =>
  exportExclusionLabels[category] ?? "другие служебные данные";
const verificationLabel = (status: string) => {
  switch (status) {
    case "VERIFIED":
      return "Проверено";
    case "INVALID":
      return "Ошибки проверки";
    case "VERIFYING":
      return "Проверяется";
    case "STALE":
      return "Проверка устарела";
    case "UNAVAILABLE":
      return "Проверка недоступна";
    default:
      return "Не проверено";
  }
};

const verificationErrorMessage = (code: string): string => {
  if (code === "BINDING_REQUIRED")
    return "Для проверки настройте узел выполнения на странице «Серверы». Сохранённый проект не изменён.";
  if (code === "EXECUTION_NODE_READY_REQUIRED")
    return "Для проверки нужен готовый узел выполнения. Откройте «Серверы» и проверьте его состояние.";
  if (code === "EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED")
    return "Нет подтверждённой привязки к runtime узла выполнения. На странице «Серверы» задайте учётные данные сеанса, проверьте SSH-ключ и подготовьте узел, затем повторите проверку проекта.";
  const safeCode = /^[A-Z][A-Z0-9_]{0,95}$/u.test(code)
    ? code
    : "PROJECT_VERIFY_FAILED";
  return `Проверка недоступна (код: ${safeCode}). Сохранённый проект не изменён.`;
};

function projectFolderNameError(value: string): string | null {
  const leaf = value.trim();
  if (!leaf) return null; // The existing required-field message handles this.
  if (
    value !== leaf ||
    new TextEncoder().encode(leaf).length > 256 ||
    /[<>:"/\\|?*\u0000-\u001f]/u.test(leaf) ||
    leaf === "." ||
    leaf === ".." ||
    leaf.endsWith(".") ||
    /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/iu.test(leaf)
  ) {
    return "Название должно быть допустимым именем одной папки Windows (не более 256 байт).";
  }
  return null;
}

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
  const [bundleUpdate, setBundleUpdate] = useState<RuntimeBundleUpdate | null>(null);
  const [orphanRun, setOrphanRun] = useState<OrphanRunRecovery | null>(null);
  const [bundleBusy, setBundleBusy] = useState(false);
  const [page, setPage] = useState<Page>("project");
  const [loading, setLoading] = useState(false);
  const [hostExitStatus, setHostExitStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [projectDialog, setProjectDialog] = useState(false);
  const [exportDialog, setExportDialog] = useState(false);
  const [exportParent, setExportParent] = useState("");
  const [exportName, setExportName] = useState("");
  const [exportOperation, setExportOperation] =
    useState<ProjectExportOperationResult | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [name, setName] = useState("");
  const [root, setRoot] = useState("");
  const [parent, setParent] = useState("");
  const [separator, setSeparator] = useState("\\");
  const [nameRequired, setNameRequired] = useState(false);
  const [createError, setCreateError] = useState<OpenResult["error"] | null>(
    null,
  );
  const [edit, setEdit] = useState<EditResult | null>(null);
  const [editError, setEditError] = useState<EditResult["error"] | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [commandCount, setCommandCount] = useState(0);
  const [intents, setIntents] = useState<StructuralIntent[]>([]);
  const [serviceFormEpoch, setServiceFormEpoch] = useState(0);
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
  const [focusServiceMemberSettings, setFocusServiceMemberSettings] =
    useState(false);
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
  const [serviceExecutionPriorities, setServiceExecutionPriorities] = useState<
    Array<{ serviceType: string; priority: number | null }>
  >([]);
  const [applicationConfigVersion, setApplicationConfigVersion] = useState<
    number | undefined
  >();
  const [configError, setConfigError] = useState<string | null>(null);
  const [credentialStatus, setCredentialStatus] =
    useState<SessionCredentialStatus | null>(null);
  const [executionNode, setExecutionNode] =
    useState<ExecutionNodeContext | null>(null);
  const [serviceConfigurationPreview, setServiceConfigurationPreview] =
    useState<ServicePreviewObservation | undefined>(undefined);
  const [
    serviceConfigurationPreviewError,
    setServiceConfigurationPreviewError,
  ] = useState("");
  const servicePreviewRequests = useRef(
    new Map<string, Promise<ServiceConfigurationPreview>>(),
  );
  const [installationState, setInstallationState] = useState<
    InstallationState | undefined
  >(undefined);
  const [installationTab, setInstallationTab] = useState<
    "summary" | "plan" | "execution" | "result"
  >("summary");
  const [installationPlan, setInstallationPlan] = useState<
    InstallationPlanOperation | undefined
  >(undefined);
  const [installationBusy, setInstallationBusy] = useState(false);
  const [installationRun, setInstallationRun] = useState<
    InstallationRunOperation | undefined
  >(undefined);
  const [installationEvents, setInstallationEvents] = useState<
    InstallationEventView[]
  >([]);
  const [runProgress, setRunProgress] = useState<RunProgress | undefined>();
  const runProgressRef = useRef<RunProgress | undefined>(undefined);
  const [runPlan, setRunPlan] = useState<InstallationPlanOperation["plan"]>();
  const activeRunIdRef = useRef("");
  const [installationSubscription, setInstallationSubscription] = useState("");
  const installationSubscriptionRef = useRef("");
  const [secretOutputPackages, setSecretOutputPackages] = useState<
    SecretOutputPackagesOperation | undefined
  >();
  const [outputDelivery, setOutputDelivery] = useState<
    SecretOutputDeliveryOperation | undefined
  >();
  const [endpointPreview, setEndpointPreview] = useState<
    EndpointPreview | undefined
  >(undefined);
  const [verifiedPKI, setVerifiedPKI] = useState<VerifiedPKIView | undefined>(
    undefined,
  );
  const endpointPreviewRequest = useRef(0);
  const destination = parent ? `${parent}${separator}${name.trim()}` : root;
  const nameError = projectFolderNameError(name);
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
  useEffect(() => {
    let active = true;
    setBundleUpdate(null);
    setOrphanRun(null);
    if (projectOpen && api.chooseRuntimeBundleUpdate) {
      void api.chooseRuntimeBundleUpdate().then((next) => {
        if (active) setBundleUpdate(next);
      }).catch(() => {
        if (active) setBundleUpdate({status: "BLOCKED"} as RuntimeBundleUpdate);
      });
    }
    return () => { active = false; };
  }, [api, projectOpen, result.root, result.managed?.projectRevision]);
  const topologyAvailable =
    projectOpen &&
    (result.classification === "EMPTY_MANAGED_PROJECT" ||
      result.classification === "MANAGED_PROJECT");
  const executionReady = executionNode?.status === "READY";
  const installationView = installationDisplay(
    installationState,
    installationRun,
    runProgress,
  );
  const title = empty
    ? local.name
    : project?.name
      ? String(project.name)
      : local?.name || "Проект не открыт";
  const certificateSources = certificateSourceOptions(managed, intents);
  const visibleServiceConfigurationPreview =
    commandCount === 0 &&
    executionNode?.status === "READY" &&
    !!executionNode.runtimeDigest &&
    !!serviceConfigurationPreview &&
    serviceConfigurationPreview.root === result.root &&
    serviceConfigurationPreview.value.projectRevision ===
      managed?.projectRevision &&
    serviceConfigurationPreview.value.runtimeDigest ===
      executionNode.runtimeDigest &&
    serviceConfigurationPreview.selectionKind === executionNode.selectionKind &&
    serviceConfigurationPreview.selectedHostId ===
      executionNode.selectedHostId &&
    serviceConfigurationPreview.safeLabel === executionNode.safeLabel
      ? serviceConfigurationPreview.value
      : undefined;
  const serviceConfigurationPreviewNotice =
    !executionReady || commandCount !== 0 || visibleServiceConfigurationPreview
      ? ""
      : !executionNode?.runtimeDigest
        ? "Core-проекция недоступна: runtime узла выполнения не подтверждён. Показаны безопасные локальные значения."
        : !managed?.projectRevision
          ? "Core-проекция недоступна: ревизия проекта не определена. Показаны безопасные локальные значения."
          : serviceConfigurationPreviewError ||
            "Вычисляются значения Core для текущей сохранённой ревизии…";

  useEffect(() => {
    let live = true;
    api
      .getApplicationConfig()
      .then((value) => {
        if (!live) return;
        if (value.status === "READY" && value.config) {
          setServerTypes(value.config.serverTypes || []);
          setServiceExecutionPriorities(
            (value.config.serviceExecutionPriorities || []).map((item) => ({
              serviceType: item.serviceType,
              priority: item.priority ?? null,
            })),
          );
          setApplicationConfigVersion(value.config.schemaVersion);
          setConfigError(null);
        } else {
          setServerTypes([]);
          setApplicationConfigVersion(undefined);
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

  useEffect(() => {
    let live = true;
    setServiceConfigurationPreview(undefined);
    setServiceConfigurationPreviewError("");
    const revision = result.managed?.projectRevision;
    const runtimeDigest = executionNode?.runtimeDigest;
    if (
      !projectOpen ||
      !revision ||
      !result.root ||
      executionNode?.status !== "READY" ||
      !runtimeDigest ||
      !api.getServiceConfigurationPreview
    )
      return () => {
        live = false;
      };
    const root = result.root;
    const selectionKind = executionNode.selectionKind;
    const selectedHostId = executionNode.selectedHostId;
    const safeLabel = executionNode.safeLabel;
    const requestKey = JSON.stringify([
      root,
      revision,
      runtimeDigest,
      selectionKind,
      selectedHostId,
      safeLabel,
    ]);
    let request = servicePreviewRequests.current.get(requestKey);
    if (!request) {
      request = api.getServiceConfigurationPreview();
      servicePreviewRequests.current.set(requestKey, request);
      const pending = request;
      const clear = () => {
        if (servicePreviewRequests.current.get(requestKey) === pending)
          servicePreviewRequests.current.delete(requestKey);
      };
      void pending.then(clear, clear);
    }
    request
      .then((value) => {
        if (
          live &&
          value.projectRevision === revision &&
          value.runtimeDigest === runtimeDigest
        )
          setServiceConfigurationPreview({
            value,
            root,
            selectionKind,
            selectedHostId,
            safeLabel,
          });
      })
      .catch((reason: unknown) => {
        if (live) {
          setServiceConfigurationPreview(undefined);
          const safeCode = String(reason).match(
            /\b(SERVICE_CONFIGURATION_PREVIEW_(?:UNAVAILABLE|UNSUPPORTED|STALE|RESPONSE_INVALID|INPUT_INVALID)|PROJECT_REVISION_CHANGED|EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED)\b/,
          )?.[1];
          setServiceConfigurationPreviewError(
            `Core-проекция недоступна для текущей сохранённой ревизии.${safeCode ? ` Код: ${safeCode}.` : ""} Показаны безопасные локальные значения.`,
          );
        }
      });
    return () => {
      live = false;
    };
  }, [
    api,
    projectOpen,
    result.root,
    result.managed?.projectRevision,
    executionNode?.status,
    executionNode?.runtimeDigest,
    executionNode?.selectionKind,
    executionNode?.selectedHostId,
    executionNode?.safeLabel,
  ]);

  useEffect(() => {
    let live = true;
    if (!projectOpen || !api.getInstallationState) {
      setInstallationState(undefined);
      setInstallationPlan(undefined);
      return () => {
        live = false;
      };
    }
    api
      .getInstallationState()
      .then((value) => live && setInstallationState(value))
      .catch(() => live && setInstallationState(undefined));
    return () => {
      live = false;
    };
  }, [api, projectOpen, result.root, commandCount, executionNode?.status]);

  useEffect(() => {
    let live = true;
    const planId = installationState?.plan.planId;
    if (!planId || !api.getInstallationPlan)
      return () => {
        live = false;
      };
    api
      .getInstallationPlan(planId)
      .then((value) => live && setInstallationPlan(value))
      .catch(() => live && setInstallationPlan(undefined));
    return () => {
      live = false;
    };
  }, [api, installationState?.plan.planId]);

  const clearDraft = () => {
    setEdit(null);
    setEditError(null);
    setSessionId("");
    setCommandCount(0);
    setIntents([]);
    setReviewOpen(false);
    setServiceFormEpoch((current) => current + 1);
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
    setInstallationTab("summary");
    setInstallationPlan(undefined);
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
    if (nameError) return;
    setCreating(true);
    setCreateError(null);
    try {
      const next = await api.createProject({
        projectRoot: destination,
        displayName: name,
        compatibilitySourceId: "default",
      });
      if (next.status !== "OPEN") {
        setCreateError(
          next.error || {
            code: "PROJECT_CREATE_FAILED",
            message: "Не удалось создать проект.",
          },
        );
        return;
      }
      setResult(next);
      clearRefreshFailure();
      resetTopologySelection();
      setProjectDialog(false);
      setPage("project");
      setName("");
      setRoot("");
      setParent("");
      setSeparator("\\");
      setNameRequired(false);
    } catch {
      setCreateError({
        code: "PROJECT_CREATE_UNAVAILABLE",
        message: "Не удалось создать проект. Попробуйте снова.",
      });
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
  const refreshBundleUpdate = async () => {
    if (!api.chooseRuntimeBundleUpdate) return;
    setBundleBusy(true);
    try { setBundleUpdate(await api.chooseRuntimeBundleUpdate()); }
    finally { setBundleBusy(false); }
  };
  const confirmBundleUpdate = async () => {
    if (!api.confirmRuntimeBundleUpdate || !bundleUpdate?.previewId) return;
    setBundleBusy(true);
    try {
      const next = await api.confirmRuntimeBundleUpdate(bundleUpdate.previewId);
      setBundleUpdate(next);
      if (next.status === "UPDATED" && result.root) setResult(await api.openProject(result.root));
    } finally { setBundleBusy(false); }
  };
  const inspectOrphanRun = async () => {
    if (!api.inspectOrphanRun) return;
    setBundleBusy(true);
    try {
      const inspected = await api.inspectOrphanRun();
      setOrphanRun(inspected);
      if (
        ["RESOLVED", "NONE"].includes(inspected.status) &&
        api.chooseRuntimeBundleUpdate
      ) {
        setBundleUpdate(await api.chooseRuntimeBundleUpdate());
      }
    }
    finally { setBundleBusy(false); }
  };
  const cancelOrphanRun = async () => {
    if (!api.cancelOrphanRun || !orphanRun?.recoveryId) return;
    setBundleBusy(true);
    try {
      setOrphanRun(await api.cancelOrphanRun(orphanRun.recoveryId));
      if (api.chooseRuntimeBundleUpdate) setBundleUpdate(await api.chooseRuntimeBundleUpdate());
    } finally { setBundleBusy(false); }
  };
  const refreshInstallationState = async () => {
    if (!api.getInstallationState) return;
    const next = await api.getInstallationState();
    setInstallationState(next);
  };
  const createInstallationPlan = async (deploymentOrder: string[]) => {
    if (!api.createInstallationPlan) return;
    setInstallationBusy(true);
    try {
      const operation = await api.createInstallationPlan(deploymentOrder);
      setInstallationPlan(operation);
      await refreshInstallationState();
      setInstallationTab("plan");
    } finally {
      setInstallationBusy(false);
    }
  };
  const approveInstallationPlan = async (
    planId: string,
    acknowledgements: string[],
  ) => {
    if (!api.approveInstallationPlan) return;
    setInstallationBusy(true);
    try {
      const operation = await api.approveInstallationPlan(
        planId,
        acknowledgements,
      );
      setInstallationPlan(operation);
      await refreshInstallationState();
    } finally {
      setInstallationBusy(false);
    }
  };
  const startApprovedInstallation = async (planId: string) => {
    if (!api.startApprovedInstallation) return;
    setInstallationBusy(true);
    try {
      const operation = await api.startApprovedInstallation(planId);
      if (operation.status === "BLOCKED" && api.getInstallationPlan) {
        setInstallationPlan(await api.getInstallationPlan(planId));
      }
      setInstallationRun(operation);
      setInstallationEvents([]);
      setRunPlan(operation.run ? installationPlan?.plan : undefined);
      activeRunIdRef.current = operation.run?.runId || "";
      runProgressRef.current = operation.run
        ? beginRunProgress(operation.run.runId, installationPlan?.plan)
        : undefined;
      setRunProgress(runProgressRef.current);
      setInstallationTab("execution");
      if (operation.run && api.subscribeInstallationRun) {
        if (
          installationSubscriptionRef.current &&
          api.unsubscribeInstallationRun
        ) {
          await api.unsubscribeInstallationRun(
            installationSubscriptionRef.current,
          );
          installationSubscriptionRef.current = "";
        }
        const subscription = await api.subscribeInstallationRun(
          operation.run.runId,
          0,
        );
        installationSubscriptionRef.current = subscription.subscriptionId || "";
        setInstallationSubscription(installationSubscriptionRef.current);
      }
      await refreshInstallationState();
    } finally {
      setInstallationBusy(false);
    }
  };
  const cancelInstallationRun = async (runId: string) => {
    if (!api.cancelInstallationRun) return;
    setInstallationBusy(true);
    try {
      setInstallationRun(await api.cancelInstallationRun(runId));
    } finally {
      setInstallationBusy(false);
    }
  };
  const setOutputEncryptionPassword = async (
    password: string,
    confirm: string,
  ) => {
    if (!api.setSecretOutputEncryptionPassword)
      throw new Error("SECRET_OUTPUT_UNAVAILABLE");
    await api.setSecretOutputEncryptionPassword(password, confirm);
    if (installationPlan?.plan?.id && api.getInstallationPlan) {
      setInstallationPlan(
        await api.getInstallationPlan(installationPlan.plan.id),
      );
    }
  };
  const refreshSecretOutputs = useCallback(async () => {
    if (!api.listPendingSecretOutputs) return;
    try {
      setSecretOutputPackages(await api.listPendingSecretOutputs());
    } catch {
      setSecretOutputPackages(secretOutputListingUnavailable());
    }
  }, [api]);
  const deliverSecretOutput = useCallback(
    async (packageId: string) => {
      if (!api.deliverPendingSecretOutput) return;
      try {
        setOutputDelivery(await api.deliverPendingSecretOutput(packageId));
      } catch {
        setOutputDelivery(secretOutputDeliveryUnavailable());
        return;
      }
      if (api.listPendingSecretOutputs) {
        try {
          setSecretOutputPackages(await api.listPendingSecretOutputs());
        } catch {
          setSecretOutputPackages(secretOutputListingUnavailable());
        }
      }
    },
    [api],
  );
  const collectAndDeliverSecretOutputs = useCallback(async (runId: string) => {
    if (!api.listPendingSecretOutputs) return;
    let pending: SecretOutputPackagesOperation;
    try {
      pending = await api.listPendingSecretOutputs();
    } catch {
      setSecretOutputPackages(secretOutputListingUnavailable());
      return;
    }
    setSecretOutputPackages(pending);
    const plan = installationPlan?.plan;
    if (
      pending.status !== "READY" ||
      !plan?.secretOutputEncryptionRequired ||
      !plan.secretOutputEncryptionPasswordPresent
    )
      return;
    const candidates = [...(pending.packages || [])];
    let cursor = pending.nextCursor;
    const seen = new Set<string>();
    for (let page = 1; cursor && page < 128; page++) {
      if (seen.has(cursor)) break;
      seen.add(cursor);
      let next: SecretOutputPackagesOperation;
      try {
        next = await api.listPendingSecretOutputs(cursor);
      } catch {
        setSecretOutputPackages(secretOutputListingUnavailable());
        return;
      }
      if (next.status !== "READY") break;
      candidates.push(...(next.packages || []));
      cursor = next.nextCursor;
    }
    for (const item of candidates) {
      if (item.sourceRunId !== runId) continue;
      if (!api.deliverPendingSecretOutput) break;
      try {
        const delivery = await api.deliverPendingSecretOutput(item.packageId);
        setOutputDelivery(delivery);
      } catch {
        setOutputDelivery(secretOutputDeliveryUnavailable());
        return;
      }
    }
    try {
      setSecretOutputPackages(await api.listPendingSecretOutputs());
    } catch {
      setSecretOutputPackages(secretOutputListingUnavailable());
    }
  }, [api, installationPlan?.plan]);
  useEffect(() => {
    if (!api.subscribeInstallationRunEvents) return undefined;
    return api.subscribeInstallationRunEvents(
      (value: {
        subscriptionId?: string;
        event?: InstallationEventView;
        errorCode?: string;
      }) => {
        if (!value.event) {
          if (
            value.errorCode === "OBSERVER_HISTORY_GAP" &&
            activeRunIdRef.current &&
            api.getInstallationRun
          ) {
            void api
              .getInstallationRun(activeRunIdRef.current)
              .then(setInstallationRun)
              .catch(() => {});
          }
          return;
        }
        const subscriptionMatches =
          value.subscriptionId === installationSubscriptionRef.current;
        if (
          !subscriptionMatches &&
          value.event.runId !== activeRunIdRef.current
        )
          return;
        setInstallationEvents((current) =>
          current.some((event) => event.sequence === value.event!.sequence)
            ? current
            : [...current, value.event!],
        );
        const nextProgress = runProgressRef.current
          ? observeRunEvent(runProgressRef.current, value.event)
          : undefined;
        if (nextProgress) {
          runProgressRef.current = nextProgress;
          setRunProgress(nextProgress);
        }
        if (
          ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
            value.event.status,
          ) &&
          api.getInstallationRun
        ) {
          api
            .getInstallationRun(value.event.runId)
            .then(setInstallationRun)
            .catch(() => {});
          void collectAndDeliverSecretOutputs(value.event.runId).catch(() =>
            setOutputDelivery(secretOutputDeliveryUnavailable()),
          );
        }
      },
    );
  }, [api, installationSubscription, collectAndDeliverSecretOutputs]);
  useEffect(
    () => () => {
      if (installationSubscriptionRef.current && api.unsubscribeInstallationRun)
        void api.unsubscribeInstallationRun(
          installationSubscriptionRef.current,
        );
    },
    [api],
  );
  useEffect(() => {
    if (
      !installationSubscription ||
      !api.unsubscribeInstallationRun ||
      !["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(
        installationRun?.run?.state || "",
      )
    )
      return;
    void api.unsubscribeInstallationRun(installationSubscription);
    installationSubscriptionRef.current = "";
    setInstallationSubscription("");
  }, [api, installationSubscription, installationRun?.run?.state]);
  useEffect(() => {
    if (
      !["execution", "result"].includes(installationTab) ||
      !installationRun?.run ||
      !api.getInstallationRun
    )
      return;
    api
      .getInstallationRun(installationRun.run.runId)
      .then(setInstallationRun)
      .catch(() => {});
  }, [api, installationRun?.run?.runId, installationTab]);
  const chooseExportParent = async () => {
    if (!api.chooseProjectExportParent) return;
    const selected = await api.chooseProjectExportParent();
    if (selected) setExportParent(selected);
  };
  const previewExport = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!api.planProjectExport) return;
    setExportBusy(true);
    try {
      setExportOperation(await api.planProjectExport(exportParent, exportName));
    } finally {
      setExportBusy(false);
    }
  };
  const commitExport = async () => {
    const digest = exportOperation?.plan?.planDigest;
    if (!api.commitProjectExport || !digest) return;
    setExportBusy(true);
    try {
      const next = await api.commitProjectExport(digest);
      setExportOperation(next);
      if (next.status === "EXPORTED") {
        setExportParent("");
        setExportName("");
      }
    } finally {
      setExportBusy(false);
    }
  };
  const openExport = () => {
    setExportOperation(null);
    setExportDialog(true);
  };
  const reopenExport = async () => {
    const exportedRoot = exportOperation?.result?.destinationRoot;
    if (!exportedRoot) return;
    setExportBusy(true);
    try {
      const next = await api.openProject(exportedRoot);
      if (next.status === "OPEN") {
        setResult(next);
        clearRefreshFailure();
        resetTopologySelection();
        setExportDialog(false);
        setPage("project");
        return;
      }
      setExportOperation((current) =>
        current
          ? {
              ...current,
              error: next.error ?? {
                code: "EXPORTED_PROJECT_OPEN_FAILED",
                message: "Экспорт создан, но открыть его не удалось.",
              },
            }
          : current,
      );
    } finally {
      setExportBusy(false);
    }
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
  const amendConfigurationIntent = async (
    previous: ConfigurationIntent,
    replacement: ConfigurationIntent | null,
  ): Promise<boolean> => {
    const index = intents.indexOf(previous);
    if (!sessionId || index < 0) {
      setEditError({
        code: "EDIT_COMMAND_CONFLICT",
        message:
          "Черновик изменился. Повторите действие после обновления страницы.",
      });
      return false;
    }
    setEditBusy(true);
    try {
      const next = await api.amendServiceConfigurationDraft(
        sessionId,
        index,
        previous,
        replacement,
      );
      if (replacement === null && next.status === "DISCARDED" && !next.error) {
        clearDraft();
        endpointPreviewRequest.current += 1;
        setEndpointPreview({ status: "STALE" });
        setVerifiedPKI({ status: "STALE" });
        return true;
      }
      if (next.error || !next.session) {
        setEditError(
          next.error || {
            code: "EDIT_COMMAND_BLOCKED",
            message: "Не удалось обновить изменение в черновике.",
          },
        );
        return false;
      }
      setEdit(next);
      setEditError(null);
      setCommandCount(next.session.commandCount);
      setIntents((current) => {
        const updated = [...current];
        if (replacement === null) updated.splice(index, 1);
        else updated[index] = replacement;
        return updated;
      });
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
        setInstallationState(undefined);
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
        setInstallationState(undefined);
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
    // Do not let a previously loaded PKI projection mask the result of this
    // verification attempt or keep old identity/SAN evidence visible.
    setVerifiedPKI(undefined);
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
    if (api.getExecutionNodeContext)
      setExecutionNode(await api.getExecutionNodeContext());
    setResult(
      (current) =>
        ({ ...current, verification: { status: "UNVERIFIED" } }) as OpenResult,
    );
    return status;
  };
  const clearSessionCredential = async () => {
    if (!api.clearSessionCredential)
      throw new Error("SESSION_CREDENTIAL_UNAVAILABLE");
    const status = await api.clearSessionCredential();
    setCredentialStatus(status);
    if (api.getExecutionNodeContext)
      setExecutionNode(await api.getExecutionNodeContext());
    setResult(
      (current) =>
        ({ ...current, verification: { status: "UNVERIFIED" } }) as OpenResult,
    );
    return status;
  };
  const setPKIStorePassword = async (value: string) => {
    if (!api.setPKIStorePassword)
      throw new Error("PKI_STORE_PASSWORD_UNAVAILABLE");
    const status = await api.setPKIStorePassword(value);
    setCredentialStatus(status);
    return status;
  };
  const getPendingRuntimeSecretDescriptors = async (
    serviceDeployment: string,
  ) => {
    if (!api.getPendingRuntimeSecretDescriptors)
      throw new Error("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE");
    return api.getPendingRuntimeSecretDescriptors(serviceDeployment);
  };
  const setPendingDeploymentRuntimeSecretValues = async (
    input: Parameters<
      NonNullable<ProjectBackend["setPendingDeploymentRuntimeSecretValues"]>
    >[0],
  ) => {
    if (!api.setPendingDeploymentRuntimeSecretValues)
      throw new Error("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE");
    await api.setPendingDeploymentRuntimeSecretValues(input);
  };

  const choosePendingDeploymentRuntimeSecretFile = async (
    input: Parameters<
      NonNullable<ProjectBackend["choosePendingDeploymentRuntimeSecretFile"]>
    >[0],
  ) => {
    if (!api.choosePendingDeploymentRuntimeSecretFile)
      throw new Error("SECRET_FILE_IMPORT_UNAVAILABLE");
    return api.choosePendingDeploymentRuntimeSecretFile(input);
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
    const refreshed = await api
      .getExecutionNodeContext?.()
      .catch(() => undefined);
    setExecutionNode((current) =>
      current
        ? {
            ...(refreshed || current),
            status: readiness.status,
            runtimeDigest: refreshed?.runtimeDigest,
          }
        : current,
    );
    return readiness;
  };
  const probeExecutionNodeHostKey = async (): Promise<HostKeyProbeResult> => {
    if (!api.probeExecutionNodeHostKey)
      throw new Error("EXECUTION_NODE_HOST_KEY_PROBE_UNAVAILABLE");
    return api.probeExecutionNodeHostKey();
  };
  const approveExecutionNodeHostKey = async (
    probeId: string,
  ): Promise<HostKeyProbeResult> => {
    if (!api.approveExecutionNodeHostKey)
      throw new Error("EXECUTION_NODE_HOST_KEY_APPROVAL_UNAVAILABLE");
    const result = await api.approveExecutionNodeHostKey(probeId);
    if (result.status === "APPROVED" && api.getExecutionNodeContext)
      setExecutionNode(await api.getExecutionNodeContext());
    return result;
  };
  const declineExecutionNodeHostKey = async (): Promise<HostKeyProbeResult> => {
    if (!api.declineExecutionNodeHostKey)
      throw new Error("EXECUTION_NODE_HOST_KEY_APPROVAL_UNAVAILABLE");
    const result = await api.declineExecutionNodeHostKey();
    if (api.getExecutionNodeContext)
      setExecutionNode(await api.getExecutionNodeContext());
    return result;
  };
  const probeTargetHostKey = async (
    hostId: string,
  ): Promise<HostKeyProbeResult> => {
    if (!api.probeTargetHostKey)
      throw new Error("TARGET_HOST_KEY_PROBE_UNAVAILABLE");
    return api.probeTargetHostKey(hostId);
  };
  const approveTargetHostKey = async (
    probeId: string,
  ): Promise<HostKeyProbeResult> => {
    if (!api.approveTargetHostKey)
      throw new Error("TARGET_HOST_KEY_APPROVAL_UNAVAILABLE");
    return api.approveTargetHostKey(probeId);
  };
  const declineTargetHostKey = async (): Promise<HostKeyProbeResult> => {
    if (!api.declineTargetHostKey)
      throw new Error("TARGET_HOST_KEY_APPROVAL_UNAVAILABLE");
    return api.declineTargetHostKey();
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
    const refreshed = await api
      .getExecutionNodeContext?.()
      .catch(() => undefined);
    setExecutionNode((current) =>
      current
        ? {
            ...(refreshed || current),
            status:
              preparation.status === "PREPARED" ? "READY" : preparation.status,
            runtimeDigest: refreshed?.runtimeDigest,
          }
        : current,
    );
    return preparation;
  };

  return (
    <div className="shell">
      <aside className="app-sidebar">
        <div className="brand">
          Platform
          <br />
          <span>Installer</span>
        </div>
        <nav aria-label="Основная навигация">
          {navigation
            .filter((item) =>
              [
                "project",
                "servers",
                "topology",
                "certificates",
                "services",
                "installation",
                "logs",
                "help",
                "about",
                "settings",
              ].includes(item.id),
            )
            .map((item) => {
              const enabled =
                item.id === "project" ||
                (item.id === "servers" && projectOpen) ||
                (item.id === "topology" && topologyAvailable) ||
                (item.id === "certificates" && topologyAvailable) ||
                (item.id === "services" && topologyAvailable) ||
                (item.id === "installation" && projectOpen) ||
                item.id === "logs" ||
                item.id === "help" ||
                item.id === "about" ||
                item.id === "settings";
              return (
                <button
                  key={item.id}
                  className={
                    item.id === page ? "active" : enabled ? undefined : "future"
                  }
                  disabled={!enabled}
                  aria-current={item.id === page ? "page" : undefined}
                  onClick={() => {
                    if (
                      item.id !== "project" &&
                      item.id !== "servers" &&
                      item.id !== "topology" &&
                      item.id !== "certificates" &&
                      item.id !== "services" &&
                      item.id !== "installation" &&
                      item.id !== "logs" &&
                      item.id !== "help" &&
                      item.id !== "about" &&
                      item.id !== "settings"
                    )
                      return;
                    setPage(item.id as Page);
                    if (item.id === "services") setServicesView("list");
                  }}
                >
                  {item.label}
                </button>
              );
            })}
        </nav>
      </aside>
      <main className="app-main">
        <header className="app-header">
          <div className="app-project-identity">
            <strong>{title}</strong>
            <span>
              {result.root || "Выберите существующий проект или создайте новый"}
            </span>
          </div>
          <div className="app-header-statuses">
            {projectOpen && (
              <div className={sessionId ? "unsaved" : "readonly"}>
                {sessionId ? "Есть несохранённые изменения" : "Сохранено"}
              </div>
            )}
            {projectOpen && (
              <div className="readonly">
                {verificationLabel(verification.status)}
              </div>
            )}
          </div>
          {projectOpen && (
            <button
              className="execution-node-badge"
              aria-label="Открыть узел выполнения"
              onClick={() => setPage("servers")}
              title="Открыть узел выполнения на странице «Серверы»"
            >
              Узел выполнения:{" "}
              {executionNodeStatusLabel(
                executionNode?.status || "NOT_CONFIGURED",
              )}
              {executionNode?.safeLabel ? ` · ${executionNode.safeLabel}` : ""}
            </button>
          )}
          {projectOpen && (
            <button
              type="button"
              className={`installation-global-status ${installationView.tone}`}
              onClick={() => {
                setPage("installation");
                setInstallationTab(
                  installationView.stage === "result"
                    ? "result"
                    : installationView.stage === "execution"
                      ? "execution"
                      : "summary",
                );
              }}
              aria-label={`Открыть установку: ${installationView.label}${installationView.percent === undefined ? "" : `, ${installationView.percent}%`}`}
            >
              <strong>
                {installationView.label}
                {installationView.percent === undefined
                  ? ""
                  : ` · ${installationView.percent}%`}
              </strong>
              <small>{installationView.detail}</small>
            </button>
          )}
          <div className="app-header-actions">
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
          {api.exitApplication && (
            <button
              className="outline"
              type="button"
              disabled={hostExitStatus !== ""}
              onClick={() => {
                void api
                  .exitApplication!()
                  .then((exit) => {
                    setHostExitStatus(
                      exit.status === "EXIT_AFTER_RUN"
                        ? "Приложение завершит работу после текущего выполнения."
                        : "Приложение завершает работу.",
                    );
                  })
                  .catch(() =>
                    setHostExitStatus("Не удалось завершить приложение."),
                  );
              }}
            >
              Выйти
            </button>
          )}
          {hostExitStatus && (
            <span role="status" aria-live="polite">
              {hostExitStatus}
            </span>
          )}
        </div>
        </header>
        <section className="banner app-banner">
          Сохранение выполняется локально. Проверка последней сохранённой
          ревизии через Core запускается отдельно.
        </section>
        <div className="workspace-content">
          {refreshRequired && (
            <section className="card refresh-required" role="alert">
              <h2>Проект сохранён, но текущее представление не обновлено</h2>
              <p>
                Канонические файлы уже записаны. Повторное сохранение
                недоступно, пока проект не будет безопасно перечитан.
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
          {!loading &&
            !creating &&
            result.status === "NO_PROJECT" &&
            page === "project" && (
              <section className="empty card">
                <h1>Создайте или откройте проект</h1>
                <p>
                  Новый проект содержит только метаданные и закреплённые версии
                  из проверенного локального пакета.
                </p>
                <button onClick={() => setProjectDialog(true)}>
                  Создать проект
                </button>
                <button className="outline" onClick={open}>
                  Открыть папку проекта
                </button>
              </section>
            )}
          {!loading &&
            !creating &&
            result.status === "ERROR" &&
            page === "project" && (
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
              catalogStatus={result.catalog?.status}
              verification={verification}
              local={local}
              onClose={close}
              onServers={() => setPage("servers")}
              closeDisabled={!!sessionId || refreshRequired}
              exportAvailable={
                !sessionId &&
                !refreshRequired &&
                !!api.planProjectExport &&
                !!api.commitProjectExport
              }
              onExport={openExport}
              bundleUpdate={bundleUpdate}
              orphanRun={orphanRun}
              bundleBusy={bundleBusy}
              onRefreshBundle={refreshBundleUpdate}
              onConfirmBundle={confirmBundleUpdate}
              onInspectOrphan={inspectOrphanRun}
              onCancelOrphan={cancelOrphanRun}
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
              onProbeExecutionNodeHostKey={probeExecutionNodeHostKey}
              onApproveExecutionNodeHostKey={approveExecutionNodeHostKey}
              onDeclineExecutionNodeHostKey={declineExecutionNodeHostKey}
              onProbeTargetHostKey={probeTargetHostKey}
              onApproveTargetHostKey={approveTargetHostKey}
              onDeclineTargetHostKey={declineTargetHostKey}
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
                  intent.operation ===
                    "ReconcileHostScopedDeploymentPlacement" ||
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
                setSelectedServiceMember("");
                setFocusServiceMemberSettings(false);
                setServicesView("detail");
                setPage("services");
              }}
              onConfigureMember={(deploymentId, memberId) => {
                setSelectedTopologyDeployment(deploymentId);
                setSelectedServiceDeployment(deploymentId);
                setSelectedServiceMember(memberId);
                setFocusServiceMemberSettings(true);
                setServicesView("detail");
                setPage("services");
              }}
              preview={endpointPreview}
              verificationStatus={verification.status}
            />
          )}
          {!loading && !creating && projectOpen && page === "services" && (
            <ServicesPage
              key={serviceFormEpoch}
              managed={managed}
              catalog={result.catalog}
              effectivePreview={visibleServiceConfigurationPreview}
              corePreviewNotice={serviceConfigurationPreviewNotice}
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
              focusMemberSettings={focusServiceMemberSettings}
              onSelectedMemberChange={setSelectedServiceMember}
              onOpenDeployment={(deploymentId) => {
                setSelectedServiceDeployment(deploymentId);
                setSelectedServiceMember("");
                setFocusServiceMemberSettings(false);
                setServicesView("detail");
              }}
              onBackToList={() => {
                setServicesView("list");
                setSelectedServiceDeployment("");
                setSelectedServiceMember("");
                setFocusServiceMemberSettings(false);
              }}
              onOpenTopology={() => setPage("topology")}
              onAmend={amendConfigurationIntent}
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
              onGetPendingRuntimeSecretDescriptors={
                getPendingRuntimeSecretDescriptors
              }
              onSetPendingDeploymentRuntimeSecretValues={
                setPendingDeploymentRuntimeSecretValues
              }
              onChoosePendingDeploymentRuntimeSecretFile={
                choosePendingDeploymentRuntimeSecretFile
              }
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
              credentialStatus={credentialStatus}
              onAppend={appendStructuralIntent}
              onSetPKIStorePassword={setPKIStorePassword}
              onReview={review}
              onDiscard={discard}
              onVerify={verify}
              onReturnToServices={
                certificateReturn
                  ? () => {
                      setSelectedServiceDeployment(
                        certificateReturn.deploymentId,
                      );
                      setSelectedServiceMember(
                        certificateReturn.memberId || "",
                      );
                      setServicesView("detail");
                      setPage("services");
                      setCertificateReturn(null);
                    }
                  : undefined
              }
            />
          )}
          {!loading && !creating && projectOpen && page === "installation" && (
            <InstallationPage
              state={installationState}
              draftActive={!!sessionId || refreshRequired}
              tab={installationTab}
              onTabChange={setInstallationTab}
              onOpenServers={() => setPage("servers")}
              plan={installationPlan}
              busy={installationBusy}
              onCreatePlan={createInstallationPlan}
              serviceDeployments={Object.values(
                result.managed?.deployments || {},
              ).map((item) => ({
                deploymentId: item.deploymentId,
                serviceType: item.serviceType,
              }))}
              serviceExecutionPriorities={serviceExecutionPriorities}
              onApprovePlan={approveInstallationPlan}
              run={installationRun}
              runPlan={runPlan}
              runProgress={runProgress}
              events={installationEvents}
              credentialStatus={credentialStatus}
              onSetOutputEncryptionPassword={setOutputEncryptionPassword}
              secretOutputPackages={secretOutputPackages}
              outputDelivery={outputDelivery}
              onRefreshSecretOutputs={() => void refreshSecretOutputs()}
              onDeliverSecretOutput={(packageId) =>
                void deliverSecretOutput(packageId)
              }
              onStart={startApprovedInstallation}
              onCancel={cancelInstallationRun}
            />
          )}
          {!loading && !creating && (
            <UtilityPages
              page={page}
              events={installationEvents}
              runId={installationRun?.run?.runId}
              configVersion={applicationConfigVersion}
              serverTypes={serverTypes}
              configError={configError}
              onNavigate={setPage}
            />
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
                      setCreateError(null);
                    }}
                    autoFocus
                    aria-invalid={nameRequired || !!nameError}
                  />
                </label>
                {nameRequired && (
                  <p className="field-error" role="alert">
                    Заполните «Название проекта»: оно задаёт новую папку
                    проекта.
                  </p>
                )}
                {nameError && (
                  <p className="field-error" role="alert">
                    {nameError}
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
                    Выбрать родительскую папку
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
                {createError && (
                  <p className="field-error" role="alert">
                    <code>{createError.code}</code> {createError.message}
                  </p>
                )}
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
          {exportDialog && (
            <ProjectExportDialog
              parent={exportParent}
              name={exportName}
              operation={exportOperation}
              busy={exportBusy}
              onParentChange={setExportParent}
              onNameChange={setExportName}
              onChooseParent={chooseExportParent}
              onPreview={previewExport}
              onCommit={commitExport}
              onReopen={reopenExport}
              onClose={() => !exportBusy && setExportDialog(false)}
            />
          )}
        </div>
      </main>
    </div>
  );
}

function ProjectPage({
  catalogStatus,
  bundleUpdate,
  orphanRun,
  bundleBusy,
  onRefreshBundle,
  onConfirmBundle,
  onInspectOrphan,
  onCancelOrphan,
  empty,
  snapshot,
  managed,
  verification,
  local,
  onClose,
  onServers,
  closeDisabled,
  exportAvailable,
  onExport,
}: {
  catalogStatus?: string;
  bundleUpdate: RuntimeBundleUpdate | null;
  orphanRun: OrphanRunRecovery | null;
  bundleBusy: boolean;
  onRefreshBundle: () => void;
  onConfirmBundle: () => void;
  onInspectOrphan: () => void;
  onCancelOrphan: () => void;
  empty: boolean;
  snapshot: OpenResult["snapshot"];
  managed: OpenResult["managed"];
  verification: NonNullable<OpenResult["verification"]>;
  local: OpenResult["project"];
  onClose: () => void;
  onServers: () => void;
  closeDisabled: boolean;
  exportAvailable: boolean;
  onExport: () => void;
}) {
  const bundleCard = (
    <section className="card" aria-label="Набор установки">
      <h2>Набор установки</h2>
      {catalogStatus !== "READY" && <p role="status">Нужна перепривязка набора установки: сохранённые данные проекта доступны, но текущий проверенный набор не соответствует проекту или отсутствует. Проверка Core и новый план пока недоступны.</p>}
      <p>Поместите полученный набор целиком в папку bundle внутри проекта. Обнаружение не меняет привязку.</p>
      <button className="outline" onClick={onRefreshBundle} disabled={bundleBusy}>Проверить новый набор</button>
      {bundleUpdate?.status === "NOT_FOUND" && <p>Новый набор не найден.</p>}
      {bundleUpdate?.status === "UNCHANGED" && <p>Набор уже привязан к проекту.</p>}
      {bundleUpdate?.status === "PREVIEW" && <>
        <dl>
          <dt>Текущий digest</dt><dd>{bundleUpdate.currentArtifactDigest}</dd>
          <dt>Новый digest</dt><dd>{bundleUpdate.newArtifactDigest}</dd>
          <dt>Каталог</dt><dd>{bundleUpdate.newCatalogDigest}</dd>
          <dt>Версия набора / Core</dt><dd>{bundleUpdate.bundleVersion} / {bundleUpdate.coreVersion}</dd>
        </dl>
        <p>После привязки прежняя проверка и одобренный план станут недействительными. Перед установкой заново подготовьте узел, проверьте проект и создайте план.</p>
        <button onClick={onConfirmBundle} disabled={bundleBusy}>Привязать</button>
      </>}
      {bundleUpdate?.status === "UPDATED" && <p>Новый набор привязан. Подготовьте узел выполнения и создайте свежий план.</p>}
      {bundleUpdate?.status === "BLOCKED" && <p role="alert">Привязка сейчас недоступна: {bundleUpdate.error?.message || bundleUpdate.error?.code || "проверьте набор и состояние выполнения"}.</p>}
      {bundleUpdate?.status === "BLOCKED" && bundleUpdate.error?.code && <p className="muted">Код: {bundleUpdate.error.code}</p>}
      {bundleUpdate?.status === "PUBLISHED_NOT_BOUND" && <p role="alert">Набор опубликован, но проект не перепривязан. Проверьте проект и повторите операцию.</p>}
      {bundleUpdate?.status === "BOUND_REFRESH_REQUIRED" && <p role="alert">Привязка записана, но проект нужно открыть заново.</p>}
      {bundleUpdate?.error?.code === "INSTALLATION_RUN_ACTIVE" && <button className="outline" onClick={onInspectOrphan} disabled={bundleBusy}>Проверить прежний запуск</button>}
      {orphanRun && orphanRun.status !== "NONE" && <div className="orphan-run-status" role={orphanRun.status === "RESOLVED" ? "status" : "alert"}>
        {orphanRun.status === "RESOLVED" ? <p>
          {orphanRun.runState === "FAILED"
            ? "Прежний запуск завершился с ошибкой. Его статус подтверждён; повторное выполнение не запускалось."
            : `Прежний запуск подтверждён как завершённый (${orphanRun.runState || "terminal"}). Повторное выполнение не запускалось.`}
          {orphanRun.runId ? ` Run ID: ${orphanRun.runId}.` : ""}
        </p> : orphanRun.status === "FOUND" ? <p>
          Найден прежний активный запуск {orphanRun.runId} ({orphanRun.runState}). Новый запуск заблокирован. Аварийная отмена сохранит журнал и результат.
        </p> : orphanRun.status === "UNAVAILABLE" ? <p>
          Не удалось проверить прежний запуск на исходном узле. Убедитесь, что узел доступен, SSH-сеанс действителен и ключ узла подтверждён. Блокировка сохранена.
        </p> : orphanRun.status === "UNKNOWN" ? <p>
          Состояние прежнего запуска неизвестно. Блокировка сохранена; не удаляйте локальную запись и не запускайте план повторно.
        </p> : orphanRun.status === "CURRENT" ? <p>
          Запуск принадлежит текущему сеансу. Следите за ним на странице «Установка»; повторный запуск недоступен.
        </p> : orphanRun.status === "CANCELLING" ? <p>
          Отмена прежнего запуска ещё не подтверждена. Блокировка сохраняется.
        </p> : <p>
          {orphanRun.error?.message || "Не удалось безопасно проверить прежний запуск."}
          {orphanRun.error?.code ? ` Код: ${orphanRun.error.code}.` : ""}
        </p>}
        {orphanRun.status === "FOUND" && <button onClick={onCancelOrphan} disabled={bundleBusy}>Снять блокировку запуска</button>}
      </div>}
    </section>
  );
  if (empty && local)
    return (
      <>
        <section className="title">
          <div>
            <h1>Проект ещё не настроен</h1>
            <p>
              Это корректный проект только с метаданными. Добавьте серверы,
              затем проверьте и сохраните проект.
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
          <Stat label="Развёртывания / Сервисы" value={0} />
          <Stat label="Выполнения" value={0} />
          <Stat label="Инвентарь" value="Не создан" />
        </section>
        <section className="card">
          <h2>Сведения проекта</h2>
          <dl>
            <dt>Название</dt>
            <dd>{local.name}</dd>
            <dt>Project ID</dt>
            <dd>{local.id}</dd>
            <dt>Источник совместимости</dt>
            <dd>{local.source?.bundleDigest}</dd>
          </dl>
          <button onClick={onServers}>Добавить первый сервер</button>
          <button
            className="outline"
            onClick={onExport}
            disabled={!exportAvailable}
          >
            Экспортировать проект
          </button>
        </section>
        {bundleCard}
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
          <p>Сохранённые поля проекта, управляемые инсталлером.</p>
        </div>
        <button className="outline" onClick={onClose} disabled={closeDisabled}>
          Закрыть проект
        </button>
      </section>
      <section className="grid">
        <Stat
          label="Серверы"
          value={managed ? count(managed.servers) : "Нет данных"}
        />
        <Stat
          label="Развёртывания"
          value={managed ? count(managed.deployments) : "Нет данных"}
        />
        <Stat
          label="Профили сертификатов"
          value={managed ? count(managed.pki?.profiles) : "Нет данных"}
        />
        <Stat
          label="Замечания проверки"
          value={
            snapshot?.projectRevision === managed?.projectRevision &&
            ["VERIFIED", "INVALID"].includes(verification.status) &&
            snapshot?.findings
              ? snapshot.findings.length
              : "Не проверено"
          }
        />
      </section>
      <section className="card">
        <h2>Состояние проекта</h2>
        <dl>
          <dt>Статус</dt>
          <dd>{verificationLabel(verification.status)}</dd>
          <dt>Ревизия</dt>
          <dd>{managed?.projectRevision || snapshot?.projectRevision}</dd>
        </dl>
        {verification.error && (
          <p className="field-error" role="alert">
            {verificationErrorMessage(verification.error.code)}
          </p>
        )}
        <button onClick={onServers}>Открыть серверы</button>
        <button
          className="outline"
          onClick={onExport}
          disabled={!exportAvailable}
        >
          Экспортировать проект
        </button>
      </section>
      {bundleCard}
    </>
  );
}

function ProjectExportDialog({
  parent,
  name,
  operation,
  busy,
  onParentChange,
  onNameChange,
  onChooseParent,
  onPreview,
  onCommit,
  onReopen,
  onClose,
}: {
  parent: string;
  name: string;
  operation: ProjectExportOperationResult | null;
  busy: boolean;
  onParentChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onChooseParent: () => void;
  onPreview: (event: React.FormEvent) => void;
  onCommit: () => void;
  onReopen: () => void;
  onClose: () => void;
}) {
  const plan = operation?.plan;
  const result = operation?.result;
  const canPreview = !!parent && !!name.trim() && !busy && !plan;
  return (
    <div className="modal" role="presentation">
      <form
        className="card dialog review-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-export-title"
        onSubmit={onPreview}
      >
        <h1 id="project-export-title">Экспорт проекта</h1>
        {!plan && !result && (
          <>
            <p>
              Будет создана новая папка с переносимой конфигурацией проекта.
              Секреты, данные выполнения, обнаруженные сведения, планы, журналы
              и результаты не экспортируются.
            </p>
            <label>
              Папка назначения
              <div className="inline-fields">
                <input
                  value={parent}
                  onChange={(event) => onParentChange(event.target.value)}
                  placeholder="C:\\Projects"
                  required
                />
                <button
                  type="button"
                  className="outline"
                  onClick={onChooseParent}
                  disabled={busy}
                >
                  Выбрать
                </button>
              </div>
            </label>
            <label>
              Имя новой папки
              <input
                value={name}
                onChange={(event) => onNameChange(event.target.value)}
                placeholder="portable-project"
                required
                maxLength={128}
              />
            </label>
          </>
        )}
        {operation?.error && (
          <p className="field-error" role="alert">
            <code>{operation.error.code}</code> {operation.error.message}
          </p>
        )}
        {plan && (
          <>
            <p>
              Проверьте состав перед публикацией. Существующая папка назначения
              никогда не будет перезаписана.
            </p>
            <dl>
              <dt>Новая папка</dt>
              <dd>{plan.destinationRoot}</dd>
              <dt>Ревизия проекта</dt>
              <dd>{plan.sourceProjectRevision}</dd>
              <dt>Файлы</dt>
              <dd>{plan.documents.length}</dd>
              <dt>Размер</dt>
              <dd>{plan.aggregateSize} байт</dd>
            </dl>
            <p className="readonly">
              Исключено:{" "}
              {plan.excludedCategories.map(exportExclusionLabel).join(", ")}
            </p>
          </>
        )}
        {result?.status === "EXPORTED" && (
          <p className="success" role="status">
            Экспорт завершён: {result.destinationRoot}
          </p>
        )}
        <footer className="dialog-actions">
          <button
            type="button"
            className="outline"
            onClick={onClose}
            disabled={busy}
          >
            {result?.status === "EXPORTED" ? "Готово" : "Отмена"}
          </button>
          {!plan && !result && (
            <button type="submit" disabled={!canPreview}>
              {busy ? "Подготовка…" : "Проверить состав"}
            </button>
          )}
          {plan && (
            <button type="button" onClick={onCommit} disabled={busy}>
              {busy ? "Экспорт…" : "Экспортировать"}
            </button>
          )}
          {result?.status === "EXPORTED" && (
            <button type="button" onClick={onReopen} disabled={busy}>
              {busy ? "Открытие…" : "Открыть экспортированный проект"}
            </button>
          )}
        </footer>
      </form>
    </div>
  );
}

function reviewFindingMessage(code: string, fallback: string): string {
  if (code === "REFERENCE_IN_USE")
    return "Объект используется. Сначала удалите связанные ссылки.";
  if (code === "INVALID_VALUE")
    return "Значение не соответствует ограничениям каталога.";
  return fallback;
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
            <code>{error.code}</code>{" "}
            {reviewFindingMessage(error.code, error.message)}
          </p>
        )}
        {plan ? (
          <>
            {plan.finding && (
              <p className="field-error" role="alert">
                <code>{plan.finding.code}</code>{" "}
                {reviewFindingMessage(
                  plan.finding.code,
                  plan.finding.safeMessage,
                )}
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

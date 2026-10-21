import {
  ProbeServerInformation,
  CheckServerInformation,
  AmendServiceConfigurationDraft,
  AmendApplicationLibraryDraft,
  AppendEditCommand,
  ChooseProject,
  ChooseApplicationPackageDirectory,
  ReviewApplicationPackageImport,
  ChooseProjectExportParent,
  ChooseProjectParent,
  CloseProject,
  CurrentProject,
  CommitStructuralEditPlan,
  CommitProjectExport,
  CreateProject,
  DiscardEditSession,
  GetApplicationConfig,
  GetServiceConfigurationPreview,
  GetEndpointPreview,
  GetVerifiedPKIView,
  GetRuntimeSecretDescriptors,
  GetApplicationRuntimeSecretAvailability,
  GetPendingRuntimeSecretDescriptors,
  ListPendingSecretOutputs,
  SetSecretOutputEncryptionPassword,
  DeliverPendingSecretOutput,
  GetExecutionNodeContext,
  ProbeExecutionNodeHostKey,
  ApproveExecutionNodeHostKey,
  DeclineExecutionNodeHostKey,
  ProbeTargetHostKey,
  ApproveTargetHostKey,
  DeclineTargetHostKey,
  GetInstallationState,
  CreateInstallationPlan,
  CreateInstallationPlanForMode,
  GetInfrastructureVerification,
  GetInstallationPlan,
  ApproveInstallationPlan,
  StartApprovedInstallation,
  GetInstallationRun,
  SubscribeInstallationRun,
  UnsubscribeInstallationRun,
  CancelInstallationRun,
  GetSessionCredentialStatus,
  CheckExecutionNode,
  OpenProject,
  ChooseRuntimeBundleUpdate,
  ConfirmRuntimeBundleUpdate,
  InspectOrphanRun,
  AttachOrphanRun,
  CancelOrphanRun,
  PlanExecutionNodePreparation,
  PlanProjectExport,
  PrepareExecutionNode,
  ReviewStructuralEditSession,
  SetSessionCredential,
  SetPKIStorePassword,
  SetDeploymentRuntimeSecretValues,
  SetPendingDeploymentRuntimeSecretValues,
  ChoosePendingDeploymentRuntimeSecretFile,
  SelectExecutionNode,
  StartEditSession,
  VerifyProject,
  ClearSessionCredential,
} from "../wailsjs/go/main/App";
import type { desktop, executionnode } from "../wailsjs/go/models";
import { EventsOn } from "../wailsjs/runtime/runtime";

export type VerificationStatus = {
  status:
    | "UNVERIFIED"
    | "VERIFYING"
    | "VERIFIED"
    | "INVALID"
    | "STALE"
    | "UNAVAILABLE";
  projectRevision?: string;
  executionNodeId?: string;
  runtime?: {
    bundleDigest: string;
    coreVersion: string;
    catalogDigest: string;
    protocol: string;
  };
  findings?: Array<{
    code: string;
    severity: string;
    summary: string;
    subjectKind?: string;
    subjectId?: string;
    helpRef?: string;
  }>;
  findingsTruncated?: boolean;
  checkedAt?: string;
  error?: { code: string; message: string; diagnosticCodes?: string[] };
};
export type ManagedProjectView = {
  projectRevision: string;
  applicationLibraries?: Record<string, { libraryRef: string }>;
  dataRootDirectory?: string;
  namePrefix?: string;
  servers: Record<
    string,
    {
      hostId: string;
      type?: string;
      desiredHostname?: string;
      address?: string;
      sshPort?: number;
    }
  >;
  deployments: Record<
    string,
    {
      deploymentId: string;
      serviceType: string;
      mode: string;
      endpointGroup?: string;
      endpointGroupRef?: string;
      virtualRouterId?: number;
      virtualAddresses?: Array<{ address: string; interface: string }>;
      providerEditState?: "NONE" | "EDITABLE" | "INCOMPLETE" | "UNSUPPORTED";
      configuration?: Array<{
        setting: string;
        overridePresent: boolean;
        state: "EDITABLE" | "UNSUPPORTED" | "UNKNOWN";
        value?: string | number | boolean;
      }>;
    }
  >;
  endpointGroups?: Record<
    string,
    {
      endpointGroupId: string;
      domain: string;
      wildcard: boolean;
    }
  >;
  memberPlacements?: Array<{
    deploymentId: string;
    memberId: string;
    hostId: string;
    roles: string[];
    configuration?: Array<{
      setting: string;
      overridePresent: boolean;
      state: "EDITABLE" | "UNSUPPORTED" | "UNKNOWN";
      value?: string | number | boolean;
    }>;
  }>;
  hostPlacements?: Array<{
    deploymentId: string;
    hostId: string;
    roles: string[];
    priority?: number;
  }>;
  pki?: {
    authorities: Record<string, Record<string, unknown>>;
    profiles: Record<string, Record<string, unknown>>;
    tlsProfiles: Record<string, Record<string, unknown>>;
    scopes: Record<string, Record<string, unknown>>;
  };
};
export type OpenResult = desktop.ProjectOpenResult & {
  managed?: ManagedProjectView;
  verification?: VerificationStatus;
};
export type RuntimeBundleUpdate = desktop.RuntimeBundleUpdateResult;
export type OrphanRunRecovery = Omit<
  desktop.OrphanRunRecoveryResult,
  "convertValues"
>;
export type EditResult = Omit<
  desktop.EditOperationResult,
  "plan" | "commit"
> & {
  plan?: {
    planId?: string;
    status: string;
    finding?: { code: string; safeMessage: string };
    semanticChanges: Array<{ safeSummary: string }>;
    affectedDocuments: Array<{
      logicalPath: string;
      before?: { state: string };
      after?: { state: string };
    }>;
    saveAllowed: boolean;
  };
  commit?: {
    status: string;
    newProjectRevision?: string;
    finding?: { code: string; safeMessage: string };
  };
  current?: OpenResult;
};
export type ConfigResult = desktop.ApplicationConfigResult;
export type SessionCredentialStatus = {
  status: string;
  username?: string;
  sshMode?: string;
  sudoPasswordStatus: string;
  pkiStorePasswordStatus?: string;
  expiresAt?: string;
};
export type SessionCredentialInput = {
  username: string;
  sshMode: "SSH_PASSWORD" | "SSH_PRIVATE_KEY";
  sshPassword: string;
  privateKeyPath: string;
  elevationMode: "NONE" | "SUDO_PASSWORD";
  elevationPassword: string;
};
export type ExecutionNodeContext = {
  status: string;
  selectionKind: string;
  selectionSource: string;
  selectedHostId?: string;
  runtimeDigest?: string;
  safeLabel?: string;
  locked: boolean;
};
export type InstallationState = {
  apiVersion: "platform.installer/installation-state/v1alpha1";
  kind: "InstallationState";
  status:
    | "PREREQUISITES_REQUIRED"
    | "READY_TO_PLAN"
    | "PLAN_BLOCKED"
    | "PLAN_REVIEW"
    | "PLAN_APPROVED";
  project?: {
    id: string;
    revision: string;
    verificationStatus: string;
    hasUnsavedChanges: boolean;
  };
  executionNode: { status: string; safeLabel?: string };
  plan: {
    status:
      | "NOT_CREATED"
      | "PLAN_STALE_OR_EXPIRED"
      | "PLAN_BLOCKED"
      | "PLAN_REVIEW"
      | "PLAN_APPROVED";
    planId?: string;
  };
  prerequisites?: Array<{
    code: string;
    destination: "project" | "servers";
    safeMessage: string;
  }>;
};
export type InstallationExecutionMode =
  "FULL_PROJECT" | "APPLICATION_LIBRARIES_ONLY" | "INFRASTRUCTURE_VERIFY_ONLY";
export type InstallationPlanRequest = {
  skipInfrastructureVerify?: boolean;
  executionMode: InstallationExecutionMode;
  deploymentOrder: string[];
  applicationLibraryOrder?: string[];
  applicationVaultSources: Record<
    string,
    "RUNTIME_INPUT" | "CURRENT_RUN_BOOTSTRAP"
  >;
};
export type InfrastructureVerificationView = Pick<
  desktop.InfrastructureVerificationView,
  "availability" | "observedAt" | "previous"
>;
export type InstallationPlanView = {
  skipInfrastructureVerify?: boolean;
  executionMode?: InstallationExecutionMode;
  infrastructureVerification?: executionnode.InfrastructureVerification;
  infrastructureObservedAt?: string;
  infrastructureCacheWarning?: boolean;
  id: string;
  status: "EXECUTABLE" | "BLOCKED";
  projectRevision: string;
  planFingerprint: string;
  executionNodeId: string;
  runtime: {
    bundleDigest: string;
    coreVersion: string;
    catalogDigest: string;
    protocol: string;
  };
  expiresAt: string;
  approved: boolean;
  pkiStorePasswordRequired?: boolean;
  secretOutputEncryptionRequired?: boolean;
  secretOutputEncryptionPasswordPresent?: boolean;
  acknowledgements: Array<{ code: string; summary: string }>;
  phases: Array<{
    id: string;
    order: number;
    actions: Array<{
      id: string;
      type: string;
      serviceDeployment?: string;
      targets: string[];
      dependsOn: string[];
      mutating: boolean;
      reboot: string;
      summary: string;
    }>;
  }>;
  findings?: Array<{ code: string; safeMessage: string }>;
};
export type InstallationPlanOperation = {
  status: "BLOCKED" | "PLAN_BLOCKED" | "PLAN_REVIEW" | "PLAN_APPROVED";
  plan?: InstallationPlanView;
  error?: { code: string; message: string; diagnosticCodes?: string[] };
};
export type InstallationRunView = desktop.InstallationRunView;
export type InstallationResultView = desktop.InstallationResultView;
export type InstallationRunOperation = desktop.InstallationRunOperation;
export type InstallationEventView = desktop.InstallationEventView;
export type InstallationSubscriptionResult =
  desktop.InstallationSubscriptionResult;
export type EndpointPreview = {
  status: "CURRENT" | "INVALID" | "STALE" | "NOT_VERIFIED" | "UNAVAILABLE";
  endpoints?: Array<{ deploymentId: string; fqdn: string }>;
  providers?: Array<{
    endpointGroupId: string;
    providerDeploymentId: string;
    endpointGroupRef: string;
    virtualRouterId: number;
    virtualAddresses: Array<{ address: string; interface: string }>;
  }>;
  findings?: VerificationStatus["findings"];
  findingsTruncated?: boolean;
  truncated?: boolean;
  error?: { code: string; message: string };
};
export type VerifiedPKIView = {
  status: "CURRENT" | "INVALID" | "STALE" | "NOT_VERIFIED" | "UNAVAILABLE";
  identities?: Array<{
    id: string;
    scope: "HOST" | "MEMBER" | "DEPLOYMENT";
    tlsProfileId: string;
    dnsNames: string[];
    ipAddresses: string[];
    consumers: Array<{
      deploymentId: string;
      memberId: string;
      hostId: string;
    }>;
  }>;
  findings?: VerificationStatus["findings"];
  findingsTruncated?: boolean;
  error?: { code: string; message: string };
};
export type ExecutionNodeReadiness = {
  status: string;
  nodeId?: string;
  safeLabel?: string;
  checkedAt?: string;
  findings?: Array<{ code: string; safeMessage: string }>;
  error?: { code: string; message: string };
};
export type HostKeyProbeResult = {
  status: string;
  probeId?: string;
  safeLabel?: string;
  keyType?: string;
  fingerprint?: string;
  error?: { code: string; message: string };
};
export type ServerInformationResult = {
  status: string;
  hostId?: string;
  information?: {
    hostname: string;
    os: string;
    osVersion: string;
    architecture: string;
    cpuCount: number;
    memoryBytes: number;
    serverTime: string;
    checkedAt: string;
  };
  error?: { code: string; message: string };
};
export type ExecutionNodePreparation = {
  status: string;
  planId?: string;
  expiresAt?: string;
  steps?: Array<{ id: string; action: string; mutates: boolean }>;
  findings?: Array<{ code: string; safeMessage: string }>;
  error?: { code: string; message: string };
  verification?: VerificationStatus;
};
export type ProjectExportPlan = {
  planDigest: string;
  sourceProjectRoot: string;
  sourceProjectRevision: string;
  destinationParent: string;
  directoryName: string;
  destinationRoot: string;
  documents: Array<{ logicalPath: string; size: number; digest: string }>;
  aggregateSize: number;
  excludedCategories: string[];
};
export type ProjectExportResult = {
  status: "EXPORTED" | "FAILED";
  destinationRoot?: string;
  sourceProjectRevision?: string;
  documentCount?: number;
  aggregateSize?: number;
  errorCode?: string;
};
export type ProjectExportOperationResult = {
  status: "READY" | "EXPORTED" | "BLOCKED";
  plan?: ProjectExportPlan;
  result?: ProjectExportResult;
  error?: { code: string; message: string };
};
export type RuntimeSecretDescriptor = {
  requirementRef: string;
  purpose:
    | "PKI_STORE_PASSWORD"
    | "SERVICE_PASSWORD"
    | "SERVICE_ADMIN_TOKEN"
    | "SERVICE_UNSEAL_SHARES";
  serviceDeployment?: string;
  setting?: string;
  displayLabel: string;
  requiredWhen?: string;
  operations?: string[];
  referenceConfigured?: boolean;
  hosts: string[];
};
export type RuntimeSecretDescriptorOperation = {
  applicationSecretAvailability?: Record<string, boolean>;
  secretsInstalled?: boolean;
  status: "READY" | "UNAVAILABLE";
  projectRevision?: string;
  descriptorSetFingerprint?: string;
  descriptors?: RuntimeSecretDescriptor[];
  applicationInputs?: Array<{
    requirementRef: string;
    purpose:
      | "APPLICATION_SECRET"
      | "APPLICATION_VAULT_ADMIN_TOKEN"
      | "APPLICATION_REGISTRY_USERNAME"
      | "APPLICATION_REGISTRY_PASSWORD";
    providerDeployment: string | null;
    applicationLibraries: string[];
    hosts: string[];
    operations: string[];
    sourceRef: string;
    displayLabel: string;
  }>;
  error?: { code: string; message: string };
};
export type ServiceConfigurationPreview = {
  apiVersion: string;
  kind: string;
  projectRevision: string;
  runtimeDigest?: string;
  services: Record<
    string,
    {
      configuration: Record<
        string,
        { state: string; source: string; value?: string | number | boolean }
      >;
      members: Record<
        string,
        Record<
          string,
          { state: string; source: string; value?: string | number | boolean }
        >
      >;
    }
  >;
};
export type RuntimeSecretValuesInput = {
  projectRevision: string;
  descriptorSetFingerprint: string;
  serviceDeployment: string;
  applicationLibrary?: string;
  applicationRequirementRef?: string;
  values: Record<string, string>;
};
export type PendingRuntimeSecretValuesInput = {
  serviceDeployment: string;
  values: Record<string, string>;
};
export type PendingRuntimeSecretFileInput = {
  serviceDeployment: string;
  purpose: "SERVICE_ADMIN_TOKEN" | "SERVICE_UNSEAL_SHARES";
  encryptionPassword: string;
};
export type SecretOutputPackage = {
  protocol: string;
  packageId: string;
  projectId: string;
  deploymentId: string;
  sourceRunId: string;
  runtimeDigest: string;
  generation: number;
  state: "READY" | "ACKED_CLEANUP_PENDING" | "LOCAL_DELIVERED";
  entries: Array<"admin-token" | "unseal-shares">;
};
export type SecretOutputPackagesOperation = {
  status: "READY" | "UNAVAILABLE";
  packages?: SecretOutputPackage[];
  nextCursor?: string | null;
  error?: { code: string; message: string };
};

export function secretOutputListingUnavailable(): SecretOutputPackagesOperation {
  return {
    status: "UNAVAILABLE",
    error: {
      code: "SECRET_OUTPUT_LIST_FAILED",
      message:
        "Не удалось проверить ожидающие защищённые файлы. Повторите проверку позже.",
    },
  };
}

export type SecretOutputDeliveryOperation = {
  status: "UNAVAILABLE" | "STAGING_RETAINED" | "ACK_PENDING" | "DELIVERED";
  package?: SecretOutputPackage;
  directory?: string;
  stagingPath?: string;
  error?: { code: string; message: string };
};

export function secretOutputDeliveryUnavailable(): SecretOutputDeliveryOperation {
  return {
    status: "UNAVAILABLE",
    error: {
      code: "SECRET_OUTPUT_DELIVERY_FAILED",
      message:
        "Не удалось получить защищённые выходные файлы. Проверьте подключение и повторите попытку.",
    },
  };
}
export interface ProjectBackend {
  exitApplication?(): Promise<{ status: "EXITING" | "EXIT_AFTER_RUN" }>;
  subscribeInstallationRunEvents?(
    handler: (value: {
      subscriptionId?: string;
      event?: InstallationEventView;
      errorCode?: string;
    }) => void,
  ): () => void;
  chooseRuntimeBundleUpdate?(): Promise<RuntimeBundleUpdate>;
  confirmRuntimeBundleUpdate?(previewId: string): Promise<RuntimeBundleUpdate>;
  inspectOrphanRun?(): Promise<OrphanRunRecovery>;
  attachOrphanRun?(recoveryId: string): Promise<InstallationRunOperation>;
  cancelOrphanRun?(recoveryId: string): Promise<OrphanRunRecovery>;
  getApplicationConfig(): Promise<ConfigResult>;
  chooseProject(): Promise<OpenResult>;
  openProject(root: string): Promise<OpenResult>;
  getCurrentProject?(): Promise<OpenResult>;
  chooseProjectParent(): Promise<string>;
  chooseProjectExportParent?(): Promise<string>;
  createProject(input: {
    projectRoot: string;
    displayName: string;
    compatibilitySourceId: string;
  }): Promise<OpenResult>;
  closeProject(): Promise<OpenResult>;
  chooseApplicationPackageDirectory?(): Promise<string>;
  reviewApplicationPackageImport?(
    sessionId: string,
    source: string,
    kind: string,
    name: string,
    version: string,
    digest: string,
  ): Promise<EditResult>;
  startEditSession(): Promise<EditResult>;
  appendEditCommand(
    sessionId: string,
    command: Record<string, unknown>,
  ): Promise<EditResult>;
  amendApplicationLibraryDraft?(
    sessionId: string,
    index: number,
    expected: Record<string, unknown>,
    replacement: Record<string, unknown> | null,
  ): Promise<EditResult>;
  amendServiceConfigurationDraft(
    sessionId: string,
    index: number,
    expected: Record<string, unknown>,
    replacement: Record<string, unknown> | null,
  ): Promise<EditResult>;
  reviewEditSession(sessionId: string): Promise<EditResult>;
  commitEditPlan(sessionId: string, planId: string): Promise<EditResult>;
  discardEditSession(sessionId: string): Promise<EditResult>;
  getSessionCredentialStatus?(): Promise<SessionCredentialStatus>;
  setSessionCredential?(
    input: SessionCredentialInput,
  ): Promise<SessionCredentialStatus>;
  setPKIStorePassword?(value: string): Promise<SessionCredentialStatus>;
  getRuntimeSecretDescriptors?(): Promise<RuntimeSecretDescriptorOperation>;
  getApplicationRuntimeSecretAvailability?(): Promise<RuntimeSecretDescriptorOperation>;
  setDeploymentRuntimeSecretValues?(
    input: RuntimeSecretValuesInput,
  ): Promise<void>;
  getPendingRuntimeSecretDescriptors?(
    serviceDeployment: string,
  ): Promise<RuntimeSecretDescriptorOperation>;
  setPendingDeploymentRuntimeSecretValues?(
    input: PendingRuntimeSecretValuesInput,
  ): Promise<void>;
  choosePendingDeploymentRuntimeSecretFile?(
    input: PendingRuntimeSecretFileInput,
  ): Promise<string>;
  listPendingSecretOutputs?(
    cursor?: string | null,
  ): Promise<SecretOutputPackagesOperation>;
  setSecretOutputEncryptionPassword?(
    password: string,
    confirm: string,
  ): Promise<void>;
  deliverPendingSecretOutput?(
    packageId: string,
  ): Promise<SecretOutputDeliveryOperation>;
  clearSessionCredential?(): Promise<SessionCredentialStatus>;
  getExecutionNodeContext?(): Promise<ExecutionNodeContext>;
  getServiceConfigurationPreview?(): Promise<ServiceConfigurationPreview>;
  probeExecutionNodeHostKey?(): Promise<HostKeyProbeResult>;
  approveExecutionNodeHostKey?(probeId: string): Promise<HostKeyProbeResult>;
  declineExecutionNodeHostKey?(): Promise<HostKeyProbeResult>;
  probeTargetHostKey?(hostId: string): Promise<HostKeyProbeResult>;
  probeServerInformation?(hostId: string): Promise<HostKeyProbeResult>;
  checkServerInformation?(probeId: string): Promise<ServerInformationResult>;
  approveTargetHostKey?(probeId: string): Promise<HostKeyProbeResult>;
  declineTargetHostKey?(): Promise<HostKeyProbeResult>;
  getInstallationState?(): Promise<InstallationState>;
  createInstallationPlan?(
    deploymentOrder: string[],
  ): Promise<InstallationPlanOperation>;
  createInstallationPlanForMode?(
    request: InstallationPlanRequest,
  ): Promise<InstallationPlanOperation>;
  getInfrastructureVerification?(): Promise<InfrastructureVerificationView>;
  getInstallationPlan?(planId: string): Promise<InstallationPlanOperation>;
  approveInstallationPlan?(
    planId: string,
    acknowledgements: string[],
  ): Promise<InstallationPlanOperation>;
  startApprovedInstallation?(planId: string): Promise<InstallationRunOperation>;
  getInstallationRun?(runId: string): Promise<InstallationRunOperation>;
  subscribeInstallationRun?(
    runId: string,
    afterSequence: number,
  ): Promise<InstallationSubscriptionResult>;
  unsubscribeInstallationRun?(subscriptionId: string): Promise<void>;
  cancelInstallationRun?(runId: string): Promise<InstallationRunOperation>;
  getEndpointPreview?(): Promise<EndpointPreview>;
  getVerifiedPKIView?(): Promise<VerifiedPKIView>;
  selectExecutionNode?(hostId: string): Promise<ExecutionNodeContext>;
  checkExecutionNode?(): Promise<ExecutionNodeReadiness>;
  planExecutionNodePreparation?(): Promise<ExecutionNodePreparation>;
  prepareExecutionNode?(planId: string): Promise<ExecutionNodePreparation>;
  verifyProject?(): Promise<VerificationStatus>;
  planProjectExport?(
    destinationParent: string,
    directoryName: string,
  ): Promise<ProjectExportOperationResult>;
  commitProjectExport?(
    planDigest: string,
  ): Promise<ProjectExportOperationResult>;
}

export const backend: ProjectBackend = {
  subscribeInstallationRunEvents: (handler) =>
    EventsOn("installation-run-event", handler),
  chooseRuntimeBundleUpdate: ChooseRuntimeBundleUpdate,
  confirmRuntimeBundleUpdate: ConfirmRuntimeBundleUpdate,
  inspectOrphanRun: InspectOrphanRun,
  attachOrphanRun: AttachOrphanRun,
  cancelOrphanRun: CancelOrphanRun,
  getApplicationConfig: GetApplicationConfig,
  chooseProject: () => ChooseProject() as unknown as Promise<OpenResult>,
  openProject: (root) => OpenProject(root) as unknown as Promise<OpenResult>,
  getCurrentProject: () => CurrentProject() as unknown as Promise<OpenResult>,
  chooseProjectParent: ChooseProjectParent,
  chooseProjectExportParent: ChooseProjectExportParent,
  createProject: (input) =>
    CreateProject(input as never) as unknown as Promise<OpenResult>,
  closeProject: () => CloseProject() as unknown as Promise<OpenResult>,
  chooseApplicationPackageDirectory: ChooseApplicationPackageDirectory,
  reviewApplicationPackageImport: (...args) =>
    ReviewApplicationPackageImport(...args) as unknown as Promise<EditResult>,
  startEditSession: () => StartEditSession() as unknown as Promise<EditResult>,
  appendEditCommand: (sessionId, command) =>
    AppendEditCommand(
      sessionId,
      command as never,
    ) as unknown as Promise<EditResult>,
  amendApplicationLibraryDraft: (sessionId, index, expected, replacement) =>
    AmendApplicationLibraryDraft(
      sessionId,
      index,
      expected as never,
      replacement as never,
    ) as unknown as Promise<EditResult>,
  amendServiceConfigurationDraft: (sessionId, index, expected, replacement) =>
    AmendServiceConfigurationDraft(
      sessionId,
      index,
      expected as never,
      replacement as never,
    ) as unknown as Promise<EditResult>,
  reviewEditSession: (sessionId) =>
    ReviewStructuralEditSession(sessionId) as unknown as Promise<EditResult>,
  commitEditPlan: (sessionId, planId) =>
    CommitStructuralEditPlan(
      sessionId,
      planId,
    ) as unknown as Promise<EditResult>,
  discardEditSession: (sessionId) =>
    DiscardEditSession(sessionId) as unknown as Promise<EditResult>,
  getSessionCredentialStatus: GetSessionCredentialStatus,
  setSessionCredential: (input) => SetSessionCredential(input as never),
  setPKIStorePassword: SetPKIStorePassword,
  getRuntimeSecretDescriptors: () =>
    GetRuntimeSecretDescriptors() as unknown as Promise<RuntimeSecretDescriptorOperation>,
  getApplicationRuntimeSecretAvailability: () =>
    GetApplicationRuntimeSecretAvailability() as unknown as Promise<RuntimeSecretDescriptorOperation>,
  setDeploymentRuntimeSecretValues: (input) =>
    SetDeploymentRuntimeSecretValues(input as never),
  getPendingRuntimeSecretDescriptors: (serviceDeployment) =>
    GetPendingRuntimeSecretDescriptors(
      serviceDeployment,
    ) as unknown as Promise<RuntimeSecretDescriptorOperation>,
  setPendingDeploymentRuntimeSecretValues: (input) =>
    SetPendingDeploymentRuntimeSecretValues(input as never),
  choosePendingDeploymentRuntimeSecretFile: (input) =>
    ChoosePendingDeploymentRuntimeSecretFile(input as never),
  listPendingSecretOutputs: (cursor = null) =>
    ListPendingSecretOutputs(
      cursor,
    ) as unknown as Promise<SecretOutputPackagesOperation>,
  setSecretOutputEncryptionPassword: (password, confirm) =>
    SetSecretOutputEncryptionPassword({ password, confirm } as never),
  deliverPendingSecretOutput: (packageId) =>
    DeliverPendingSecretOutput({
      packageId,
    } as never) as unknown as Promise<SecretOutputDeliveryOperation>,
  clearSessionCredential: ClearSessionCredential,
  getExecutionNodeContext: GetExecutionNodeContext,
  getServiceConfigurationPreview: () =>
    GetServiceConfigurationPreview() as unknown as Promise<ServiceConfigurationPreview>,
  probeExecutionNodeHostKey: () =>
    ProbeExecutionNodeHostKey() as unknown as Promise<HostKeyProbeResult>,
  approveExecutionNodeHostKey: (probeId) =>
    ApproveExecutionNodeHostKey(
      probeId,
    ) as unknown as Promise<HostKeyProbeResult>,
  declineExecutionNodeHostKey: () =>
    DeclineExecutionNodeHostKey() as unknown as Promise<HostKeyProbeResult>,
  probeTargetHostKey: (hostId) =>
    ProbeTargetHostKey(hostId) as unknown as Promise<HostKeyProbeResult>,
  probeServerInformation: (hostId) =>
    ProbeServerInformation(hostId) as unknown as Promise<HostKeyProbeResult>,
  checkServerInformation: (probeId) =>
    CheckServerInformation(
      probeId,
    ) as unknown as Promise<ServerInformationResult>,
  approveTargetHostKey: (probeId) =>
    ApproveTargetHostKey(probeId) as unknown as Promise<HostKeyProbeResult>,
  declineTargetHostKey: () =>
    DeclineTargetHostKey() as unknown as Promise<HostKeyProbeResult>,
  getInstallationState: () =>
    GetInstallationState() as unknown as Promise<InstallationState>,
  createInstallationPlan: (deploymentOrder) =>
    CreateInstallationPlan(
      deploymentOrder,
    ) as unknown as Promise<InstallationPlanOperation>,
  createInstallationPlanForMode: (request) =>
    CreateInstallationPlanForMode({
      ...request,
      skipInfrastructureVerify: request.skipInfrastructureVerify ?? false,
    }) as unknown as Promise<InstallationPlanOperation>,
  getInfrastructureVerification: () =>
    GetInfrastructureVerification() as unknown as Promise<InfrastructureVerificationView>,
  getInstallationPlan: (planId) =>
    GetInstallationPlan(
      planId,
    ) as unknown as Promise<InstallationPlanOperation>,
  approveInstallationPlan: (planId, acknowledgements) =>
    ApproveInstallationPlan(
      planId,
      acknowledgements,
    ) as unknown as Promise<InstallationPlanOperation>,
  startApprovedInstallation: (planId) =>
    StartApprovedInstallation(
      planId,
    ) as unknown as Promise<InstallationRunOperation>,
  getInstallationRun: (runId) =>
    GetInstallationRun(runId) as unknown as Promise<InstallationRunOperation>,
  subscribeInstallationRun: (runId, afterSequence) =>
    SubscribeInstallationRun(
      runId,
      afterSequence,
    ) as unknown as Promise<InstallationSubscriptionResult>,
  unsubscribeInstallationRun: (subscriptionId) =>
    UnsubscribeInstallationRun(subscriptionId),
  cancelInstallationRun: (runId) =>
    CancelInstallationRun(
      runId,
    ) as unknown as Promise<InstallationRunOperation>,
  getEndpointPreview: () =>
    GetEndpointPreview() as unknown as Promise<EndpointPreview>,
  getVerifiedPKIView: () =>
    GetVerifiedPKIView() as unknown as Promise<VerifiedPKIView>,
  selectExecutionNode: SelectExecutionNode,
  checkExecutionNode: () =>
    CheckExecutionNode() as unknown as Promise<ExecutionNodeReadiness>,
  planExecutionNodePreparation: () =>
    PlanExecutionNodePreparation() as unknown as Promise<ExecutionNodePreparation>,
  prepareExecutionNode: (planId) =>
    PrepareExecutionNode(
      planId,
    ) as unknown as Promise<ExecutionNodePreparation>,
  verifyProject: () =>
    VerifyProject() as unknown as Promise<VerificationStatus>,
  planProjectExport: (destinationParent, directoryName) =>
    PlanProjectExport(
      destinationParent,
      directoryName,
    ) as unknown as Promise<ProjectExportOperationResult>,
  commitProjectExport: (planDigest) =>
    CommitProjectExport(
      planDigest,
    ) as unknown as Promise<ProjectExportOperationResult>,
};

import {
  AppendEditCommand,
  ChooseProject,
  ChooseProjectExportParent,
  ChooseProjectParent,
  CloseProject,
  CommitStructuralEditPlan,
  CommitProjectExport,
  CreateProject,
  DiscardEditSession,
  GetApplicationConfig,
  GetEndpointPreview,
  GetVerifiedPKIView,
  GetExecutionNodeContext,
  GetInstallationState,
  CreateInstallationPlan,
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
  PlanExecutionNodePreparation,
  PlanProjectExport,
  PrepareExecutionNode,
  ReviewStructuralEditSession,
  SetSessionCredential,
  SetPKIStorePassword,
  SelectExecutionNode,
  StartEditSession,
  VerifyProject,
  ClearSessionCredential,
} from "../wailsjs/go/main/App";
import type { main } from "../wailsjs/go/models";

export type VerificationStatus = {
  status: "UNVERIFIED" | "VERIFYING" | "VERIFIED" | "INVALID";
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
  error?: { code: string; message: string };
};
export type ManagedProjectView = {
  projectRevision: string;
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
export type OpenResult = main.ProjectOpenResult & {
  managed?: ManagedProjectView;
  verification?: VerificationStatus;
};
export type EditResult = Omit<main.EditOperationResult, "plan" | "commit"> & {
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
export type ConfigResult = main.ApplicationConfigResult;
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
export type InstallationPlanView = {
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
  error?: { code: string; message: string };
};
export type InstallationRunView = main.InstallationRunView;
export type InstallationResultView = main.InstallationResultView;
export type InstallationRunOperation = main.InstallationRunOperation;
export type InstallationEventView = main.InstallationEventView;
export type InstallationSubscriptionResult = main.InstallationSubscriptionResult;
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
export interface ProjectBackend {
  getApplicationConfig(): Promise<ConfigResult>;
  chooseProject(): Promise<OpenResult>;
  openProject(root: string): Promise<OpenResult>;
  chooseProjectParent(): Promise<string>;
  chooseProjectExportParent?(): Promise<string>;
  createProject(input: {
    projectRoot: string;
    displayName: string;
    compatibilitySourceId: string;
  }): Promise<OpenResult>;
  closeProject(): Promise<OpenResult>;
  startEditSession(): Promise<EditResult>;
  appendEditCommand(
    sessionId: string,
    command: Record<string, unknown>,
  ): Promise<EditResult>;
  reviewEditSession(sessionId: string): Promise<EditResult>;
  commitEditPlan(sessionId: string, planId: string): Promise<EditResult>;
  discardEditSession(sessionId: string): Promise<EditResult>;
  getSessionCredentialStatus?(): Promise<SessionCredentialStatus>;
  setSessionCredential?(
    input: SessionCredentialInput,
  ): Promise<SessionCredentialStatus>;
  setPKIStorePassword?(value: string): Promise<SessionCredentialStatus>;
  clearSessionCredential?(): Promise<SessionCredentialStatus>;
  getExecutionNodeContext?(): Promise<ExecutionNodeContext>;
  getInstallationState?(): Promise<InstallationState>;
  createInstallationPlan?(): Promise<InstallationPlanOperation>;
  getInstallationPlan?(planId: string): Promise<InstallationPlanOperation>;
  approveInstallationPlan?(
    planId: string,
    acknowledgements: string[],
  ): Promise<InstallationPlanOperation>;
  startApprovedInstallation?(planId: string): Promise<InstallationRunOperation>;
  getInstallationRun?(runId: string): Promise<InstallationRunOperation>;
  subscribeInstallationRun?(runId: string, afterSequence: number): Promise<InstallationSubscriptionResult>;
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
  commitProjectExport?(planDigest: string): Promise<ProjectExportOperationResult>;
}

export const backend: ProjectBackend = {
  getApplicationConfig: GetApplicationConfig,
  chooseProject: () => ChooseProject() as unknown as Promise<OpenResult>,
  openProject: (root) => OpenProject(root) as unknown as Promise<OpenResult>,
  chooseProjectParent: ChooseProjectParent,
  chooseProjectExportParent: ChooseProjectExportParent,
  createProject: (input) =>
    CreateProject(input as never) as unknown as Promise<OpenResult>,
  closeProject: () => CloseProject() as unknown as Promise<OpenResult>,
  startEditSession: () => StartEditSession() as unknown as Promise<EditResult>,
  appendEditCommand: (sessionId, command) =>
    AppendEditCommand(
      sessionId,
      command as never,
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
  clearSessionCredential: ClearSessionCredential,
  getExecutionNodeContext: GetExecutionNodeContext,
  getInstallationState: () =>
    GetInstallationState() as unknown as Promise<InstallationState>,
  createInstallationPlan: () =>
    CreateInstallationPlan() as unknown as Promise<InstallationPlanOperation>,
  getInstallationPlan: (planId) =>
    GetInstallationPlan(planId) as unknown as Promise<InstallationPlanOperation>,
  approveInstallationPlan: (planId, acknowledgements) =>
    ApproveInstallationPlan(
      planId,
      acknowledgements,
    ) as unknown as Promise<InstallationPlanOperation>,
  startApprovedInstallation: (planId) => StartApprovedInstallation(planId) as unknown as Promise<InstallationRunOperation>,
  getInstallationRun: (runId) => GetInstallationRun(runId) as unknown as Promise<InstallationRunOperation>,
  subscribeInstallationRun: (runId, afterSequence) => SubscribeInstallationRun(runId, afterSequence) as unknown as Promise<InstallationSubscriptionResult>,
  unsubscribeInstallationRun: (subscriptionId) => UnsubscribeInstallationRun(subscriptionId),
  cancelInstallationRun: (runId) => CancelInstallationRun(runId) as unknown as Promise<InstallationRunOperation>,
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
    CommitProjectExport(planDigest) as unknown as Promise<ProjectExportOperationResult>,
};

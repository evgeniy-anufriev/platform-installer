import {
  AppendEditCommand,
  ChooseProject,
  ChooseProjectParent,
  CloseProject,
  CommitStructuralEditPlan,
  CreateProject,
  DiscardEditSession,
  GetApplicationConfig,
  GetExecutionNodeContext,
  GetSessionCredentialStatus,
  OpenProject,
  ReviewStructuralEditSession,
  SetSessionCredential,
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
export interface ProjectBackend {
  getApplicationConfig(): Promise<ConfigResult>;
  chooseProject(): Promise<OpenResult>;
  openProject(root: string): Promise<OpenResult>;
  chooseProjectParent(): Promise<string>;
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
  clearSessionCredential?(): Promise<SessionCredentialStatus>;
  getExecutionNodeContext?(): Promise<ExecutionNodeContext>;
  selectExecutionNode?(hostId: string): Promise<ExecutionNodeContext>;
  verifyProject?(): Promise<VerificationStatus>;
}

export const backend: ProjectBackend = {
  getApplicationConfig: GetApplicationConfig,
  chooseProject: () => ChooseProject() as unknown as Promise<OpenResult>,
  openProject: (root) => OpenProject(root) as unknown as Promise<OpenResult>,
  chooseProjectParent: ChooseProjectParent,
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
  clearSessionCredential: ClearSessionCredential,
  getExecutionNodeContext: GetExecutionNodeContext,
  selectExecutionNode: SelectExecutionNode,
  verifyProject: () =>
    VerifyProject() as unknown as Promise<VerificationStatus>,
};

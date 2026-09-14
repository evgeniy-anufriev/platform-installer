import {
  AppendEditCommand,
  ChooseProject,
  ChooseProjectParent,
  CloseProject,
  CommitEditPlan,
  CreateProject,
  DiscardEditSession,
  GetApplicationConfig,
  GetExecutionNodeContext,
  GetSessionCredentialStatus,
  OpenProject,
  ReviewEditSession,
  SetSessionCredential,
  SelectExecutionNode,
  StartEditSession,
  ClearSessionCredential,
} from "../wailsjs/go/main/App";
import type { main } from "../wailsjs/go/models";

export type OpenResult = main.ProjectOpenResult;
export type EditResult = main.EditOperationResult;
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
  startEditSession(): Promise<main.EditOperationResult>;
  appendEditCommand(
    sessionId: string,
    command: Record<string, unknown>,
  ): Promise<main.EditOperationResult>;
  reviewEditSession(sessionId: string): Promise<main.EditOperationResult>;
  commitEditPlan(
    sessionId: string,
    planId: string,
  ): Promise<main.EditOperationResult>;
  discardEditSession(sessionId: string): Promise<main.EditOperationResult>;
  getSessionCredentialStatus?(): Promise<SessionCredentialStatus>;
  setSessionCredential?(
    input: SessionCredentialInput,
  ): Promise<SessionCredentialStatus>;
  clearSessionCredential?(): Promise<SessionCredentialStatus>;
  getExecutionNodeContext?(): Promise<ExecutionNodeContext>;
  selectExecutionNode?(hostId: string): Promise<ExecutionNodeContext>;
}

export const backend: ProjectBackend = {
  getApplicationConfig: GetApplicationConfig,
  chooseProject: ChooseProject,
  openProject: OpenProject,
  chooseProjectParent: ChooseProjectParent,
  createProject: CreateProject,
  closeProject: CloseProject,
  startEditSession: StartEditSession,
  appendEditCommand: (sessionId, command) =>
    AppendEditCommand(sessionId, command as never),
  reviewEditSession: ReviewEditSession,
  commitEditPlan: CommitEditPlan,
  discardEditSession: DiscardEditSession,
  getSessionCredentialStatus: GetSessionCredentialStatus,
  setSessionCredential: (input) => SetSessionCredential(input as never),
  clearSessionCredential: ClearSessionCredential,
  getExecutionNodeContext: GetExecutionNodeContext,
  selectExecutionNode: SelectExecutionNode,
};

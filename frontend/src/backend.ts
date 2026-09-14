import {
  AppendEditCommand,
  ChooseProject,
  ChooseProjectParent,
  CloseProject,
  CommitEditPlan,
  CreateProject,
  DiscardEditSession,
  GetApplicationConfig,
  ReviewEditSession,
  StartEditSession,
} from "../wailsjs/go/main/App";
import type { main } from "../wailsjs/go/models";

export type OpenResult = main.ProjectOpenResult;
export type EditResult = main.EditOperationResult;
export type ConfigResult = main.ApplicationConfigResult;
export interface ProjectBackend {
  getApplicationConfig(): Promise<ConfigResult>;
  chooseProject(): Promise<OpenResult>;
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
}

export const backend: ProjectBackend = {
  getApplicationConfig: GetApplicationConfig,
  chooseProject: ChooseProject,
  chooseProjectParent: ChooseProjectParent,
  createProject: CreateProject,
  closeProject: CloseProject,
  startEditSession: StartEditSession,
  appendEditCommand: (sessionId, command) =>
    AppendEditCommand(sessionId, command as never),
  reviewEditSession: ReviewEditSession,
  commitEditPlan: CommitEditPlan,
  discardEditSession: DiscardEditSession,
};

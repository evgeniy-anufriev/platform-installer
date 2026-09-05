import { ChooseProject, CloseProject } from "../wailsjs/go/main/App";
import type { main } from "../wailsjs/go/models";

export type OpenResult = main.ProjectOpenResult;
export interface ProjectBackend {
  chooseProject(): Promise<OpenResult>;
  closeProject(): Promise<OpenResult>;
}

export const backend: ProjectBackend = { chooseProject: ChooseProject, closeProject: CloseProject };

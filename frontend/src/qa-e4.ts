import type { ExecutionNodeContext, ProjectBackend } from "./backend";

let node: ExecutionNodeContext = { status: "NOT_PREPARED", selectionKind: "PROJECT_SERVER", selectionSource: "AUTO_FIRST_ELIGIBLE", selectedHostId: "node1", safeLabel: "node1 · 192.0.2.10", locked: true };
const project = { status: "OPEN", root: "QA:/e4", classification: "MANAGED_PROJECT", project: { id: "qa-e4", name: "E4 QA" }, counts: { servers: 2, deployments: 0, runs: 0 }, snapshot: { status: "PASS", project: { name: "E4 QA" }, projectRevision: "sha256:qa", snapshotFingerprint: "sha256:qa", hosts: { node1: { type: "infra", desiredHostname: "node1", ansibleHost: "192.0.2.10", ansiblePort: 22 }, node2: { type: "infra", desiredHostname: "node2", ansibleHost: "192.0.2.11", ansiblePort: 22 } }, serviceDeployments: {}, pki: {}, findings: [], documents: [] } };
export const qaE4Backend: ProjectBackend = {
  getApplicationConfig: async () => ({ status: "READY", config: { schemaVersion: 1, serverTypes: [{ id: "infra", displayName: "Infrastructure" }] } } as never),
  chooseProject: async () => project as never, openProject: async () => project as never, chooseProjectParent: async () => "", createProject: async () => project as never, closeProject: async () => ({ status: "NO_PROJECT" } as never),
  startEditSession: async () => ({ status: "EDITING", session: { sessionId: "qa", commandCount: 0 } } as never), appendEditCommand: async () => ({ status: "EDITING", session: { sessionId: "qa", commandCount: 1 } } as never), reviewEditSession: async () => ({ status: "BLOCKED" } as never), commitEditPlan: async () => ({ status: "BLOCKED" } as never), discardEditSession: async () => ({ status: "DISCARDED" } as never),
  getSessionCredentialStatus: async () => ({ status: "MISSING", sudoPasswordStatus: "NOT_PROVIDED" }), setSessionCredential: async () => ({ status: "MISSING", sudoPasswordStatus: "NOT_PROVIDED" }), clearSessionCredential: async () => ({ status: "MISSING", sudoPasswordStatus: "NOT_PROVIDED" }),
  getExecutionNodeContext: async () => node,
  selectExecutionNode: async (hostId) => { node = { ...node, selectionSource: "EXPLICIT", selectedHostId: hostId, safeLabel: hostId === "node2" ? "node2 · 192.0.2.11" : "node1 · 192.0.2.10" }; return node; },
};

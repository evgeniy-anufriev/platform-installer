package desktop

import "platform-installer/internal/installer"

const (
	installationStatePrerequisitesRequired = "PREREQUISITES_REQUIRED"
	installationStateReadyToPlan           = "READY_TO_PLAN"
	installationPlanNotCreated             = "NOT_CREATED"
)

// InstallationState is the closed, read-only Wails projection for UI-02A.
// It intentionally contains no plan actions, runtime paths, transport details,
// Core output, or credentials. Future UI-02 slices may add bounded plan/run
// summaries without changing the desired project.
type InstallationState struct {
	APIVersion    string                     `json:"apiVersion"`
	Kind          string                     `json:"kind"`
	Status        string                     `json:"status"`
	Project       *InstallationProjectState  `json:"project,omitempty"`
	ExecutionNode InstallationNodeState      `json:"executionNode"`
	Plan          InstallationPlanState      `json:"plan"`
	Prerequisites []InstallationPrerequisite `json:"prerequisites,omitempty"`
}

type InstallationProjectState struct {
	ID                 string `json:"id"`
	Revision           string `json:"revision"`
	VerificationStatus string `json:"verificationStatus"`
	HasUnsavedChanges  bool   `json:"hasUnsavedChanges"`
}

type InstallationNodeState struct {
	Status    string `json:"status"`
	SafeLabel string `json:"safeLabel,omitempty"`
}

type InstallationPlanState struct {
	Status string `json:"status"`
	PlanID string `json:"planId,omitempty"`
}

type InstallationPrerequisite struct {
	Code        string `json:"code"`
	Destination string `json:"destination"`
	SafeMessage string `json:"safeMessage"`
}

// GetInstallationState performs only a bounded local read of the canonical
// revision. It never calls Core, an Execution Node, or a target host.
func (a *App) GetInstallationState() InstallationState {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()

	state := InstallationState{
		APIVersion:    "platform.installer/installation-state/v1alpha1",
		Kind:          "InstallationState",
		Status:        installationStatePrerequisitesRequired,
		ExecutionNode: installationNodeState(a.execution.context),
		Plan:          InstallationPlanState{Status: installationPlanNotCreated},
	}
	if a.current.Status != "OPEN" || a.current.Root == "" || a.current.Project == nil || a.current.Project.ID == "" {
		return state.withPrerequisite("PROJECT_NOT_OPEN", "project", "Open or create a project before installation.")
	}

	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return state.withPrerequisite("PROJECT_REVISION_UNAVAILABLE", "project", "The saved project revision cannot be read safely.")
	}
	state.Project = &InstallationProjectState{
		ID:                 a.current.Project.ID,
		Revision:           revision,
		VerificationStatus: installationVerificationStatus(a.current.Verification.Status),
		HasUnsavedChanges:  a.activeSession != "",
	}
	if a.activeSession != "" {
		if a.installationPlanID != "" {
			state.Plan.Status = "PLAN_STALE_OR_EXPIRED"
		}
		return state.withPrerequisite("PROJECT_CHANGES_UNSAVED", "project", "Save or discard the current changes before creating an installation plan.")
	}
	state.Plan = a.installationPlanStateLocked()
	if a.execution.context.Status != "READY" {
		return state.withPrerequisite("EXECUTION_NODE_READY_REQUIRED", "servers", "A READY Execution Node is required before creating an installation plan.")
	}
	if _, err := a.resolveSelectedExecutionNodeBindingLocked(); err != nil {
		return state.withPrerequisite("EXECUTION_NODE_BINDING_REQUIRED", "servers", "The selected Execution Node has no trusted runtime binding.")
	}
	if state.Plan.Status != installationPlanNotCreated && state.Plan.Status != "PLAN_STALE_OR_EXPIRED" {
		state.Status = state.Plan.Status
		return state
	}
	state.Status = installationStateReadyToPlan
	return state
}

func (a *App) installationPlanStateLocked() InstallationPlanState {
	if a.installationPlanID == "" {
		return InstallationPlanState{Status: installationPlanNotCreated}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		a.installationPlanID = ""
		return InstallationPlanState{Status: "PLAN_STALE_OR_EXPIRED"}
	}
	record, err := binding.plans.GetPlan(a.installationPlanID)
	if err != nil {
		a.installationPlanID = ""
		return InstallationPlanState{Status: "PLAN_STALE_OR_EXPIRED"}
	}
	status := "PLAN_REVIEW"
	if record.Consumed {
		return InstallationPlanState{Status: "PLAN_STALE_OR_EXPIRED"}
	}
	if record.Plan.Status == "BLOCKED" {
		status = "PLAN_BLOCKED"
	} else if record.Approved {
		status = "PLAN_APPROVED"
	}
	return InstallationPlanState{Status: status, PlanID: record.ID}
}

func installationNodeState(context ExecutionNodeContext) InstallationNodeState {
	return InstallationNodeState{Status: context.Status, SafeLabel: context.SafeLabel}
}

func installationVerificationStatus(status string) string {
	switch status {
	case "VERIFIED", "INVALID", "VERIFYING", "STALE", "UNAVAILABLE", "UNVERIFIED":
		return status
	default:
		return "UNVERIFIED"
	}
}

func (state InstallationState) withPrerequisite(code, destination, message string) InstallationState {
	state.Prerequisites = []InstallationPrerequisite{{Code: code, Destination: destination, SafeMessage: message}}
	return state
}

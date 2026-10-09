package main

import (
	"errors"
	"sort"
	"strings"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
)

const maxInstallationPlanFindings = 64

// InstallationPlanOperation is the only UI-02B mutation response. Its plan is
// a bounded in-memory projection of a Core-owned PlanRecord, never a portable
// project document or a Start authorization.
type InstallationPlanOperation struct {
	Status string                `json:"status"`
	Plan   *InstallationPlanView `json:"plan,omitempty"`
	Error  *ProjectOpenError     `json:"error,omitempty"`
}

type InstallationPlanView struct {
	ID                                    string                        `json:"id"`
	Status                                string                        `json:"status"`
	ProjectRevision                       string                        `json:"projectRevision"`
	PlanFingerprint                       string                        `json:"planFingerprint"`
	ExecutionNodeID                       string                        `json:"executionNodeId"`
	Runtime                               InstallationRuntimeBinding    `json:"runtime"`
	ExpiresAt                             string                        `json:"expiresAt"`
	Approved                              bool                          `json:"approved"`
	Acknowledgements                      []InstallationAcknowledgement `json:"acknowledgements"`
	Phases                                []InstallationPlanPhase       `json:"phases"`
	Findings                              []InstallationPlanFinding     `json:"findings,omitempty"`
	PKIStorePasswordRequired              bool                          `json:"pkiStorePasswordRequired"`
	SecretOutputEncryptionRequired        bool                          `json:"secretOutputEncryptionRequired"`
	SecretOutputEncryptionPasswordPresent bool                          `json:"secretOutputEncryptionPasswordPresent"`
}

type InstallationRuntimeBinding struct {
	BundleDigest  string `json:"bundleDigest"`
	CoreVersion   string `json:"coreVersion"`
	CatalogDigest string `json:"catalogDigest"`
	Protocol      string `json:"protocol"`
}

type InstallationAcknowledgement struct {
	Code    string `json:"code"`
	Summary string `json:"summary"`
}

type InstallationPlanPhase struct {
	ID      string                   `json:"id"`
	Order   int                      `json:"order"`
	Actions []InstallationPlanAction `json:"actions"`
}

type InstallationPlanAction struct {
	ID                string   `json:"id"`
	Type              string   `json:"type"`
	ServiceDeployment string   `json:"serviceDeployment,omitempty"`
	Targets           []string `json:"targets"`
	DependsOn         []string `json:"dependsOn"`
	Mutating          bool     `json:"mutating"`
	Reboot            string   `json:"reboot"`
	Summary           string   `json:"summary"`
}

type InstallationPlanFinding struct {
	Code        string `json:"code"`
	SafeMessage string `json:"safeMessage"`
}

func (a *App) CreateInstallationPlan(deploymentOrder []string) InstallationPlanOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Root == "" || a.current.Project == nil || a.current.Project.ID == "" {
		return installationPlanFailure(errors.New("PROJECT_NOT_OPEN"))
	}
	if a.activeSession != "" {
		return installationPlanFailure(errors.New("PROJECT_CHANGES_UNSAVED"))
	}
	if a.execution.context.Status != "READY" {
		return installationPlanFailure(errors.New("EXECUTION_NODE_READY_REQUIRED"))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		if err == nil {
			err = errors.New("EXECUTION_NODE_BINDING_REQUIRED")
		}
		return installationPlanFailure(err)
	}
	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return installationPlanFailure(errors.New("PROJECT_REVISION_UNAVAILABLE"))
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	record, err := binding.plans.CreatePlanWithOrder(ctx, binding.node, a.current.Root, binding.reader.runtimeRelease, deploymentOrder)
	if err != nil {
		if binding.dynamic {
			a.invalidateDynamicBindingLocked()
		}
		return installationPlanFailure(err)
	}
	if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
		return installationPlanFailure(err)
	}
	if !installationPlanMatches(record, a.current.Project.ID, revision, binding) {
		return installationPlanFailure(errors.New("PROJECT_REVISION_CHANGED"))
	}
	a.installationPlanID = record.ID
	view, err := installationPlanView(record, binding)
	if err != nil {
		a.installationPlanID = ""
		return installationPlanFailure(err)
	}
	view.SecretOutputEncryptionRequired = a.secretOutputEncryptionRequiredLocked()
	view.SecretOutputEncryptionPasswordPresent = a.secretOutputEncryptionPasswordPresentLocked()
	return InstallationPlanOperation{Status: installationPlanStateFor(record), Plan: &view}
}

func (a *App) GetInstallationPlan(planID string) InstallationPlanOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	return a.getInstallationPlanLocked(planID)
}

func (a *App) ApproveInstallationPlan(planID string, acknowledgements []string) InstallationPlanOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if planID == "" || planID != a.installationPlanID {
		return installationPlanFailure(errors.New("INSTALLATION_PLAN_NOT_FOUND"))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		return installationPlanFailure(errors.New("EXECUTION_NODE_BINDING_REQUIRED"))
	}
	record, err := binding.plans.GetPlan(planID)
	if err != nil {
		a.installationPlanID = ""
		return installationPlanFailure(err)
	}
	if a.current.Status != "OPEN" || a.current.Root == "" || a.current.Project == nil {
		a.installationPlanID = ""
		return installationPlanFailure(errors.New("PLAN_STALE"))
	}
	revision, revisionErr := installer.ProjectRevision(a.current.Root)
	if revisionErr != nil || !installationPlanMatches(record, a.current.Project.ID, revision, binding) {
		a.installationPlanID = ""
		return installationPlanFailure(errors.New("PLAN_STALE"))
	}
	view, viewErr := installationPlanView(record, binding)
	if viewErr != nil {
		return installationPlanFailure(viewErr)
	}
	view.SecretOutputEncryptionRequired = a.secretOutputEncryptionRequiredLocked()
	view.SecretOutputEncryptionPasswordPresent = a.secretOutputEncryptionPasswordPresentLocked()
	approvalFailure := func(err *ProjectOpenError) InstallationPlanOperation {
		return InstallationPlanOperation{Status: installationPlanStateFor(record), Plan: &view, Error: err}
	}
	if a.secretOutputEncryptionRequiredLocked() {
		credentialBinding, bindingErr := a.credentialBindingLocked()
		if bindingErr != nil || !a.secrets.HasOutputEncryptionPassword(credentialBinding) {
			code := "SECRET_OUTPUT_ENCRYPTION_PASSWORD_REQUIRED"
			return approvalFailure(&ProjectOpenError{Code: code, Message: projectErrorMessage(code)})
		}
	}
	missing, secretErr := a.missingInstallationSecretsLocked(record.Plan, false)
	if secretErr != nil {
		code := projectErrorCode(secretErr)
		return approvalFailure(&ProjectOpenError{Code: code, Message: projectErrorMessage(code)})
	}
	if len(missing) > 0 {
		return approvalFailure(missingInstallationSecretsError(missing))
	}
	if err := binding.plans.ApprovePlan(planID, append([]string(nil), acknowledgements...)); err != nil {
		code := projectErrorCode(err)
		return approvalFailure(&ProjectOpenError{Code: code, Message: projectErrorMessage(code)})
	}
	return a.getInstallationPlanLocked(planID)
}

// missingInstallationSecretsLocked uses only the current Core plan and the
// Core-attested descriptor set. Values remain private inside the broker.
func (a *App) missingInstallationSecretsLocked(plan executionnode.DeploymentPlan, attest bool) ([]string, error) {
	passwords, err := installationPlanRuntimeSecretRequirements(plan)
	if err != nil {
		return nil, err
	}
	labels := map[string]string{"pki-store-password": "Сертификаты: пароль PKCS#12"}
	for _, descriptor := range a.runtimeSecretEvidenceDescriptorsLocked(plan.ProjectRevision) {
		label := descriptor.DisplayLabel
		if descriptor.ServiceDeployment != "" {
			label = descriptor.ServiceDeployment + ": " + label
		}
		labels[descriptor.RequirementRef] = label
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return nil, err
	}
	missing := a.secrets.MissingRequiredSecrets(binding, passwords, executionnodePlanRequiresPKIStorePassword(plan), !attest)
	if len(missing) > 0 || !attest || len(passwords) == 0 {
		for i, reference := range missing {
			if label := labels[reference]; label != "" {
				missing[i] = label
			}
		}
		return missing, nil
	}
	if len(passwords) > 0 {
		currentDescriptors := a.runtimeSecretEvidenceDescriptorsLocked(plan.ProjectRevision)
		if currentDescriptors == nil {
			descriptors := a.getRuntimeSecretDescriptorsLocked(false)
			if descriptors.Status != "READY" {
				if descriptors.Error != nil && descriptors.Error.Code != "" {
					return nil, errors.New(descriptors.Error.Code)
				}
				return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
			}
			currentDescriptors = descriptors.Descriptors
		}
		known := map[string]bool{}
		for _, descriptor := range currentDescriptors {
			known[descriptor.RequirementRef+"\x00"+descriptor.Purpose] = true
			label := descriptor.DisplayLabel
			if descriptor.ServiceDeployment != "" {
				label = descriptor.ServiceDeployment + ": " + label
			}
			labels[descriptor.RequirementRef] = label
		}
		for _, reference := range passwords {
			if !known[reference+"\x00SERVICE_PASSWORD"] {
				return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
			}
		}
	}
	missing = a.secrets.MissingRequiredSecrets(binding, passwords, executionnodePlanRequiresPKIStorePassword(plan), false)
	for i, reference := range missing {
		if label := labels[reference]; label != "" {
			missing[i] = label
		}
	}
	return missing, nil
}

func (a *App) runtimeSecretEvidenceDescriptorsLocked(revision string) []RuntimeSecretDescriptorView {
	if a.runtimeSecretEvidence == nil || a.runtimeSecretEvidence.projectRevision != revision || a.current.Project == nil || a.runtimeSecretEvidence.projectID != a.current.Project.ID || a.binding == nil || a.runtimeSecretEvidence.nodeID != a.binding.node.ID || !runtimeEvidenceMatchesExpected(a.runtimeSecretEvidence.runtime, a.binding.reader.runtimeRelease) {
		return nil
	}
	return a.runtimeSecretEvidence.descriptors
}

func missingInstallationSecretsError(missing []string) *ProjectOpenError {
	return &ProjectOpenError{Code: "INSTALLATION_SECRETS_MISSING", Message: "Задайте обязательные секреты перед одобрением и запуском плана: " + strings.Join(missing, "; ") + "."}
}

func (a *App) getInstallationPlanLocked(planID string) InstallationPlanOperation {
	if planID == "" || planID != a.installationPlanID {
		return installationPlanFailure(errors.New("INSTALLATION_PLAN_NOT_FOUND"))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		return installationPlanFailure(errors.New("EXECUTION_NODE_BINDING_REQUIRED"))
	}
	record, err := binding.plans.GetPlan(planID)
	if err != nil {
		a.installationPlanID = ""
		return installationPlanFailure(err)
	}
	if record.Consumed {
		return installationPlanFailure(errors.New("PLAN_STALE"))
	}
	revision, revisionErr := installer.ProjectRevision(a.current.Root)
	if revisionErr != nil || !installationPlanMatches(record, a.current.Project.ID, revision, binding) {
		a.installationPlanID = ""
		return installationPlanFailure(errors.New("PLAN_STALE"))
	}
	view, err := installationPlanView(record, binding)
	if err != nil {
		return installationPlanFailure(err)
	}
	view.SecretOutputEncryptionRequired = a.secretOutputEncryptionRequiredLocked()
	view.SecretOutputEncryptionPasswordPresent = a.secretOutputEncryptionPasswordPresentLocked()
	return InstallationPlanOperation{Status: installationPlanStateFor(record), Plan: &view}
}

func installationPlanMatches(record executionnode.PlanRecord, projectID, revision string, binding *executionNodeBinding) bool {
	if record.ID == "" || record.ID != record.Plan.ID || record.Plan.ProjectRevision != revision || !sameRuntimeRelease(record.Plan.RuntimeRelease, binding.reader.runtimeRelease) {
		return false
	}
	return record.Plan.Status == "BLOCKED" || record.Plan.ProjectIdentity == projectID
}

func sameRuntimeRelease(left, right map[string]any) bool {
	if len(left) != len(right) {
		return false
	}
	for key, value := range left {
		if right[key] != value {
			return false
		}
	}
	return true
}

func installationPlanView(record executionnode.PlanRecord, binding *executionNodeBinding) (InstallationPlanView, error) {
	runtime, ok := installationRuntimeBinding(record.Plan.RuntimeRelease)
	if !ok || record.ID == "" || record.Plan.PlanFingerprint == "" || record.Plan.ProjectRevision == "" {
		return InstallationPlanView{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	view := InstallationPlanView{ID: record.ID, Status: record.Plan.Status, ProjectRevision: record.Plan.ProjectRevision,
		PlanFingerprint: record.Plan.PlanFingerprint, ExecutionNodeID: binding.node.ID, Runtime: runtime,
		ExpiresAt: record.ExpiresAt.UTC().Format(time.RFC3339), Approved: record.Approved,
		Acknowledgements: make([]InstallationAcknowledgement, 0, len(record.Plan.AcknowledgementDetails)),
		Phases:           make([]InstallationPlanPhase, 0, len(record.Plan.Phases)), Findings: safeInstallationPlanFindings(record.Plan.Findings),
		PKIStorePasswordRequired: executionnodePlanRequiresPKIStorePassword(record.Plan)}
	for _, acknowledgement := range record.Plan.AcknowledgementDetails {
		view.Acknowledgements = append(view.Acknowledgements, InstallationAcknowledgement{Code: acknowledgement.Code, Summary: acknowledgement.Summary})
	}
	for _, phase := range record.Plan.Phases {
		projected := InstallationPlanPhase{ID: phase.ID, Order: phase.Order, Actions: make([]InstallationPlanAction, 0, len(phase.Actions))}
		for _, action := range phase.Actions {
			projected.Actions = append(projected.Actions, InstallationPlanAction{ID: action.ID, Type: action.Type, ServiceDeployment: action.ServiceDeployment,
				Targets: append([]string{}, action.Targets...), DependsOn: append([]string{}, action.DependsOn...), Mutating: action.Mutating, Reboot: action.Reboot, Summary: action.Summary})
		}
		view.Phases = append(view.Phases, projected)
	}
	return view, nil
}

func executionnodePlanRequiresPKIStorePassword(plan executionnode.DeploymentPlan) bool {
	for _, requirement := range plan.RequiredCredentials {
		if requirement.RequirementRef == "pki-store-password" && requirement.Purpose == "PKI_STORE_PASSWORD" {
			return true
		}
	}
	return false
}

// installationPlanRuntimeSecretRequirements is intentionally derived from the
// fresh Core plan rather than the UI catalog. It is used only to bind already
// pending runtime-only values at the pre-target Start gate.
func installationPlanRuntimeSecretRequirements(plan executionnode.DeploymentPlan) ([]string, error) {
	result := make([]string, 0)
	seen := map[string]struct{}{}
	for _, requirement := range plan.RequiredCredentials {
		if requirement.Purpose != "SERVICE_PASSWORD" {
			continue
		}
		if !runtimeSecretDescriptorRequirement.MatchString(requirement.RequirementRef) {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
		}
		if _, duplicate := seen[requirement.RequirementRef]; duplicate {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
		}
		seen[requirement.RequirementRef] = struct{}{}
		result = append(result, requirement.RequirementRef)
	}
	sort.Strings(result)
	return result, nil
}

func installationRuntimeBinding(release map[string]any) (InstallationRuntimeBinding, bool) {
	bundleDigest, bundleOK := release["bundleDigest"].(string)
	coreVersion, coreOK := release["coreVersion"].(string)
	catalogDigest, catalogOK := release["catalogDigest"].(string)
	protocol, protocolOK := release["planningProtocol"].(string)
	if !bundleOK || !coreOK || !catalogOK || !protocolOK || !validPlanDigest(bundleDigest) || !validPlanDigest(catalogDigest) || len(coreVersion) == 0 || len(coreVersion) > 128 || len(protocol) == 0 || len(protocol) > 128 {
		return InstallationRuntimeBinding{}, false
	}
	return InstallationRuntimeBinding{BundleDigest: bundleDigest, CoreVersion: coreVersion, CatalogDigest: catalogDigest, Protocol: protocol}, true
}

func validPlanDigest(value string) bool {
	if len(value) != len("sha256:")+64 || len(value) < 8 || value[:7] != "sha256:" {
		return false
	}
	for _, character := range value[7:] {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}

func safeInstallationPlanFindings(findings []executionnode.Finding) []InstallationPlanFinding {
	if len(findings) > maxInstallationPlanFindings {
		findings = findings[:maxInstallationPlanFindings]
	}
	result := make([]InstallationPlanFinding, 0, len(findings))
	for _, finding := range findings {
		if finding.Code == "" || len(finding.Code) > 128 || finding.SafeMessage == "" || len(finding.SafeMessage) > 512 {
			continue
		}
		result = append(result, InstallationPlanFinding{Code: finding.Code, SafeMessage: finding.SafeMessage})
	}
	return result
}

func installationPlanStateFor(record executionnode.PlanRecord) string {
	if record.Plan.Status == "BLOCKED" {
		return "PLAN_BLOCKED"
	}
	if record.Approved {
		return "PLAN_APPROVED"
	}
	return "PLAN_REVIEW"
}

func installationPlanFailure(err error) InstallationPlanOperation {
	code := projectErrorCode(err)
	return InstallationPlanOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code), DiagnosticCodes: runtimeSecretDescriptorDiagnosticCodes(err)}}
}

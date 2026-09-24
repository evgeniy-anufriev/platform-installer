package main

import (
	"context"
	"errors"
	"regexp"
	"sort"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

// projectSnapshotReader is intentionally narrower than the future editor
// backend: UI-01B can only obtain an authoritative read-only Core projection.
type projectSnapshotReader interface {
	BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error)
}

type projectReader struct {
	transport      projectSnapshotReader
	node           executionnode.Node
	runtimeRelease map[string]any
}

type verificationSnapshot struct {
	Snapshot *coreadapter.Snapshot
	Runtime  executionnode.RuntimeEvidence
	NodeID   string
}

func (r projectReader) BuildVerificationSnapshot(ctx context.Context, root string) (verificationSnapshot, error) {
	transport, ok := r.transport.(interface {
		BuildProjectVerificationSnapshot(context.Context, executionnode.Node, string, map[string]any) (executionnode.ProjectVerificationSnapshot, error)
	})
	if !ok || r.node.ID == "" || len(r.runtimeRelease) == 0 {
		return verificationSnapshot{}, errors.New("EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED")
	}
	result, err := transport.BuildProjectVerificationSnapshot(ctx, r.node, root, r.runtimeRelease)
	if err != nil {
		return verificationSnapshot{}, err
	}
	if !runtimeEvidenceMatchesExpected(result.Runtime, r.runtimeRelease) {
		return verificationSnapshot{}, errors.New("EXECUTION_RUNTIME_IDENTITY_MISMATCH")
	}
	return verificationSnapshot{Snapshot: result.Snapshot, Runtime: result.Runtime, NodeID: r.node.ID}, nil
}

func runtimeEvidenceMatchesExpected(actual executionnode.RuntimeEvidence, expected map[string]any) bool {
	for key, actualValue := range map[string]string{"bundleDigest": actual.BundleDigest, "coreVersion": actual.CoreVersion, "catalogDigest": actual.CatalogDigest} {
		requested, present := expected[key]
		if !present || requested != actualValue {
			return false
		}
	}
	planningProtocol, ok := expected["planningProtocol"].(string)
	return ok && planningProtocol != "" && actual.Protocol != "" && planningProtocol == actual.Protocol
}

func (r projectReader) BuildSnapshot(ctx context.Context, root string) (*coreadapter.Snapshot, error) {
	if r.transport == nil || r.node.ID == "" || len(r.runtimeRelease) == 0 {
		return nil, errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return r.transport.BuildProjectSnapshot(ctx, r.node, root, r.runtimeRelease)
}

type unavailableProjectReader struct{}

func (unavailableProjectReader) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return nil, errors.New("EXECUTION_NODE_NOT_CONFIGURED")
}

type ProjectOpenResult struct {
	Status         string                               `json:"status"`
	Root           string                               `json:"root,omitempty"`
	Classification string                               `json:"classification,omitempty"`
	Project        *projectlifecycle.Project            `json:"project,omitempty"`
	Counts         projectlifecycle.Counts              `json:"counts"`
	Catalog        *projectlifecycle.ProjectCatalogView `json:"catalog,omitempty"`
	Snapshot       *coreadapter.Snapshot                `json:"snapshot,omitempty"`
	Managed        *installer.ManagedProjectView        `json:"managed,omitempty"`
	Verification   ProjectVerification                  `json:"verification"`
	Diagnostics    []ApplicationDiagnostic              `json:"diagnostics,omitempty"`
	Error          *ProjectOpenError                    `json:"error,omitempty"`
}

type ProjectVerification struct {
	APIVersion        string                         `json:"apiVersion"`
	Kind              string                         `json:"kind"`
	Status            string                         `json:"status"`
	ProjectIdentity   string                         `json:"projectIdentity,omitempty"`
	ProjectRevision   string                         `json:"projectRevision,omitempty"`
	ExecutionNodeID   string                         `json:"executionNodeId,omitempty"`
	Runtime           *executionnode.RuntimeEvidence `json:"runtime,omitempty"`
	Findings          []VerificationFinding          `json:"findings,omitempty"`
	FindingsTruncated bool                           `json:"findingsTruncated,omitempty"`
	CheckedAt         time.Time                      `json:"checkedAt,omitempty"`
	Error             *ProjectOpenError              `json:"error,omitempty"`
}

type VerificationFinding struct {
	Code        string `json:"code"`
	Severity    string `json:"severity"`
	Summary     string `json:"summary"`
	SubjectKind string `json:"subjectKind,omitempty"`
	SubjectID   string `json:"subjectId,omitempty"`
	HelpRef     string `json:"helpRef,omitempty"`
}

func notVerified() ProjectVerification {
	return ProjectVerification{APIVersion: "platform.installer/project-verification/v1alpha1", Kind: "ProjectVerification", Status: "UNVERIFIED"}
}

type ProjectOpenError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type ApplicationDiagnostic struct {
	Code        string `json:"code"`
	Severity    string `json:"severity"`
	HostID      string `json:"hostId,omitempty"`
	SafeMessage string `json:"safeMessage"`
}

type ApplicationConfigResult struct {
	Status string            `json:"status"`
	Config *appconfig.Config `json:"config,omitempty"`
	Error  *ProjectOpenError `json:"error,omitempty"`
}

type RuntimeSecretDescriptorView struct {
	RequirementRef, Purpose, ServiceDeployment, DisplayLabel string
	Hosts                                                    []string
}

type RuntimeSecretDescriptorOperation struct {
	Status, ProjectRevision, DescriptorSetFingerprint string
	Descriptors                                       []RuntimeSecretDescriptorView
	Error                                             *ProjectOpenError `json:"error,omitempty"`
}

// RuntimeSecretValuesInput is one non-persistent submission for a single
// Core-derived service deployment. Values are accepted but never returned.
type RuntimeSecretValuesInput struct {
	ProjectRevision          string            `json:"projectRevision"`
	DescriptorSetFingerprint string            `json:"descriptorSetFingerprint"`
	ServiceDeployment        string            `json:"serviceDeployment"`
	Values                   map[string]string `json:"values"`
}

type runtimeSecretDescriptorEvidence struct {
	projectID, projectRevision, nodeID, fingerprint string
	runtime                                         executionnode.RuntimeEvidence
	descriptors                                     []RuntimeSecretDescriptorView
}

var runtimeSecretDescriptorRequirement = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)

type App struct {
	ctx    context.Context
	reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	projectRevision        func(string) (string, error)
	lifecycle              projectLifecycle
	current                ProjectOpenResult
	sessions               *installer.EditSessionStore
	editor                 *installer.Backend
	activeSession          string
	editMu                 sync.Mutex
	config                 appconfig.Config
	configErr              error
	secrets                *runtimesecret.Broker
	execution              *executionNodeContextStore
	binding                *executionNodeBinding
	continuation           *verificationContinuation
	export                 *installer.ProjectExport
	installationPlanID     string
	installationRuns       *installationRunRegistry
	installationGeneration uint64
	runtimeSecretEvidence  *runtimeSecretDescriptorEvidence
}

type AppOption func(*App)

func WithApplicationConfig(config appconfig.Config, err error) AppOption {
	return func(app *App) {
		app.config, app.configErr = config, err
		if err == nil {
			app.configErr = appconfig.Validate(config)
		}
	}
}

// WithExplicitExecutionNode supplies only a safe display identity for the
// existing startup-configured Execution Node. It never changes its transport.
func WithExplicitExecutionNode(id, address string) AppOption {
	return func(app *App) {
		if id == "" || address == "" {
			return
		}
		app.execution.external = &executionNodeCandidate{hostID: id, label: id + " · " + address}
	}
}

// WithTrustedExecutionNodeBinding supplies the private, startup-validated
// binding used by the existing read-only project reader. It is deliberately
// not derived from an E4 candidate or Wails input.
func WithTrustedExecutionNodeBinding(binding executionNodeBinding) AppOption {
	return func(app *App) {
		app.binding = &binding
	}
}

type projectLifecycle interface {
	CreateProject(context.Context, projectlifecycle.CreateProjectRequest) (projectlifecycle.Result, error)
	OpenProject(context.Context, string) (projectlifecycle.Result, error)
	ResolveProjectCatalog(context.Context, string) (*projectlifecycle.ProjectCatalogView, error)
}

func NewApp(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, lifecycle projectLifecycle, options ...AppOption) *App {
	app := &App{reader: reader, lifecycle: lifecycle, projectRevision: installer.ProjectRevision, sessions: installer.NewEditSessionStore(), current: ProjectOpenResult{Status: "NO_PROJECT"}, configErr: errors.New("APPLICATION_CONFIG_NOT_FOUND"), secrets: runtimesecret.NewBroker(), execution: newExecutionNodeContextStore(nil, probeLocalExecutionNodeCandidate()), installationRuns: newInstallationRunRegistry()}
	for _, option := range options {
		option(app)
	}
	app.configureTargetCredentialLease()
	return app
}

func (a *App) GetApplicationConfig() ApplicationConfigResult {
	if a.configErr != nil {
		code := projectErrorCode(a.configErr)
		return ApplicationConfigResult{Status: "ERROR", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
	}
	config := a.config
	return ApplicationConfigResult{Status: "READY", Config: &config}
}

func (a *App) serverTypeDiagnostics(snapshot *coreadapter.Snapshot) []ApplicationDiagnostic {
	if snapshot == nil || a.configErr != nil {
		return nil
	}
	var diagnostics []ApplicationDiagnostic
	hostIDs := make([]string, 0, len(snapshot.Hosts))
	for hostID := range snapshot.Hosts {
		hostIDs = append(hostIDs, hostID)
	}
	sort.Strings(hostIDs)
	for _, hostID := range hostIDs {
		host := snapshot.Hosts[hostID]
		typeID, _ := host["type"].(string)
		if typeID == "" {
			diagnostics = append(diagnostics, ApplicationDiagnostic{Code: "LEGACY_SERVER_TYPE_MISSING", Severity: "WARNING", HostID: hostID, SafeMessage: "Server type is missing and must be selected before editing this server"})
		} else if !a.config.HasServerType(typeID) {
			diagnostics = append(diagnostics, ApplicationDiagnostic{Code: "UNKNOWN_CONFIGURED_SERVER_TYPE", Severity: "WARNING", HostID: hostID, SafeMessage: "Server type is not present in the current application configuration"})
		}
	}
	return diagnostics
}

func (a *App) managedServerTypeDiagnostics(view *installer.ManagedProjectView) []ApplicationDiagnostic {
	if view == nil || a.configErr != nil {
		return nil
	}
	hosts := managedSnapshotHosts(view)
	return a.serverTypeDiagnostics(&coreadapter.Snapshot{Hosts: hosts})
}

func (a *App) startup(ctx context.Context) { a.ctx = ctx }

func (a *App) shutdown(context.Context) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.secrets.Close()
	a.installationRuns.clear()
	a.execution.clear()
	a.continuation = nil
	a.clearProjectExportLocked()
}

func (a *App) ChooseProject() ProjectOpenResult {
	if a.ctx == nil {
		return a.failure("UI_NOT_READY")
	}
	root, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{Title: "Открыть существующий проект"})
	if err != nil {
		return a.failure("PROJECT_SELECTION_FAILED")
	}
	if root == "" {
		return a.CurrentProject()
	}
	return a.OpenProject(root)
}

func (a *App) ChooseProjectParent() string {
	if a.ctx == nil {
		return ""
	}
	root, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{Title: "Выбрать папку для нового проекта"})
	if err != nil {
		return ""
	}
	return root
}

// ChooseProjectExportParent only selects a directory. It never creates,
// validates or publishes an export destination.
func (a *App) ChooseProjectExportParent() string {
	if a.ctx == nil {
		return ""
	}
	root, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{Title: "Выбрать папку для экспорта проекта"})
	if err != nil {
		return ""
	}
	return root
}

func (a *App) CreateProject(request projectlifecycle.CreateProjectRequest) ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.clearProjectExportLocked()
	if a.lifecycle == nil {
		return a.failure("PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE")
	}
	result, err := a.lifecycle.CreateProject(context.Background(), request)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	a.secrets.Clear()
	a.installationRuns.clear()
	a.current = ProjectOpenResult{Status: "OPEN", Root: result.Root, Classification: result.Classification, Project: result.Project, Counts: result.Counts, Catalog: result.Catalog, Verification: notVerified()}
	a.bindExecutionLocked(result.Root, result.Project, nil)
	return a.current
}

func (a *App) OpenProject(root string) ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.clearProjectExportLocked()
	if a.lifecycle == nil {
		return a.failure("PROJECT_OPEN_BLOCKED")
	}
	for attempt := 0; attempt < 2; attempt++ {
		r0, revisionErr := a.projectRevision(root)
		if revisionErr != nil {
			return a.failure(projectErrorCode(revisionErr))
		}
		local, err := a.lifecycle.OpenProject(context.Background(), root)
		if err != nil {
			return a.failure(projectErrorCode(err))
		}
		if local.Classification == projectlifecycle.ClassificationEmpty {
			r1, afterErr := a.projectRevision(local.Root)
			if afterErr != nil {
				return a.failure(projectErrorCode(afterErr))
			}
			if r0 != r1 {
				continue
			}
			a.clearCredentialForReplacementLocked(local.Root, local.Project)
			a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project, Counts: local.Counts, Catalog: local.Catalog, Verification: notVerified()}
			a.bindExecutionLocked(local.Root, local.Project, nil)
			return a.current
		}
		if local.Classification == projectlifecycle.ClassificationManaged && local.Project != nil {
			managed, managedErr := installer.ReadManagedProjectViewWithCatalog(local.Root, local.Catalog)
			if managedErr != nil {
				return a.failure(projectErrorCode(managedErr))
			}
			r1, afterErr := a.projectRevision(local.Root)
			if afterErr != nil {
				return a.failure(projectErrorCode(afterErr))
			}
			if r0 != r1 || managed.ProjectRevision != r0 {
				continue
			}
			local.Counts.Servers = len(managed.Servers)
			local.Counts.Deployments = len(managed.Deployments)
			a.clearCredentialForReplacementLocked(local.Root, local.Project)
			a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project,
				Counts: local.Counts, Catalog: local.Catalog, Managed: managed, Verification: notVerified(), Diagnostics: a.managedServerTypeDiagnostics(managed)}
			a.bindExecutionLocked(local.Root, local.Project, managedSnapshotHosts(managed))
			return a.current
		}
		// Existing external-project behavior remains Core-backed and is outside
		// F1's Installer-owned local observation contract.
		return a.openExternalProjectLocked(local)
	}
	return a.failure("PROJECT_CHANGED")
}

func (a *App) openExternalProjectLocked(local projectlifecycle.Result) ProjectOpenResult {
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	snapshot, err := a.reader.BuildSnapshot(ctx, local.Root)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	a.clearCredentialForReplacementLocked(local.Root, local.Project)
	a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project, Counts: local.Counts, Snapshot: snapshot, Verification: notVerified(), Diagnostics: a.serverTypeDiagnostics(snapshot)}
	a.bindExecutionLocked(local.Root, local.Project, snapshot.Hosts)
	return a.current
}

func (a *App) CloseProject() ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.clearProjectExportLocked()
	a.secrets.Clear()
	a.execution.clear()
	a.continuation = nil
	a.installationGeneration++
	a.installationPlanID = ""
	a.installationRuns.clear()
	a.current = ProjectOpenResult{Status: "NO_PROJECT"}
	return a.current
}

// VerifyProject validates exactly the current saved revision through the
// existing target-free Core snapshot operation. It never writes project files.
// When E5 has a trusted binding it first performs the permitted read-only
// readiness check; preparation remains a separately confirmed operation.
func (a *App) VerifyProject() ProjectVerification {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Root == "" || a.current.Project == nil {
		return ProjectVerification{APIVersion: "platform.installer/project-verification/v1alpha1", Kind: "ProjectVerification", Status: "UNVERIFIED",
			Error: &ProjectOpenError{Code: "PROJECT_NOT_OPEN", Message: projectErrorMessage("PROJECT_NOT_OPEN")}}
	}
	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return a.setVerificationUnavailableLocked(err, "")
	}
	if a.binding != nil {
		binding, err := a.resolveSelectedExecutionNodeBindingLocked()
		if err != nil {
			return a.setVerificationUnavailableLocked(err, revision)
		}
		return a.verifyProjectWithBindingLocked(binding, revision, true)
	}
	return a.verifyProjectWithReaderLocked(a.reader, revision)
}

func (a *App) verifyProjectWithBindingLocked(binding *executionNodeBinding, revision string, inspect bool) ProjectVerification {
	if inspect {
		ctx, cancel := a.operationContext(90 * time.Second)
		defer cancel()
		inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
		if err != nil {
			return a.setVerificationUnavailableLocked(err, revision)
		}
		a.execution.setStatus(string(inspection.State))
		if inspection.State != executionnode.Ready {
			return a.setVerificationUnavailableLocked(errors.New("EXECUTION_NODE_READY_REQUIRED"), revision)
		}
	}
	return a.verifyProjectWithReaderLocked(binding.reader, revision)
}

func (a *App) verifyProjectWithReaderLocked(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, revision string) ProjectVerification {
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	verificationReader, ok := reader.(interface {
		BuildVerificationSnapshot(context.Context, string) (verificationSnapshot, error)
	})
	if !ok {
		return a.setVerificationUnavailableLocked(errors.New("EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED"), revision)
	}
	verifiedSnapshot, err := verificationReader.BuildVerificationSnapshot(ctx, a.current.Root)
	if err != nil {
		return a.setVerificationUnavailableLocked(err, revision)
	}
	after, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return a.setVerificationUnavailableLocked(err, revision)
	}
	evidence := ProjectVerification{APIVersion: "platform.installer/project-verification/v1alpha1", Kind: "ProjectVerification",
		ProjectIdentity: a.current.Project.ID, ProjectRevision: revision, ExecutionNodeID: verifiedSnapshot.NodeID,
		Runtime: &verifiedSnapshot.Runtime, CheckedAt: time.Now().UTC()}
	evidence.Findings, evidence.FindingsTruncated = safeVerificationFindings(verifiedSnapshot.Snapshot.Findings)
	if after != revision || verifiedSnapshot.Snapshot.ProjectRevision != revision {
		return a.setVerificationUnavailableLocked(errors.New("PROJECT_REVISION_CHANGED"), revision)
	} else if verifiedSnapshot.Snapshot.Status == "PASS" && !verifiedSnapshot.Snapshot.Partial {
		evidence.Status = "VERIFIED"
		a.current.Snapshot = verifiedSnapshot.Snapshot
	} else {
		evidence.Status = "INVALID"
		a.current.Snapshot = verifiedSnapshot.Snapshot
	}
	a.current.Verification = evidence
	return evidence
}

func (a *App) setVerificationUnavailableLocked(err error, revision string) ProjectVerification {
	code := projectErrorCode(err)
	if code == "EXECUTION_NODE_NOT_CONFIGURED" || code == "EXECUTION_NODE_UNAVAILABLE" {
		code = "EXECUTION_NODE_READY_REQUIRED"
	}
	evidence := ProjectVerification{APIVersion: "platform.installer/project-verification/v1alpha1", Kind: "ProjectVerification", Status: "UNVERIFIED",
		ProjectRevision: revision, CheckedAt: time.Now().UTC(), Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
	a.current.Verification = evidence
	return evidence
}

func safeVerificationFindings(findings []map[string]any) ([]VerificationFinding, bool) {
	const maxFindings = 64
	truncated := len(findings) > maxFindings
	if truncated {
		findings = findings[:maxFindings]
	}
	result := make([]VerificationFinding, 0, len(findings))
	for _, raw := range findings {
		code, message := boundedFindingString(raw["code"], 128), boundedFindingString(raw["safeMessage"], 512)
		if code == "" || message == "" {
			continue
		}
		finding := VerificationFinding{Code: code, Summary: message, Severity: boundedFindingString(raw["status"], 32)}
		if finding.Severity == "" {
			finding.Severity = "UNKNOWN"
		}
		if subject, ok := raw["subject"].(map[string]any); ok {
			finding.SubjectKind = boundedFindingString(subject["kind"], 64)
			finding.SubjectID = boundedFindingString(subject["id"], 128)
		}
		if remediation, ok := raw["remediation"].(map[string]any); ok {
			finding.HelpRef = boundedFindingString(remediation["helpUri"], 256)
		}
		result = append(result, finding)
	}
	return result, truncated
}

func boundedFindingString(raw any, limit int) string {
	value, ok := raw.(string)
	if !ok || len(value) == 0 || len(value) > limit {
		return ""
	}
	return value
}

// SetSessionCredential captures one target credential for the current project
// in memory only. It does not contact an Execution Node or target host.
func (a *App) SetSessionCredential(input runtimesecret.Input) (runtimesecret.Status, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return runtimesecret.Status{}, err
	}
	return a.secrets.Set(binding, input)
}

func (a *App) GetSessionCredentialStatus() (runtimesecret.Status, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return runtimesecret.Status{}, err
	}
	return a.secrets.Status(binding), nil
}

// SetPKIStorePassword stores the one approved runtime-only PKI password on
// the current in-memory session credential. The return value is status-only.
func (a *App) SetPKIStorePassword(value string) (runtimesecret.Status, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return runtimesecret.Status{}, err
	}
	return a.secrets.SetPKIStorePassword(binding, value)
}

// SetDeploymentRuntimeSecretValues accepts values only for the current,
// Core-derived descriptor set. It never persists or returns secret values.
func (a *App) SetDeploymentRuntimeSecretValues(input RuntimeSecretValuesInput) error {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return err
	}
	evidence := a.runtimeSecretEvidence
	if evidence == nil || a.binding == nil || a.current.Project == nil || input.ProjectRevision == "" || input.ProjectRevision != evidence.projectRevision || input.DescriptorSetFingerprint == "" || input.DescriptorSetFingerprint != evidence.fingerprint || evidence.projectID != a.current.Project.ID || evidence.nodeID != a.execution.context.SelectedHostID || !runtimeEvidenceMatchesExpected(evidence.runtime, a.binding.reader.runtimeRelease) {
		return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
	}
	requirements := make([]string, 0)
	for _, descriptor := range evidence.descriptors {
		if descriptor.Purpose == "SERVICE_PASSWORD" && descriptor.ServiceDeployment == input.ServiceDeployment {
			requirements = append(requirements, descriptor.RequirementRef)
		}
	}
	if len(requirements) == 0 {
		return errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
	}
	return a.secrets.SetRuntimeSecretValuesForRequirements(binding, requirements, input.Values)
}

// GetRuntimeSecretDescriptors is a target-free Core query. It exposes only
// bounded prompt metadata and never exposes the runtime reference or value.
func (a *App) GetRuntimeSecretDescriptors() RuntimeSecretDescriptorOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Root == "" || a.execution.context.Status != "READY" {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "EXECUTION_NODE_READY_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_READY_REQUIRED")}}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	transport, ok := binding.reader.transport.(interface {
		BuildRuntimeSecretDescriptors(context.Context, executionnode.Node, string, map[string]any, executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error)
	})
	if !ok {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNSUPPORTED", Message: "Execution Node does not support service secret descriptors."}}
	}
	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "PROJECT_REVISION_UNAVAILABLE", Message: projectErrorMessage("PROJECT_REVISION_UNAVAILABLE")}}
	}
	requestID, err := executionnode.NewRequestID()
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Could not create a bounded secret descriptor request."}}
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	result, err := transport.BuildRuntimeSecretDescriptors(ctx, binding.node, a.current.Root, binding.reader.runtimeRelease, executionnode.RuntimeSecretDescriptorRequest{RequestID: requestID, ProjectIdentity: a.current.Project.ID, ProjectRevision: revision, ArtifactLockDigest: a.current.Project.Source.BundleDigest, CatalogLockDigest: a.current.Project.Source.CatalogDigest})
	if err != nil || result.ProjectRevision != revision || !runtimeEvidenceMatchesExpected(result.Runtime, binding.reader.runtimeRelease) {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core could not safely build service secret descriptors."}}
	}
	view := RuntimeSecretDescriptorOperation{Status: "READY", ProjectRevision: result.ProjectRevision, DescriptorSetFingerprint: result.DescriptorSetFingerprint}
	for _, item := range result.Descriptors {
		if !validRuntimeSecretDescriptor(item) {
			return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned an unsafe service secret descriptor."}}
		}
		view.Descriptors = append(view.Descriptors, RuntimeSecretDescriptorView{RequirementRef: item.RequirementRef, Purpose: item.Purpose, ServiceDeployment: item.ServiceDeployment, DisplayLabel: item.DisplayLabel, Hosts: append([]string(nil), item.Hosts...)})
	}
	if len(view.Descriptors) > 16 {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned too many service secret descriptors."}}
	}
	a.clearRuntimeSecretDescriptorEvidenceLocked()
	a.runtimeSecretEvidence = &runtimeSecretDescriptorEvidence{projectID: a.current.Project.ID, projectRevision: revision, nodeID: binding.node.ID, runtime: result.Runtime, fingerprint: result.DescriptorSetFingerprint, descriptors: append([]RuntimeSecretDescriptorView(nil), view.Descriptors...)}
	return view
}

func validRuntimeSecretDescriptor(item executionnode.RuntimeSecretDescriptor) bool {
	if !runtimeSecretDescriptorRequirement.MatchString(item.RequirementRef) || item.DisplayLabel == "" || len([]byte(item.DisplayLabel)) > 160 || len(item.Hosts) == 0 || len(item.Hosts) > 256 {
		return false
	}
	seenHosts := make(map[string]struct{}, len(item.Hosts))
	for _, host := range item.Hosts {
		if host == "" {
			return false
		}
		if _, duplicate := seenHosts[host]; duplicate {
			return false
		}
		seenHosts[host] = struct{}{}
	}
	if item.Purpose == "PKI_STORE_PASSWORD" {
		return item.RequirementRef == "pki-store-password" && item.ServiceDeployment == ""
	}
	return item.Purpose == "SERVICE_PASSWORD" && item.ServiceDeployment != ""
}

func (a *App) ClearSessionCredential() (runtimesecret.Status, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if _, err := a.credentialBindingLocked(); err != nil {
		return runtimesecret.Status{}, err
	}
	a.secrets.Clear()
	a.runtimeSecretEvidence = nil
	return runtimesecret.Status{Status: runtimesecret.StatusMissing, SudoPasswordStatus: runtimesecret.SudoNotProvided, PKIStorePasswordStatus: runtimesecret.PKIStorePasswordMissing}, nil
}

// GetExecutionNodeContext exposes only app-memory, non-secret selection state.
func (a *App) GetExecutionNodeContext() (ExecutionNodeContext, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return ExecutionNodeContext{}, errors.New("PROJECT_NOT_OPEN")
	}
	return a.execution.context, nil
}

// SelectExecutionNode changes only the current safe project-server selection.
func (a *App) SelectExecutionNode(hostID string) (ExecutionNodeContext, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return ExecutionNodeContext{}, errors.New("PROJECT_NOT_OPEN")
	}
	before := a.execution.context
	if err := a.execution.selectProjectServer(hostID); err != nil {
		return ExecutionNodeContext{}, err
	}
	if !sameExecutionNodeTarget(before, a.execution.context) {
		a.clearRuntimeSecretDescriptorEvidenceLocked()
		a.current.Snapshot = nil
		a.current.Verification = notVerified()
		a.installationPlanID = ""
		a.installationGeneration++
		a.installationRuns.clear()
	}
	a.continuation = nil
	return a.execution.context, nil
}

func sameExecutionNodeTarget(left, right ExecutionNodeContext) bool {
	return left.SelectionKind == right.SelectionKind && left.SelectedHostID == right.SelectedHostID
}

func (a *App) credentialBindingLocked() (runtimesecret.Binding, error) {
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Root == "" || a.current.Project.ID == "" {
		return runtimesecret.Binding{}, errors.New("PROJECT_NOT_OPEN")
	}
	return runtimesecret.Binding{Root: a.current.Root, ID: a.current.Project.ID}, nil
}

func (a *App) clearCredentialForReplacementLocked(root string, project *projectlifecycle.Project) {
	a.clearRuntimeSecretDescriptorEvidenceLocked()
	if a.current.Status != "OPEN" || a.current.Project == nil || project == nil || a.current.Root != root || a.current.Project.ID != project.ID {
		a.secrets.Clear()
	}
}

func (a *App) clearRuntimeSecretDescriptorEvidenceLocked() {
	a.runtimeSecretEvidence = nil
	if binding, err := a.credentialBindingLocked(); err == nil {
		a.secrets.ClearRuntimeSecretValues(binding)
	}
}

type EditOperationResult struct {
	Status      string                      `json:"status"`
	Session     *installer.EditSession      `json:"session,omitempty"`
	Plan        *installer.EditPlan         `json:"plan,omitempty"`
	Commit      *installer.EditCommitResult `json:"commit,omitempty"`
	Diagnostics []ApplicationDiagnostic     `json:"diagnostics,omitempty"`
	Error       *ProjectOpenError           `json:"error,omitempty"`
}

// StructuralEditOperationResult is the additive local Save contract. Legacy
// EditOperationResult remains published for previous Wails consumers.
type StructuralEditOperationResult struct {
	Status      string                          `json:"status"`
	Session     *installer.EditSession          `json:"session,omitempty"`
	Plan        *installer.StructuralEditPlan   `json:"plan,omitempty"`
	Commit      *installer.StructuralSaveResult `json:"commit,omitempty"`
	Current     *ProjectOpenResult              `json:"current,omitempty"`
	Diagnostics []ApplicationDiagnostic         `json:"diagnostics,omitempty"`
	Error       *ProjectOpenError               `json:"error,omitempty"`
}

type ProjectExportOperationResult struct {
	Status string                         `json:"status"`
	Plan   *installer.ProjectExportPlan   `json:"plan,omitempty"`
	Result *installer.ProjectExportResult `json:"result,omitempty"`
	Error  *ProjectOpenError              `json:"error,omitempty"`
}

func (a *App) projectExportFailure(err error) ProjectExportOperationResult {
	code := projectErrorCode(err)
	return ProjectExportOperationResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

// PlanProjectExport creates one bounded in-memory export capability. It does
// not write the project, call Core, contact an Execution Node, or expose file
// contents to Wails.
func (a *App) PlanProjectExport(destinationParent, directoryName string) ProjectExportOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.projectExportFailure(errors.New("EDIT_SESSION_ACTIVE"))
	}
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return a.projectExportFailure(errors.New("PROJECT_NOT_OPEN"))
	}
	if a.current.Classification != projectlifecycle.ClassificationEmpty && a.current.Classification != projectlifecycle.ClassificationManaged {
		return a.projectExportFailure(errors.New("EXPORT_NOT_AVAILABLE"))
	}
	if a.current.Classification == projectlifecycle.ClassificationManaged && a.current.Managed == nil {
		return a.projectExportFailure(errors.New("LOCAL_PROJECT_REFRESH_REQUIRED"))
	}
	a.clearProjectExportLocked()
	capability, plan, err := installer.PlanProjectExport(a.current.Root, destinationParent, directoryName)
	if err != nil {
		return a.projectExportFailure(err)
	}
	a.export = capability
	return ProjectExportOperationResult{Status: "READY", Plan: &plan}
}

// CommitProjectExport publishes only the manifest bound to the active preview.
// It is synchronous by owner decision: no user-facing interruption path exists.
func (a *App) CommitProjectExport(planDigest string) ProjectExportOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.export == nil {
		return a.projectExportFailure(errors.New("EXPORT_PLAN_STALE"))
	}
	capability := a.export
	a.export = nil
	result := capability.Commit(planDigest)
	if result.Status != "EXPORTED" {
		return a.projectExportFailure(errors.New(result.ErrorCode))
	}
	return ProjectExportOperationResult{Status: "EXPORTED", Result: &result}
}

func (a *App) clearProjectExportLocked() {
	if a.export != nil {
		a.export.Close()
		a.export = nil
	}
}

func (a *App) editFailure(err error) EditOperationResult {
	code := projectErrorCode(err)
	return EditOperationResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func (a *App) structuralEditFailure(err error) StructuralEditOperationResult {
	code := projectErrorCode(err)
	return StructuralEditOperationResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func (a *App) StartEditSession() EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return a.editFailure(errors.New("PROJECT_NOT_OPEN"))
	}
	if a.current.Classification == projectlifecycle.ClassificationManaged && a.current.Managed == nil {
		return a.editFailure(errors.New("LOCAL_PROJECT_REFRESH_REQUIRED"))
	}
	a.clearProjectExportLocked()
	revision := ""
	if a.current.Snapshot != nil {
		revision = a.current.Snapshot.ProjectRevision
	} else {
		var err error
		revision, err = installer.ProjectRevision(a.current.Root)
		if err != nil {
			return a.editFailure(err)
		}
	}
	typeIDs := make([]string, 0, len(a.config.ServerTypes))
	if a.configErr == nil {
		for _, serverType := range a.config.ServerTypes {
			typeIDs = append(typeIDs, serverType.ID)
		}
	}
	a.editor = installer.NewBackend(nil, installer.WithServerTypes(typeIDs), installer.WithProjectCatalogResolver(a.lifecycle.ResolveProjectCatalog))
	session, err := a.sessions.Start(a.current.Project.ID, a.current.Root, a.current.Classification, revision)
	if err != nil {
		return a.editFailure(err)
	}
	a.activeSession = session.SessionID
	return EditOperationResult{Status: "EDITING", Session: &session}
}

func (a *App) AppendEditCommand(sessionID string, command installer.EditCommand) EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if sessionID == "" || sessionID != a.activeSession {
		return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	switch command.Operation {
	case "CreateServer", "UpdateServer", "DeleteServer",
		"CreateServiceDeployment", "DeleteServiceDeployment",
		"ReconcileDeploymentPlacement", "ReconcileHostScopedDeploymentPlacement",
		"CreateEndpointGroup", "UpdateEndpointGroup", "DeleteEndpointGroup",
		"SetServiceEndpointGroup", "ClearServiceEndpointGroup",
		"ReconcileEndpointProvider", "ClearEndpointProvider",
		"CreateCertificateAuthority", "UpdateCertificateAuthority", "DeleteCertificateAuthority",
		"CreateCertificateProfile", "UpdateCertificateProfile", "DeleteCertificateProfile",
		"CreateTLSProfile", "UpdateTLSProfile", "DeleteTLSProfile",
		"CreateCertificateScope", "UpdateCertificateScope", "DeleteCertificateScope":
	case "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride":
	default:
		return a.editFailure(errors.New("EDIT_OPERATION_NOT_AVAILABLE"))
	}
	session, err := a.sessions.Append(sessionID, command, a.editor)
	if err != nil {
		return a.editFailure(err)
	}
	a.execution.applyCommand(command.HostID, command.Operation, command.Address)
	result := EditOperationResult{Status: "EDITING", Session: &session}
	if command.ServerType != "" && a.configErr == nil && !a.config.HasServerType(command.ServerType) {
		result.Diagnostics = []ApplicationDiagnostic{{Code: "UNKNOWN_CONFIGURED_SERVER_TYPE", Severity: "WARNING", HostID: command.HostID, SafeMessage: "Server type is not present in the current application configuration"}}
	}
	return result
}

// ReviewEditSession is retained only as a shape-compatible legacy endpoint.
func (a *App) ReviewEditSession(string) EditOperationResult {
	return a.editFailure(errors.New("EDIT_CONTRACT_SUPERSEDED"))
}

func (a *App) ReviewStructuralEditSession(sessionID string) StructuralEditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.editor == nil || sessionID == "" || sessionID != a.activeSession {
		return a.structuralEditFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	plan, err := a.sessions.ReviewStructural(ctx, a.editor, sessionID)
	if err != nil {
		return a.structuralEditFailure(err)
	}
	return StructuralEditOperationResult{Status: plan.Status, Plan: plan}
}

// CommitEditPlan is retained only as a shape-compatible legacy endpoint.
func (a *App) CommitEditPlan(string, string) EditOperationResult {
	return a.editFailure(errors.New("EDIT_CONTRACT_SUPERSEDED"))
}

func (a *App) CommitStructuralEditPlan(sessionID, planID string) StructuralEditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.editor == nil || sessionID == "" || sessionID != a.activeSession {
		return a.structuralEditFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	if _, err := a.sessions.BeginCommit(sessionID, planID); err != nil {
		return a.structuralEditFailure(err)
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	result := a.editor.CommitStructuralSave(ctx, planID)
	if result.Status == "COMMITTED" && result.Managed != nil && a.current.Catalog != nil && a.current.Catalog.Status == "READY" {
		if enriched, readErr := installer.ReadManagedProjectViewWithCatalog(a.current.Root, a.current.Catalog); readErr == nil && enriched.ProjectRevision == result.NewProjectRevision {
			result.Managed = enriched
		}
	}
	if result.Status == "COMMITTED" || result.Status == "COMMITTED_REFRESH_FAILED" {
		a.clearRuntimeSecretDescriptorEvidenceLocked()
		if !a.sessions.FinishCommit(sessionID, planID, true) {
			return a.structuralEditFailure(errors.New("EDIT_SESSION_EXPIRED"))
		}
		a.activeSession = ""
		a.editor = nil
		a.current.Snapshot = nil
		a.current.Classification = projectlifecycle.ClassificationManaged
		if result.Status == "COMMITTED" && result.Managed != nil && result.Managed.ProjectRevision == result.NewProjectRevision {
			a.current.Managed = result.Managed
			managed := result.Managed
			a.current.Counts.Servers = len(managed.Servers)
			a.current.Diagnostics = a.managedServerTypeDiagnostics(managed)
			a.bindExecutionLocked(a.current.Root, a.current.Project, managedSnapshotHosts(managed))
		} else {
			a.current.Managed = nil
			a.current.Snapshot = nil
			a.current.Counts.Servers = 0
			a.current.Diagnostics = nil
			a.execution.bind(a.current.Root, a.current.Project.ID, nil)
		}
		a.continuation = nil
		a.current.Verification = notVerified()
	}
	if result.Status != "COMMITTED" && result.Status != "COMMITTED_REFRESH_FAILED" {
		a.sessions.FinishCommit(sessionID, planID, false)
	}
	response := StructuralEditOperationResult{Status: result.Status, Commit: &result}
	if result.Status == "COMMITTED" || result.Status == "COMMITTED_REFRESH_FAILED" {
		current := a.current
		response.Current = &current
	}
	return response
}

func (a *App) DiscardEditSession(sessionID string) EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	wasActive := sessionID != "" && sessionID == a.activeSession
	a.reconcileEditSessionLocked()
	if wasActive && a.activeSession == "" {
		return EditOperationResult{Status: "DISCARDED"}
	}
	if a.editor == nil || !a.sessions.Discard(sessionID, a.editor) {
		return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	a.activeSession, a.editor = "", nil
	a.execution.discardDraft(currentProjectHosts(a.current))
	return EditOperationResult{Status: "DISCARDED"}
}

func (a *App) reconcileEditSessionLocked() {
	if a.activeSession != "" && !a.sessions.Active(a.activeSession) {
		a.activeSession, a.editor = "", nil
		a.execution.discardDraft(currentProjectHosts(a.current))
	}
}

func snapshotHosts(snapshot *coreadapter.Snapshot) map[string]map[string]any {
	if snapshot == nil {
		return nil
	}
	return snapshot.Hosts
}

func currentProjectHosts(current ProjectOpenResult) map[string]map[string]any {
	if current.Managed != nil {
		return managedSnapshotHosts(current.Managed)
	}
	return snapshotHosts(current.Snapshot)
}

func managedSnapshotHosts(view *installer.ManagedProjectView) map[string]map[string]any {
	if view == nil {
		return nil
	}
	hosts := make(map[string]map[string]any, len(view.Servers))
	for id, server := range view.Servers {
		hosts[id] = map[string]any{"ansibleHost": server.Address, "type": server.Type, "desiredHostname": server.DesiredHostname}
		if server.SSHPort != nil {
			hosts[id]["ansiblePort"] = *server.SSHPort
		}
	}
	return hosts
}

func (a *App) bindExecutionLocked(root string, project *projectlifecycle.Project, hosts map[string]map[string]any) {
	a.clearRuntimeSecretDescriptorEvidenceLocked()
	a.installationGeneration++
	a.continuation = nil
	a.installationPlanID = ""
	a.installationRuns.clear()
	if project == nil || project.ID == "" {
		a.execution.clear()
		return
	}
	a.execution.bind(root, project.ID, hosts)
}

func (a *App) operationContext(timeout time.Duration) (context.Context, context.CancelFunc) {
	base := a.ctx
	if base == nil {
		base = context.Background()
	}
	return context.WithTimeout(base, timeout)
}

func (a *App) CurrentProject() ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	return a.current
}

func (a *App) failure(code string) ProjectOpenResult {
	return ProjectOpenResult{Status: "ERROR", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func projectErrorCode(err error) string {
	var executionError *executionnode.ExecutionError
	if errors.As(err, &executionError) && executionError.Code != "" {
		return executionError.Code
	}
	if err == nil || err.Error() == "" {
		return "PROJECT_OPEN_FAILED"
	}
	return err.Error()
}

func projectErrorMessage(code string) string {
	switch code {
	case "EXECUTION_NODE_NOT_CONFIGURED":
		return "Не настроен READY Execution Node для read-only открытия проекта."
	case "EXECUTION_NODE_UNAVAILABLE":
		return "Execution Node недоступен. Проект на диске не изменён."
	case "EXECUTION_NODE_READY_REQUIRED":
		return "Требуется READY Execution Node. Проверьте или подготовьте его на странице Серверы."
	case "EXECUTION_NODE_BINDING_REQUIRED":
		return "Выбранный Execution Node не имеет доверенного runtime binding. Откройте страницу Серверы."
	case "PROJECT_CHANGES_UNSAVED":
		return "Сначала сохраните или отмените несохранённые изменения проекта."
	case "PROJECT_REVISION_UNAVAILABLE":
		return "Не удалось безопасно прочитать сохранённую ревизию проекта."
	case "INSTALLATION_PLAN_NOT_FOUND":
		return "Этот план не принадлежит текущему открытому проекту или уже истёк. Создайте свежий план."
	case "PLAN_BLOCKED":
		return "План заблокирован findings Core и не может быть одобрен."
	case "PLAN_STALE":
		return "Сохранённый проект или runtime binding изменились. Создайте свежий план."
	case "DEPLOYMENT_PLAN_RESPONSE_INVALID":
		return "Execution Node вернул некорректный план. Выполнение не начиналось."
	case "BINDING_REQUIRED":
		return "Выбранный кандидат не имеет доверенного Execution Node binding. Настройте узел через поддерживаемый trusted path."
	case "EXECUTION_NODE_PLAN_INVALID":
		return "План подготовки отсутствует, изменился или истёк. Проверьте узел и спланируйте подготовку заново."
	case "PROJECT_REVISION_CHANGED":
		return "Сохранённая ревизия проекта изменилась. Подготовка отменена; проверьте проект заново."
	case "PROJECT_SNAPSHOT_INPUT_INVALID", "PROJECT_SNAPSHOT_FAILED", "PROJECT_SNAPSHOT_RESPONSE_INVALID":
		return "Core не смог построить снимок проекта. Проект на диске не изменён."
	case "PROJECT_PATH_INVALID":
		return "Не удалось прочитать выбранный путь проекта."
	case "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE":
		return "Нет проверенного локального compatibility source для создания проекта."
	case "PROJECT_DESTINATION_EXISTS":
		return "Папка нового проекта уже существует и не будет изменена."
	case "PROJECT_PARENT_MISSING", "PROJECT_PARENT_NOT_WRITABLE", "PROJECT_PATH_UNSAFE":
		return "Нельзя безопасно создать проект в выбранной папке."
	case "PROJECT_DISPLAY_NAME_INVALID":
		return "Введите корректное название проекта."
	case "EXPORT_NOT_AVAILABLE":
		return "Экспорт доступен только для сохранённого Installer-managed проекта."
	case "EXPORT_DESTINATION_INVALID":
		return "Введите корректное имя новой папки экспорта и выберите отдельную папку назначения."
	case "EXPORT_DESTINATION_EXISTS":
		return "Папка экспорта уже существует и не будет изменена."
	case "EXPORT_DESTINATION_UNSAFE":
		return "Нельзя безопасно опубликовать экспорт в выбранной папке."
	case "EXPORT_SOURCE_UNSAFE":
		return "Сохранённый проект нельзя безопасно прочитать для экспорта."
	case "EXPORT_LIMIT_EXCEEDED":
		return "Экспорт превышает допустимые ограничения portable-проекта."
	case "EXPORT_PLAN_STALE":
		return "Проект или предварительный просмотр экспорта изменились. Создайте предварительный просмотр заново."
	case "EXPORT_WRITE_FAILED", "EXPORT_PUBLISH_FAILED":
		return "Экспорт не был опубликован. Исходный проект не изменён."
	case "EXPORT_STAGING_RETAINED":
		return "Экспорт не завершён. Временная папка сохранена, потому что безопасное автоматическое удаление не удалось доказать."
	case "APPLICATION_CONFIG_NOT_FOUND", "APPLICATION_CONFIG_UNREADABLE", "APPLICATION_CONFIG_UNSAFE_PATH", "APPLICATION_CONFIG_INVALID", "APPLICATION_CONFIG_TOO_LARGE", "APPLICATION_CONFIG_VERSION_UNSUPPORTED", "APPLICATION_CONFIG_SERVER_TYPES_INVALID", "APPLICATION_CONFIG_SERVER_TYPE_ID_INVALID", "APPLICATION_CONFIG_SERVER_TYPE_NAME_INVALID", "APPLICATION_CONFIG_SERVER_TYPE_DUPLICATE", "APPLICATION_CONFIG_UNAVAILABLE":
		return "Конфигурация приложения недоступна или некорректна. Создание нового сервера заблокировано."
	case "PROJECT_NOT_OPEN":
		return "Сначала откройте проект."
	case "EDIT_SESSION_ACTIVE":
		return "Сначала сохраните или отмените несохранённые изменения."
	case "EDIT_SESSION_EXPIRED":
		return "Черновик отсутствует или истёк. Начните редактирование заново."
	case "EDIT_SESSION_BUSY":
		return "Проверка черновика уже выполняется."
	case "EDIT_OPERATION_NOT_AVAILABLE":
		return "Эта операция ещё не доступна в текущем UI milestone."
	case "INVALID_EDIT_COMMAND", "INVALID_VALUE":
		return "Изменение сервера содержит некорректное значение. Исправьте поля и повторите проверку."
	case "SERVER_METADATA_REQUIRED":
		return "Для редактирования сервера заполните обязательные метаданные."
	case "REFERENCE_IN_USE":
		return "Удаление заблокировано: сервер остаётся в канонических ссылках проекта."
	case "EDIT_SHADOWED", "SERVER_RECREATE_IN_SESSION_UNSUPPORTED":
		return "Черновик содержит конфликтующие изменения сервера. Отмените его и начните заново."
	case "EDIT_SESSION_EMPTY", "EDIT_SESSION_COMMANDS_UNSUPPORTED":
		return "В черновике нет поддерживаемых изменений для проверки."
	case "PLAN_EXPIRED":
		return "План изменений истёк. Проверьте черновик заново перед сохранением."
	case "PROJECT_LOCKED":
		return "Проект занят другой операцией. Повторите сохранение позже."
	case "STAGING_FAILED", "CORE_SNAPSHOT_FAILED", "VALIDATION_BLOCKED":
		return "Core не смог безопасно проверить полный candidate проекта. Проект на диске не изменён."
	case "WRITE_FAILED", "RECOVERY_FAILED", "ROLLBACK_FAILED", "PATH_UNSAFE":
		return "Сохранение проекта не выполнено безопасно. Проверьте состояние проекта перед повтором."
	case "PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED":
		return "Активный Execution Node не поддерживает проверку edit candidate."
	case "WRITE_OWNERSHIP_REQUIRED", "WRITE_NOT_ALLOWED", "DOCUMENT_CHANGED", "PROJECT_CHANGED":
		return "Сохранение заблокировано: проект или владение документами изменилось."
	case "PROJECT_INPUT_INCOMPLETE", "MANAGED_PROJECT_INVALID", "MANAGED_DOCUMENT_INVALID", "PROJECT_OPEN_BLOCKED":
		return "Выбранный проект нельзя безопасно открыть в текущем режиме."
	default:
		return "Не удалось открыть проект в режиме только чтения. Проект на диске не изменён."
	}
}

package main

import (
	"bytes"
	"context"
	"errors"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
	"platform-installer/internal/secretfiles"
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

func verificationAfterSave(previous ProjectVerification) ProjectVerification {
	if previous.Status != "VERIFIED" && previous.Status != "INVALID" && previous.Status != "STALE" {
		return notVerified()
	}
	return ProjectVerification{
		APIVersion:      "platform.installer/project-verification/v1alpha1",
		Kind:            "ProjectVerification",
		Status:          "STALE",
		ProjectIdentity: previous.ProjectIdentity,
		ProjectRevision: previous.ProjectRevision,
		ExecutionNodeID: previous.ExecutionNodeID,
		Runtime:         previous.Runtime,
		CheckedAt:       previous.CheckedAt,
	}
}

type ProjectOpenError struct {
	Code            string   `json:"code"`
	Message         string   `json:"message"`
	DiagnosticCodes []string `json:"diagnosticCodes,omitempty"`
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
	RequirementRef      string   `json:"requirementRef"`
	Purpose             string   `json:"purpose"`
	ServiceDeployment   string   `json:"serviceDeployment,omitempty"`
	Setting             string   `json:"setting,omitempty"`
	DisplayLabel        string   `json:"displayLabel"`
	RequiredWhen        string   `json:"requiredWhen,omitempty"`
	Operations          []string `json:"operations,omitempty"`
	ReferenceConfigured bool     `json:"referenceConfigured"`
	Hosts               []string `json:"hosts"`
}

type RuntimeSecretDescriptorOperation struct {
	SecretsInstalled         bool                          `json:"secretsInstalled,omitempty"`
	Status                   string                        `json:"status"`
	ProjectRevision          string                        `json:"projectRevision,omitempty"`
	DescriptorSetFingerprint string                        `json:"descriptorSetFingerprint,omitempty"`
	Descriptors              []RuntimeSecretDescriptorView `json:"descriptors,omitempty"`
	Error                    *ProjectOpenError             `json:"error,omitempty"`
}

// RuntimeSecretValuesInput is one non-persistent submission for a single
// Core-derived service deployment. Values are accepted but never returned.
type RuntimeSecretValuesInput struct {
	ProjectRevision          string            `json:"projectRevision"`
	DescriptorSetFingerprint string            `json:"descriptorSetFingerprint"`
	ServiceDeployment        string            `json:"serviceDeployment"`
	Values                   map[string]string `json:"values"`
}

// PendingRuntimeSecretValuesInput is a locally catalog-authorized, transient
// service-password submission. It intentionally has no project revision or
// Execution Node evidence: Core confirms exact requirements later at the
// installation gate before any target can be contacted.
type PendingRuntimeSecretValuesInput struct {
	ServiceDeployment string            `json:"serviceDeployment"`
	Values            map[string]string `json:"values"`
}

type PendingRuntimeSecretFileInput struct {
	ServiceDeployment  string `json:"serviceDeployment"`
	Purpose            string `json:"purpose"`
	EncryptionPassword string `json:"encryptionPassword"`
}

type OutputEncryptionPasswordInput struct {
	Password string `json:"password"`
	Confirm  string `json:"confirm"`
}

type SecretOutputPackagesOperation struct {
	Status     string                              `json:"status"`
	Packages   []executionnode.SecretOutputPackage `json:"packages,omitempty"`
	NextCursor *string                             `json:"nextCursor,omitempty"`
	Error      *ProjectOpenError                   `json:"error,omitempty"`
}

type runtimeSecretDescriptorEvidence struct {
	projectID, projectRevision, nodeID, fingerprint string
	runtime                                         executionnode.RuntimeEvidence
	descriptors                                     []RuntimeSecretDescriptorView
}

var runtimeSecretDescriptorRequirement = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)
var runtimeSecretUsername = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]{0,62}$`)
var verificationSettingName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,127}$`)

type App struct {
	ctx              context.Context
	dialogs          DialogProvider
	events           ApplicationEventPublisher
	chooseSecretFile secretFileChooser
	reader           interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	projectRevision          func(string) (string, error)
	lifecycle                projectLifecycle
	current                  ProjectOpenResult
	sessions                 *installer.EditSessionStore
	editor                   *installer.Backend
	activeSession            string
	editMu                   sync.Mutex
	config                   appconfig.Config
	configErr                error
	secrets                  *runtimesecret.Broker
	execution                *executionNodeContextStore
	binding                  *executionNodeBinding
	availableBundleRoot      string
	bundleCacheRoot          string
	bundlePublisher          func(string) (executionbundle.Verified, error) // nil uses the verified cache publisher
	localRunRecordRoot       string
	bundlePreview            *runtimeBundlePreview
	orphanRecovery           *orphanRunRecovery
	pendingServerInformation *serverInformationProbe
	pendingHostKey           *pendingExecutionHostKey
	pendingTargetHostKey     *pendingTargetHostKey
	approvedTargetHostKeys   map[string]approvedTargetHostKey
	continuation             *verificationContinuation
	export                   *installer.ProjectExport
	installationPlanID       string
	installationRuns         *installationRunRegistry
	installationGeneration   uint64
	startInFlight            bool
	startOutcomeUnknown      bool
	runtimeUpdateInFlight    bool
	runtimeSecretEvidence    *runtimeSecretDescriptorEvidence
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

func WithAvailableExecutionBundle(root string) AppOption {
	return func(app *App) { app.availableBundleRoot = root }
}

func WithBundleCacheRoot(root string) AppOption {
	return func(app *App) { app.bundleCacheRoot = root }
}

func WithLocalRunRecordRoot(root string) AppOption {
	return func(app *App) { app.localRunRecordRoot = root }
}

type projectLifecycle interface {
	CreateProject(context.Context, projectlifecycle.CreateProjectRequest) (projectlifecycle.Result, error)
	OpenProject(context.Context, string) (projectlifecycle.Result, error)
	ResolveProjectCatalog(context.Context, string) (*projectlifecycle.ProjectCatalogView, error)
}

func NewApp(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, lifecycle projectLifecycle, options ...AppOption) *App {
	app := &App{reader: reader, lifecycle: lifecycle, projectRevision: installer.ProjectRevision, sessions: installer.NewEditSessionStore(), current: ProjectOpenResult{Status: "NO_PROJECT"}, configErr: errors.New("APPLICATION_CONFIG_NOT_FOUND"), secrets: runtimesecret.NewBroker(), execution: newExecutionNodeContextStore(nil, probeLocalExecutionNodeCandidate()), installationRuns: newInstallationRunRegistry(), approvedTargetHostKeys: map[string]approvedTargetHostKey{}, localRunRecordRoot: defaultLocalRunRecordRoot(), events: noopEventPublisher{}}
	for _, option := range options {
		option(app)
	}
	app.configureTargetCredentialLease()
	app.configureTargetHostTrust()
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
	a.pendingHostKey = nil
	a.invalidateDynamicBindingLocked()
	a.clearInstallationRunsLocked()
	a.execution.clear()
	a.continuation = nil
	a.clearProjectExportLocked()
}

func (a *App) ChooseProject() ProjectOpenResult {
	if a.ctx == nil {
		return a.failure("UI_NOT_READY")
	}
	root, err := a.openDirectory(a.ctx, DialogOptions{Title: "Открыть существующий проект"})
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
	root, err := a.openDirectory(a.ctx, DialogOptions{Title: "Выбрать папку для нового проекта"})
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
	root, err := a.openDirectory(a.ctx, DialogOptions{Title: "Выбрать папку для экспорта проекта"})
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
	a.pendingHostKey = nil
	a.invalidateDynamicBindingLocked()
	a.secrets.Clear()
	a.clearInstallationRunsLocked()
	a.current = ProjectOpenResult{Status: "OPEN", Root: result.Root, Classification: result.Classification, Project: result.Project, Counts: result.Counts, Catalog: result.Catalog, Verification: notVerified()}
	a.bindExecutionLocked(result.Root, result.Project, nil)
	return a.current
}

func (a *App) OpenProject(root string) ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.bundlePreview = nil
	a.orphanRecovery = nil
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.pendingHostKey = nil
	a.pendingTargetHostKey = nil
	clear(a.approvedTargetHostKeys)
	a.invalidateDynamicBindingLocked()
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
	a.bundlePreview = nil
	a.orphanRecovery = nil
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.clearProjectExportLocked()
	a.secrets.Clear()
	a.pendingHostKey = nil
	a.pendingTargetHostKey = nil
	clear(a.approvedTargetHostKeys)
	a.invalidateDynamicBindingLocked()
	a.execution.clear()
	a.continuation = nil
	a.installationGeneration++
	a.installationPlanID = ""
	a.clearInstallationRunsLocked()
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
	return a.verifyProjectWithReaderLocked(a.reader, revision, nil)
}

func (a *App) verifyProjectWithBindingLocked(binding *executionNodeBinding, revision string, inspect bool) ProjectVerification {
	if inspect {
		ctx, cancel := a.operationContext(90 * time.Second)
		defer cancel()
		inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
		if err != nil {
			if binding.dynamic {
				a.invalidateDynamicBindingLocked()
			}
			return a.setVerificationUnavailableLocked(err, revision)
		}
		if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
			return a.setVerificationUnavailableLocked(err, revision)
		}
		a.execution.setStatus(string(inspection.State))
		if inspection.State != executionnode.Ready {
			return a.setVerificationUnavailableLocked(errors.New("EXECUTION_NODE_READY_REQUIRED"), revision)
		}
	}
	return a.verifyProjectWithReaderLocked(binding.reader, revision, binding)
}

func (a *App) verifyProjectWithReaderLocked(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, revision string, binding *executionNodeBinding) ProjectVerification {
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
	}
	if binding != nil {
		if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
			return a.setVerificationUnavailableLocked(err, revision)
		}
	}
	if verifiedSnapshot.Snapshot.Status == "PASS" && !verifiedSnapshot.Snapshot.Partial {
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
	code := safeVerificationErrorCode(err)
	if code == "EXECUTION_NODE_NOT_CONFIGURED" || code == "EXECUTION_NODE_UNAVAILABLE" {
		code = "EXECUTION_NODE_READY_REQUIRED"
	}
	evidence := ProjectVerification{APIVersion: "platform.installer/project-verification/v1alpha1", Kind: "ProjectVerification", Status: "UNVERIFIED",
		ProjectRevision: revision, CheckedAt: time.Now().UTC(), Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
	a.current.Verification = evidence
	return evidence
}

var verificationErrorCodePattern = regexp.MustCompile(`^[A-Z][A-Z0-9_]{0,95}$`)

// Verify may receive transport/process errors containing paths or command
// output. Only bounded diagnostic identifiers may cross into the UI.
func safeVerificationErrorCode(err error) string {
	if errors.Is(err, context.DeadlineExceeded) {
		return "PROJECT_VERIFY_TIMEOUT"
	}
	if errors.Is(err, context.Canceled) {
		return "PROJECT_VERIFY_CANCELLED"
	}
	var executionError *executionnode.ExecutionError
	if errors.As(err, &executionError) && verificationErrorCodePattern.MatchString(executionError.Code) {
		return executionError.Code
	}
	switch projectErrorCode(err) {
	case "EXECUTION_NODE_NOT_CONFIGURED", "EXECUTION_NODE_UNAVAILABLE", "EXECUTION_NODE_READY_REQUIRED",
		"EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED", "EXECUTION_RUNTIME_IDENTITY_MISMATCH",
		"EXECUTION_PROTOCOL_RESPONSE_INVALID", "PROJECT_REVISION_CHANGED",
		"PROJECT_SNAPSHOT_INPUT_INVALID", "PROJECT_SNAPSHOT_RESPONSE_INVALID",
		"PROJECT_REVISION_UNAVAILABLE", "EXECUTION_BUNDLE_UNAVAILABLE":
		return projectErrorCode(err)
	default:
		return "PROJECT_VERIFY_FAILED"
	}
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
		if code == "SERVICE_CONFIGURATION_PROPERTY_UNKNOWN" {
			if details, ok := raw["safeDetails"].(map[string]any); ok {
				property := boundedFindingString(details["property"], 128)
				deployment := boundedFindingString(details["deploymentId"], 64)
				if verificationSettingName.MatchString(property) && runtimeSecretDescriptorRequirement.MatchString(deployment) {
					finding.Summary = "Неизвестный параметр конфигурации «" + property + "» у сервиса «" + deployment + "»."
				}
			}
		}
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
	if a.startInFlight || a.installationRuns.hasActiveRun() || a.secrets.HasAnyRunExecutionIdentityHold() {
		return runtimesecret.Status{}, errors.New("INSTALLATION_RUN_ACTIVE")
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return runtimesecret.Status{}, err
	}
	status, err := a.secrets.Set(binding, input)
	if err == nil {
		a.pendingHostKey = nil
		a.invalidateDynamicBindingLocked()
	}
	return status, err
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

// GetPendingRuntimeSecretDescriptors uses only the exact immutable catalog
// already locked by project.yml plus the saved managed deployment. It neither
// contacts Core nor requires an Execution Node to be READY.
func (a *App) GetPendingRuntimeSecretDescriptors(serviceDeployment string) RuntimeSecretDescriptorOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	descriptors, err := a.pendingRuntimeSecretDescriptorsLocked(serviceDeployment)
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	installed := false
	if binding, bindingErr := a.credentialBindingLocked(); bindingErr == nil {
		requirements := make([]runtimesecret.RuntimeSecretInput, 0, len(descriptors))
		for _, descriptor := range descriptors {
			requirements = append(requirements, runtimesecret.RuntimeSecretInput{RequirementRef: descriptor.RequirementRef, Purpose: descriptor.Purpose, ServiceDeployment: descriptor.ServiceDeployment})
		}
		installed = a.secrets.ServiceSecretsPresent(binding, requirements)
	}
	return RuntimeSecretDescriptorOperation{Status: "READY", Descriptors: descriptors, SecretsInstalled: installed}
}

// SetPendingDeploymentRuntimeSecretValues keeps locally catalog-authorized
// service passwords in short-lived process memory. They are never written to
// desired state. A later Core descriptor query must attest the same
// requirements before the Broker can attach them to a target credential.
func (a *App) SetPendingDeploymentRuntimeSecretValues(input PendingRuntimeSecretValuesInput) error {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return err
	}
	descriptors, err := a.pendingRuntimeSecretDescriptorsLocked(input.ServiceDeployment)
	if err != nil {
		return err
	}
	requirements := make([]string, 0, len(descriptors))
	for _, descriptor := range descriptors {
		requirements = append(requirements, descriptor.RequirementRef)
	}
	return a.secrets.SetPendingRuntimeSecretValuesForRequirements(binding, requirements, input.Values)
}

// SetSecretOutputEncryptionPassword keeps a confirmed workstation age
// password only in the project-bound in-memory Broker. It is never sent to
// Core or to the Execution Node.
func (a *App) SetSecretOutputEncryptionPassword(input OutputEncryptionPasswordInput) error {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return err
	}
	password, confirm := []byte(input.Password), []byte(input.Confirm)
	defer clear(password)
	defer clear(confirm)
	if len(password) == 0 || len(password) > secretfiles.MaxPasswordBytes || !utf8.Valid(password) || !bytes.Equal(password, confirm) {
		return errors.New("SECRET_OUTPUT_PASSWORD_INVALID")
	}
	return a.secrets.SetOutputEncryptionPassword(binding, password)
}

// ChoosePendingDeploymentRuntimeSecretFile imports one trusted typed-secret
// file without returning its path or contents to the Wails/React boundary.
func (a *App) ChoosePendingDeploymentRuntimeSecretFile(input PendingRuntimeSecretFileInput) (string, error) {
	binding, ctx, err := a.pendingRuntimeSecretFileBinding(input)
	if err != nil {
		return "", err
	}
	path, err := a.openFile(ctx, DialogOptions{Title: "Выбрать файл секрета", Filters: []DialogFilter{{DisplayName: "Файлы секрета (*.json, *.age)", Pattern: "*.json;*.age"}}})
	if err != nil {
		return "", errors.New("SECRET_FILE_SELECTION_FAILED")
	}
	if path == "" {
		return "CANCELLED", nil
	}
	fileBytes, err := secretfiles.ReadSelectedFile(path, secretfiles.MaxEncryptedBytes)
	if err != nil {
		return "", errors.New("SECRET_FILE_INVALID")
	}
	defer clear(fileBytes)
	return a.importPendingDeploymentRuntimeSecretFileBound(input, fileBytes, binding)
}

func (a *App) importPendingDeploymentRuntimeSecretFile(input PendingRuntimeSecretFileInput, fileBytes []byte) (string, error) {
	binding, _, err := a.pendingRuntimeSecretFileBinding(input)
	if err != nil {
		return "", err
	}
	return a.importPendingDeploymentRuntimeSecretFileBound(input, fileBytes, binding)
}

func (a *App) pendingRuntimeSecretFileBinding(input PendingRuntimeSecretFileInput) (runtimesecret.Binding, context.Context, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.ctx == nil {
		return runtimesecret.Binding{}, nil, errors.New("UI_NOT_READY")
	}
	descriptors, err := a.pendingRuntimeSecretDescriptorsLocked(input.ServiceDeployment)
	if err != nil {
		return runtimesecret.Binding{}, nil, err
	}
	allowed := false
	for _, descriptor := range descriptors {
		if descriptor.Purpose == input.Purpose && descriptor.ServiceDeployment == input.ServiceDeployment && (input.Purpose == secretfiles.PurposeAdminToken || input.Purpose == secretfiles.PurposeUnsealShares) {
			allowed = true
			break
		}
	}
	binding, bindErr := a.credentialBindingLocked()
	if !allowed || bindErr != nil {
		return runtimesecret.Binding{}, nil, errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
	}
	return binding, a.ctx, nil
}

func (a *App) importPendingDeploymentRuntimeSecretFileBound(input PendingRuntimeSecretFileInput, fileBytes []byte, binding runtimesecret.Binding) (string, error) {
	if len(fileBytes) == 0 || len(fileBytes) > secretfiles.MaxEncryptedBytes {
		return "", errors.New("SECRET_FILE_INVALID")
	}
	password := []byte(input.EncryptionPassword)
	defer clear(password)
	parsed, err := secretfiles.ReadVaultInput(input.Purpose, fileBytes, password)
	if err != nil {
		return "", errors.New("SECRET_FILE_INVALID")
	}
	defer clear(parsed.Token)
	defer func() {
		for _, share := range parsed.Shares {
			clear(share)
		}
	}()
	a.editMu.Lock()
	defer a.editMu.Unlock()
	currentBinding, err := a.credentialBindingLocked()
	if err != nil || currentBinding != binding {
		return "", errors.New("PROJECT_CHANGED")
	}
	currentDescriptors, err := a.pendingRuntimeSecretDescriptorsLocked(input.ServiceDeployment)
	if err != nil {
		return "", err
	}
	for _, descriptor := range currentDescriptors {
		if descriptor.Purpose == input.Purpose && descriptor.ServiceDeployment == input.ServiceDeployment {
			if err := a.secrets.SetPendingServiceSecretInput(binding, input.ServiceDeployment, input.Purpose, parsed.Token, parsed.Shares); err != nil {
				return "", err
			}
			return "STORED", nil
		}
	}
	return "", errors.New("RUNTIME_SECRET_DESCRIPTOR_STALE")
}

func (a *App) pendingRuntimeSecretDescriptorsLocked(serviceDeployment string) ([]RuntimeSecretDescriptorView, error) {
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Managed == nil || a.current.Catalog == nil || a.current.Catalog.Status != "READY" || serviceDeployment == "" {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
	}
	deployment, exists := a.current.Managed.Deployments[serviceDeployment]
	if !exists {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
	}
	var service *projectlifecycle.ProjectCatalogService
	for index := range a.current.Catalog.Services {
		if a.current.Catalog.Services[index].ID == deployment.ServiceType {
			service = &a.current.Catalog.Services[index]
			break
		}
	}
	if service == nil {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
	}
	var mode *projectlifecycle.ProjectCatalogMode
	for index := range service.Modes {
		if service.Modes[index].ID == deployment.Mode {
			mode = &service.Modes[index]
			break
		}
	}
	if mode == nil || (len(mode.RequiredRuntimeSecretSettings) == 0 && len(service.SecretInputs) == 0) {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
	}
	settings := make(map[string]projectlifecycle.ProjectCatalogSetting, len(service.ConfigurationSettings))
	for _, setting := range service.ConfigurationSettings {
		settings[setting.ID] = setting
	}
	result := make([]RuntimeSecretDescriptorView, 0, len(mode.RequiredRuntimeSecretSettings)+len(service.SecretInputs))
	seen := make(map[string]struct{}, len(mode.RequiredRuntimeSecretSettings))
	for _, settingID := range mode.RequiredRuntimeSecretSettings {
		setting, exists := settings[settingID]
		if !exists || setting.EditorShape != "RUNTIME_SECRET_REFERENCE_OBJECT" || !runtimeSecretDescriptorRequirement.MatchString(setting.RuntimeSecretRequirementRef) || setting.RuntimeSecretRequirementRef == "" || setting.Label == "" {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
		}
		if _, duplicate := seen[setting.RuntimeSecretRequirementRef]; duplicate {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
		}
		seen[setting.RuntimeSecretRequirementRef] = struct{}{}
		referenceConfigured := false
		for _, override := range deployment.Configuration {
			if override.Setting != settingID || !override.OverridePresent || override.State != "EDITABLE" {
				continue
			}
			value, valid := override.Value.(map[string]any)
			referenceConfigured = valid && value["passwordSecretRef"] == "runtime:"+setting.RuntimeSecretRequirementRef
			if setting.RuntimeSecretUsernameRequired {
				username, ok := value["username"].(string)
				referenceConfigured = referenceConfigured && len(value) == 2 && ok && runtimeSecretUsername.MatchString(username)
			} else {
				referenceConfigured = referenceConfigured && len(value) == 1
			}
			break
		}
		result = append(result, RuntimeSecretDescriptorView{RequirementRef: setting.RuntimeSecretRequirementRef, Purpose: "SERVICE_PASSWORD", ServiceDeployment: serviceDeployment, Setting: settingID, DisplayLabel: setting.Label, ReferenceConfigured: referenceConfigured})
	}
	for _, input := range service.SecretInputs {
		if !runtimeSecretDescriptorRequirement.MatchString(input.RequirementRef) || input.DisplayLabel == "" || (input.Purpose != secretfiles.PurposeAdminToken && input.Purpose != secretfiles.PurposeUnsealShares) || input.RequiredWhen == "" || len(input.Operations) == 0 {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
		}
		result = append(result, RuntimeSecretDescriptorView{RequirementRef: input.RequirementRef, Purpose: input.Purpose, ServiceDeployment: serviceDeployment, DisplayLabel: input.DisplayLabel, RequiredWhen: input.RequiredWhen, Operations: append([]string(nil), input.Operations...)})
	}
	return result, nil
}

func (a *App) secretOutputEncryptionRequiredLocked() bool {
	if a.current.Managed == nil || a.current.Catalog == nil || a.current.Catalog.Status != "READY" {
		return false
	}
	declared := make(map[string]bool, len(a.current.Catalog.Services))
	for _, service := range a.current.Catalog.Services {
		declared[service.ID] = len(service.SecretOutputEntries) == 2 && service.SecretOutputEntries[0] == "admin-token" && service.SecretOutputEntries[1] == "unseal-shares"
	}
	for _, deployment := range a.current.Managed.Deployments {
		if declared[deployment.ServiceType] {
			return true
		}
	}
	return false
}

func (a *App) secretOutputEncryptionPasswordPresentLocked() bool {
	binding, err := a.credentialBindingLocked()
	return err == nil && a.secrets.HasOutputEncryptionPassword(binding)
}

// GetRuntimeSecretDescriptors is a target-free Core query. It exposes only
// bounded prompt metadata and never exposes the runtime reference or value.
func (a *App) GetRuntimeSecretDescriptors() RuntimeSecretDescriptorOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	return a.getRuntimeSecretDescriptorsLocked(true)
}

// ListPendingSecretOutputs exposes only bounded package metadata. The remote
// output protocol is consulted only for the currently READY, explicitly
// selected Execution Node; secret bytes remain in the dedicated delivery flow.
func (a *App) ListPendingSecretOutputs(cursor *string) SecretOutputPackagesOperation {
	a.editMu.Lock()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		a.editMu.Unlock()
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "PROJECT_NOT_OPEN", Message: projectErrorMessage("PROJECT_NOT_OPEN")}}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || a.execution.context.Status != "READY" {
		a.editMu.Unlock()
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "EXECUTION_NODE_NOT_READY", Message: projectErrorMessage("EXECUTION_NODE_NOT_READY")}}
	}
	client, ok := binding.reader.transport.(interface {
		GetSecretOutputCapabilities(context.Context, executionnode.Node, string, string) (executionnode.SecretOutputCapabilities, error)
		ListPendingSecretOutputs(context.Context, executionnode.Node, string, string, int, *string) (executionnode.SecretOutputList, error)
	})
	if !ok {
		a.editMu.Unlock()
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_UNSUPPORTED", Message: "The selected Execution Node does not support protected output delivery."}}
	}
	runtimeBinding, valid := installationRuntimeBinding(binding.reader.runtimeRelease)
	if !valid {
		a.editMu.Unlock()
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "EXECUTION_NODE_NOT_READY", Message: projectErrorMessage("EXECUTION_NODE_NOT_READY")}}
	}
	projectID, node, runtimeDigest := a.current.Project.ID, binding.node, runtimeBinding.BundleDigest
	generation, root := a.installationGeneration, a.current.Root
	ctx, cancel := a.operationContext(30 * time.Second)
	a.editMu.Unlock()
	defer cancel()
	if _, err := client.GetSecretOutputCapabilities(ctx, node, runtimeDigest, projectID); err != nil {
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_UNAVAILABLE", Message: "Secret output delivery is not available from the selected Execution Node."}}
	}
	listed, err := client.ListPendingSecretOutputs(ctx, node, runtimeDigest, projectID, 32, cursor)
	if err != nil {
		if errors.Is(err, executionnode.ErrSecretOutputRecoveryRequired) {
			return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "OUTPUT_RECOVERY_REQUIRED", Message: "Незавершённые выходные файлы сервиса сохранены на Execution Node. Требуется восстановление; частичные данные не удалены."}}
		}
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_UNAVAILABLE", Message: "Pending secret outputs could not be safely listed."}}
	}
	a.editMu.Lock()
	defer a.editMu.Unlock()
	currentBinding, bindingErr := a.resolveSelectedExecutionNodeBindingLocked()
	if a.installationGeneration != generation || a.current.Status != "OPEN" || a.current.Root != root || a.current.Project == nil || a.current.Project.ID != projectID || a.execution.context.Status != "READY" || bindingErr != nil || currentBinding != binding || currentBinding.node != node {
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "PROJECT_CHANGED", Message: projectErrorMessage("PROJECT_CHANGED")}}
	}
	currentRuntime, runtimeValid := installationRuntimeBinding(currentBinding.reader.runtimeRelease)
	if !runtimeValid || currentRuntime != runtimeBinding {
		return SecretOutputPackagesOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "PROJECT_CHANGED", Message: projectErrorMessage("PROJECT_CHANGED")}}
	}
	// A delivered/cleanup-pending remote package may no longer be listable.
	for index := range listed.Packages {
		item := &listed.Packages[index]
		_, encrypted, readErr := installer.ReadSecretOutputFiles(root, projectID, item.DeploymentID, item.PackageID, item.SourceRunID, item.Generation, item.RuntimeDigest)
		for _, data := range encrypted {
			clear(data)
		}
		if readErr == nil {
			item.State = "LOCAL_DELIVERED"
		}
	}
	// Recover its identity from the bound local receipt at known managed paths.
	if cursor == nil && a.current.Managed != nil {
		seen := map[string]bool{}
		for _, item := range listed.Packages {
			seen[item.PackageID] = true
		}
		for deployment := range a.current.Managed.Deployments {
			receipt, encrypted, readErr := installer.ReadSecretOutputReceipt(root, projectID, deployment, runtimeDigest)
			for _, data := range encrypted {
				clear(data)
			}
			if readErr != nil || seen[receipt.PackageID] {
				continue
			}
			listed.Packages = append(listed.Packages, executionnode.SecretOutputPackage{Protocol: "SecretOutputDelivery/v1alpha1", PackageID: receipt.PackageID, ProjectID: receipt.ProjectID, DeploymentID: receipt.DeploymentID, SourceRunID: receipt.SourceRunID, RuntimeDigest: receipt.RuntimeDigest, Generation: receipt.Generation, State: "LOCAL_DELIVERED", Entries: []string{"admin-token", "unseal-shares"}})
			if len(listed.Packages) >= 96 {
				break
			}
		}
	}
	return SecretOutputPackagesOperation{Status: "READY", Packages: listed.Packages, NextCursor: listed.NextCursor}
}

func (a *App) getRuntimeSecretDescriptorsLocked(clearAttached bool) RuntimeSecretDescriptorOperation {
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
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core could not safely build service secret descriptors.", DiagnosticCodes: runtimeSecretDescriptorDiagnosticCodes(err)}}
	}
	if result.ProjectRevision != revision {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned descriptors for a different saved project revision.", DiagnosticCodes: []string{"PROJECT_SNAPSHOT_REVISION_MISMATCH"}}}
	}
	if !runtimeEvidenceMatchesExpected(result.Runtime, binding.reader.runtimeRelease) {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned descriptors without matching runtime identity.", DiagnosticCodes: []string{"EXECUTION_RUNTIME_IDENTITY_MISMATCH"}}}
	}
	view := RuntimeSecretDescriptorOperation{Status: "READY", ProjectRevision: result.ProjectRevision, DescriptorSetFingerprint: result.DescriptorSetFingerprint}
	for _, item := range result.Descriptors {
		if !validRuntimeSecretDescriptor(item) {
			return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned an unsafe service secret descriptor."}}
		}
		view.Descriptors = append(view.Descriptors, RuntimeSecretDescriptorView{RequirementRef: item.RequirementRef, Purpose: item.Purpose, ServiceDeployment: item.ServiceDeployment, DisplayLabel: item.DisplayLabel, RequiredWhen: item.RequiredWhen, Operations: append([]string(nil), item.Operations...), Hosts: append([]string(nil), item.Hosts...)})
	}
	if len(view.Descriptors) > 16 {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", Message: "Core returned too many service secret descriptors."}}
	}
	// A fresh Core descriptor set invalidates values already attached to a
	// target credential, but retains local pending values long enough to prove
	// they match this exact set below.
	a.runtimeSecretEvidence = nil
	if credentialBinding, bindingErr := a.credentialBindingLocked(); clearAttached && bindingErr == nil {
		a.secrets.ClearAttachedRuntimeSecretValues(credentialBinding)
	}
	a.runtimeSecretEvidence = &runtimeSecretDescriptorEvidence{projectID: a.current.Project.ID, projectRevision: revision, nodeID: binding.node.ID, runtime: result.Runtime, fingerprint: result.DescriptorSetFingerprint, descriptors: append([]RuntimeSecretDescriptorView(nil), view.Descriptors...)}
	requirements := make([]string, 0, len(view.Descriptors))
	typedRequirements := make([]runtimesecret.RuntimeSecretInput, 0, len(view.Descriptors))
	for _, descriptor := range view.Descriptors {
		if descriptor.Purpose == "SERVICE_PASSWORD" {
			requirements = append(requirements, descriptor.RequirementRef)
		}
		if descriptor.Purpose == secretfiles.PurposeAdminToken || descriptor.Purpose == secretfiles.PurposeUnsealShares {
			typedRequirements = append(typedRequirements, runtimesecret.RuntimeSecretInput{RequirementRef: descriptor.RequirementRef, Purpose: descriptor.Purpose, ServiceDeployment: descriptor.ServiceDeployment, Operations: append([]string(nil), descriptor.Operations...)})
		}
	}
	if credentialBinding, bindingErr := a.credentialBindingLocked(); bindingErr == nil {
		if err := a.secrets.PromotePendingRuntimeSecretValues(credentialBinding, requirements); err != nil {
			a.runtimeSecretEvidence = nil
			return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
		}
		if err := a.secrets.BindPendingServiceSecretInputs(credentialBinding, typedRequirements); err != nil {
			a.runtimeSecretEvidence = nil
			return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
		}
	}
	return view
}

// runtimeSecretDescriptorDiagnosticCodes returns only bounded machine tokens
// from the fixed Execution Node protocol. It deliberately excludes diagnostic
// messages, command output, paths and all user/project data.
func runtimeSecretDescriptorDiagnosticCodes(err error) []string {
	var executionErr *executionnode.ExecutionError
	if !errors.As(err, &executionErr) || executionErr == nil {
		return nil
	}
	var result []string
	seen := make(map[string]struct{}, 4)
	appendCode := func(code string) {
		if len(result) >= 8 || len(code) > 80 || !verificationErrorCodePattern.MatchString(code) {
			return
		}
		if _, exists := seen[code]; exists {
			return
		}
		seen[code] = struct{}{}
		result = append(result, code)
	}
	appendCode(executionErr.Code)
	for _, finding := range executionErr.Findings {
		appendCode(finding.Code)
	}
	return result
}

func typedRuntimeSecretRequirements(plan executionnode.DeploymentPlan) []executionnode.RuntimeSecretInputRequirement {
	result := make([]executionnode.RuntimeSecretInputRequirement, 0)
	for _, requirement := range plan.RequiredCredentials {
		if requirement.Purpose == secretfiles.PurposeAdminToken || requirement.Purpose == secretfiles.PurposeUnsealShares {
			result = append(result, executionnode.RuntimeSecretInputRequirement{RequirementRef: requirement.RequirementRef, Purpose: requirement.Purpose})
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].RequirementRef < result[j].RequirementRef })
	return result
}

func runtimeDescriptorsMatchPlan(descriptors []RuntimeSecretDescriptorView, requirements []executionnode.RuntimeSecretInputRequirement) bool {
	actual := make([]executionnode.RuntimeSecretInputRequirement, 0)
	for _, descriptor := range descriptors {
		if descriptor.Purpose == secretfiles.PurposeAdminToken || descriptor.Purpose == secretfiles.PurposeUnsealShares {
			actual = append(actual, executionnode.RuntimeSecretInputRequirement{RequirementRef: descriptor.RequirementRef, Purpose: descriptor.Purpose})
		}
	}
	sort.Slice(actual, func(i, j int) bool { return actual[i].RequirementRef < actual[j].RequirementRef })
	if len(actual) != len(requirements) {
		return false
	}
	for i := range actual {
		if actual[i] != requirements[i] {
			return false
		}
	}
	return true
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
		return item.RequirementRef == "pki-store-password" && item.ServiceDeployment == "" && item.RequiredWhen == "ALWAYS" && len(item.Operations) == 2 && item.Operations[0] == "SERVICE_APPLY" && item.Operations[1] == "SERVICE_VERIFY"
	}
	if item.Purpose == "SERVICE_PASSWORD" {
		return item.ServiceDeployment != "" && item.RequiredWhen == "ALWAYS" && len(item.Operations) == 2 && item.Operations[0] == "SERVICE_APPLY" && item.Operations[1] == "SERVICE_VERIFY"
	}
	if item.Purpose == secretfiles.PurposeAdminToken {
		return item.ServiceDeployment != "" && item.RequiredWhen == "INITIALIZED" && len(item.Operations) == 2 && item.Operations[0] == "SERVICE_APPLY" && item.Operations[1] == "SERVICE_VERIFY"
	}
	if item.Purpose == secretfiles.PurposeUnsealShares {
		return item.ServiceDeployment != "" && item.RequiredWhen == "SEALED" && len(item.Operations) == 1 && item.Operations[0] == "SERVICE_APPLY"
	}
	return false
}

func (a *App) ClearSessionCredential() (runtimesecret.Status, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.startInFlight || a.installationRuns.hasActiveRun() || a.secrets.HasAnyRunExecutionIdentityHold() {
		return runtimesecret.Status{}, errors.New("INSTALLATION_RUN_ACTIVE")
	}
	_, err := a.credentialBindingLocked()
	if err != nil {
		return runtimesecret.Status{}, err
	}
	a.secrets.Clear()
	a.pendingHostKey = nil
	a.invalidateDynamicBindingLocked()
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
	// A draft cannot authorize execution, but merely rendering its node panel
	// must not revoke verification evidence for the still-saved revision.
	if a.activeSession == "" && a.binding != nil && a.binding.dynamic {
		_, _ = a.resolveSelectedExecutionNodeBindingLocked()
	}
	context := a.execution.context
	// Revalidating a dynamic binding while a draft is open may revoke the
	// verification of the still-saved revision. The draft is not executable.
	if a.activeSession == "" && context.Status == "READY" {
		if binding, err := a.resolveSelectedExecutionNodeBindingLocked(); err == nil {
			if digest, ok := binding.reader.runtimeRelease["bundleDigest"].(string); ok {
				context.RuntimeDigest = digest
			}
		}
	}
	return context, nil
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
		a.pendingHostKey = nil
		a.invalidateDynamicBindingLocked()
		a.clearRuntimeSecretDescriptorEvidenceLocked()
		a.current.Snapshot = nil
		a.current.Verification = notVerified()
		a.installationPlanID = ""
		a.installationGeneration++
		a.clearInstallationRunsLocked()
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
	case "SetProjectSetting", "CreateServer", "UpdateServer", "DeleteServer",
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

// AmendServiceConfigurationDraft replaces or withdraws one acknowledged
// setting command in the current unsaved session. It cannot edit other intents.
func (a *App) AmendServiceConfigurationDraft(sessionID string, index int, expected installer.EditCommand, replacement *installer.EditCommand) EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if sessionID == "" || sessionID != a.activeSession {
		return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	session, err := a.sessions.AmendConfiguration(sessionID, index, expected, replacement, a.editor)
	if err != nil {
		return a.editFailure(err)
	}
	if session.CommandCount == 0 {
		if !a.sessions.Discard(sessionID, a.editor) {
			return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
		}
		a.activeSession, a.editor = "", nil
		a.execution.discardDraft(currentProjectHosts(a.current))
		return EditOperationResult{Status: "DISCARDED"}
	}
	return EditOperationResult{Status: "EDITING", Session: &session}
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
		a.pendingTargetHostKey = nil
		clear(a.approvedTargetHostKeys)
		previousVerification := a.current.Verification
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
			a.refreshExecutionAfterSaveLocked(a.current.Root, a.current.Project, managedSnapshotHosts(managed))
		} else {
			a.pendingHostKey = nil
			a.invalidateDynamicBindingLocked()
			a.current.Managed = nil
			a.current.Snapshot = nil
			a.current.Counts.Servers = 0
			a.current.Diagnostics = nil
			a.execution.bind(a.current.Root, a.current.Project.ID, nil)
		}
		a.continuation = nil
		a.current.Verification = verificationAfterSave(previousVerification)
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

// Saving desired state invalidates plans, not an unchanged prepared transport.
// Connection authority is still checked by the normal credential/pin guards.
func (a *App) refreshExecutionAfterSaveLocked(root string, project *projectlifecycle.Project, hosts map[string]map[string]any) {
	if project != nil && a.binding != nil && a.binding.dynamic &&
		a.execution.root == root && a.execution.projectID == project.ID &&
		a.execution.context.SelectionKind == "PROJECT_SERVER" {
		id, address, port, err := a.selectedSavedExecutionServerLocked()
		runtime, valid := installationRuntimeBinding(a.binding.reader.runtimeRelease)
		if err == nil && id == a.binding.node.ID && address == a.binding.node.Address && port == a.binding.node.Port &&
			valid && runtime.BundleDigest == project.Source.BundleDigest && runtime.CatalogDigest == project.Source.CatalogDigest {
			a.pendingHostKey = nil
			a.execution.replaceSnapshotHosts(hosts)
			if candidate, ok := a.execution.candidates[id]; ok {
				a.execution.context.SafeLabel = candidate.label
			}
			a.clearRuntimeSecretDescriptorEvidenceLocked()
			a.installationGeneration++
			a.continuation = nil
			a.installationPlanID = ""
			a.clearInstallationRunsLocked()
			return
		}
	}
	a.bindExecutionLocked(root, project, hosts)
}

func (a *App) bindExecutionLocked(root string, project *projectlifecycle.Project, hosts map[string]map[string]any) {
	a.pendingHostKey = nil
	a.pendingTargetHostKey = nil
	clear(a.approvedTargetHostKeys)
	a.invalidateDynamicBindingLocked()
	a.clearRuntimeSecretDescriptorEvidenceLocked()
	a.installationGeneration++
	a.continuation = nil
	a.installationPlanID = ""
	a.clearInstallationRunsLocked()
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

// GetServiceConfigurationPreview obtains a read-only Core projection for the
// exact saved revision. It neither changes Verify state nor creates a plan.
func (a *App) GetServiceConfigurationPreview() (executionnode.ServiceConfigurationPreview, error) {
	a.editMu.Lock()
	if a.current.Status != "OPEN" || a.current.Managed == nil || a.current.Catalog == nil || a.current.Catalog.Status != "READY" || a.execution.context.Status != "READY" {
		a.editMu.Unlock()
		return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_UNAVAILABLE")
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		a.editMu.Unlock()
		return executionnode.ServiceConfigurationPreview{}, err
	}
	transport, ok := binding.reader.transport.(interface {
		BuildServiceConfigurationPreview(context.Context, executionnode.Node, string, map[string]any) (executionnode.ServiceConfigurationPreview, error)
	})
	if !ok {
		a.editMu.Unlock()
		return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED")
	}
	root := a.current.Root
	revision, err := installer.ProjectRevision(root)
	if err != nil || revision != a.current.Managed.ProjectRevision {
		a.editMu.Unlock()
		return executionnode.ServiceConfigurationPreview{}, errors.New("PROJECT_REVISION_CHANGED")
	}
	a.editMu.Unlock()
	ctx, cancel := a.operationContext(90 * time.Second)
	defer cancel()
	preview, err := transport.BuildServiceConfigurationPreview(ctx, binding.node, root, binding.reader.runtimeRelease)
	if err != nil {
		return executionnode.ServiceConfigurationPreview{}, err
	}
	a.editMu.Lock()
	defer a.editMu.Unlock()
	after, err := installer.ProjectRevision(root)
	if err != nil || a.current.Status != "OPEN" || a.current.Root != root || a.current.Managed == nil || a.current.Catalog == nil || a.current.Catalog.Status != "READY" || a.current.Managed.ProjectRevision != revision || after != revision || preview.ProjectRevision != revision || !runtimeEvidenceMatchesExpected(preview.Runtime, binding.reader.runtimeRelease) || a.revalidateBindingBeforePublicationLocked(binding) != nil {
		return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_STALE")
	}
	for deploymentID, scoped := range preview.Services {
		deployment, present := a.current.Managed.Deployments[deploymentID]
		if !present {
			return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
		}
		var service *projectlifecycle.ProjectCatalogService
		for index := range a.current.Catalog.Services {
			if a.current.Catalog.Services[index].ID == deployment.ServiceType {
				service = &a.current.Catalog.Services[index]
				break
			}
		}
		if service == nil {
			return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
		}
		filter := func(values map[string]executionnode.ServiceConfigurationValue) {
			for settingID, item := range values {
				var descriptor *projectlifecycle.ProjectCatalogSetting
				for index := range service.ConfigurationSettings {
					if service.ConfigurationSettings[index].ID == settingID {
						descriptor = &service.ConfigurationSettings[index]
						break
					}
				}
				if descriptor == nil || descriptor.Kind != "MANAGED" || descriptor.EditorShape == "UNSUPPORTED" || descriptor.EditorShape == "RUNTIME_SECRET_REFERENCE_OBJECT" {
					delete(values, settingID)
					continue
				}
				if item.State != "RESOLVED" || !projectlifecycle.SafePresentationValue(*descriptor, item.Value) {
					item.Value = nil
					values[settingID] = item
				}
			}
		}
		filter(scoped.Configuration)
		for memberID, values := range scoped.Members {
			found := false
			for _, placement := range a.current.Managed.MemberPlacements {
				if placement.DeploymentID == deploymentID && placement.MemberID == memberID {
					found = true
					break
				}
			}
			if !found {
				return executionnode.ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
			}
			filter(values)
		}
	}
	preview.RuntimeDigest = preview.Runtime.BundleDigest
	return preview, nil
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
	if strings.HasPrefix(err.Error(), "EXECUTION_NODE_TRANSPORT_FAILED") {
		return "EXECUTION_NODE_UNAVAILABLE"
	}
	return err.Error()
}

func projectErrorMessage(code string) string {
	switch code {
	case "SESSION_CREDENTIAL_UNAVAILABLE":
		return "Учётные данные SSH-сеанса недоступны или срок их действия истёк. Укажите пароль или приватный ключ PEM на странице «Серверы»."
	case "SESSION_CREDENTIAL_PASSWORD_FORMAT_UNSUPPORTED":
		return "Пароль SSH или sudo не должен содержать перенос строки или нулевой символ. Введите пароль заново."
	case "INSTALLATION_RUN_ACTIVE":
		return "Новый набор пока нельзя проверить: прежний запуск не подтверждён как завершённый. Нажмите «Проверить прежний запуск»; не запускайте план повторно."
	case "RUNTIME_BUNDLE_UPDATE_UNAVAILABLE":
		return "Проверка нового набора сейчас недоступна. Убедитесь, что управляемый проект открыт, изменения сохранены и другая операция не выполняется."
	case "RUNTIME_BUNDLE_PREVIEW_STALE":
		return "Предварительная проверка набора устарела. Нажмите «Проверить новый набор» ещё раз."
	case "LOCAL_RUN_RECORD_INVALID":
		return "Локальная запись прежнего запуска повреждена. Блокировка сохранена; не удаляйте запись вручную."
	case "LOCAL_RUN_RECORD_UNAVAILABLE":
		return "Не удалось сохранить подтверждённый статус прежнего запуска. Повторите проверку; блокировка пока сохранена."
	case "ORPHAN_RUN_IDENTITY_UNVERIFIED":
		return "Execution Node не подтвердил принадлежность прежнего запуска этому проекту. Блокировка сохранена."
	case "ORPHAN_RUN_STATE_UNKNOWN":
		return "Не удалось подтвердить итог прежнего запуска. Блокировка сохранена; проверьте доступность узла и повторите проверку."
	case "ORPHAN_RUN_CANCEL_UNCONFIRMED":
		return "Отмена прежнего запуска не подтверждена. Проверьте его фактическое состояние; блокировка сохранена."
	case "EXECUTION_NODE_NOT_CONFIGURED":
		return "Не настроен READY Execution Node для read-only открытия проекта."
	case "EXECUTION_NODE_UNAVAILABLE":
		return "Execution Node недоступен. Проект на диске не изменён."
	case "EXECUTION_NODE_PREPARE_INSPECT_FAILED":
		return "Подготовка остановилась при повторной проверке узла. Проверьте соединение и повторите подготовку. Проект не изменён."
	case "EXECUTION_NODE_PREPARE_WORKSPACE_FAILED":
		return "Не удалось передать рабочий каталог Execution Node текущему SSH-пользователю. Проверьте владельца каталога и отсутствие симлинков, затем повторите подготовку."
	case "EXECUTION_NODE_PREPARE_STAGE_FAILED":
		return "Подготовка остановилась при передаче проверенного runtime bundle. Проверьте доступность узла и свободное место. Проект не изменён."
	case "EXECUTION_NODE_PREPARE_ACTIVATE_FAILED":
		return "Подготовка остановилась при активации runtime на узле. Проверьте состояние узла; повторная подготовка безопасна. Проект не изменён."
	case "EXECUTION_NODE_READY_REQUIRED":
		return "Требуется READY Execution Node. Проверьте или подготовьте его на странице Серверы."
	case "EXECUTION_NODE_BINDING_REQUIRED":
		return "Выбранный Execution Node не имеет доверенного runtime binding. Откройте страницу Серверы."
	case "EXECUTION_NODE_PEM_REQUIRED":
		return "Для подключения нужны действующие учётные данные SSH-сеанса: пароль или приватный ключ PEM."
	case "EXECUTION_NODE_USER_INVALID":
		return "Имя технического пользователя не подходит для подключения к узлу выполнения."
	case "EXECUTION_NODE_HOST_KEY_PROBE_FAILED":
		return "Не удалось получить ключ SSH выбранного узла. Подключение не подтверждено."
	case "EXECUTION_NODE_HOST_KEY_APPROVAL_STALE":
		return "Данные ключа SSH изменились или истекли. Повторите получение отпечатка."
	case "TARGET_HOST_TRUST_PROJECT_UNAVAILABLE", "TARGET_HOST_TRUST_PROJECT_STALE", "TARGET_HOST_TRUST_STALE":
		return "Проект изменился. Сохраните изменения и повторно подтвердите SSH-ключи целевых серверов."
	case "TARGET_HOST_TRUST_SERVER_INVALID":
		return "У сохранённого сервера нет допустимого адреса или SSH-порта."
	case "TARGET_HOST_KEY_PROBE_FAILED":
		return "Не удалось получить SSH-ключ целевого сервера. Подключение не подтверждено."
	case "TARGET_HOST_KEY_APPROVAL_STALE":
		return "Отпечаток целевого сервера устарел. Получите его снова и сверьте независимо."
	case "TARGET_HOST_TRUST_REQUIRED":
		return "Перед запуском подтвердите SSH-ключ каждого целевого сервера на странице Серверы."
	case "TARGET_HOST_TRUST_INVALID":
		return "Подтверждённые SSH-ключи не соответствуют адресам текущего плана. Запуск заблокирован."
	case "EXECUTION_NODE_BINDING_INVALID":
		return "Доверенная привязка узла изменилась. Повторно проверьте ключ и подключение."
	case "EXECUTION_BUNDLE_UNAVAILABLE":
		return "Для проекта нет одного совместимого проверенного runtime bundle."
	case "PROJECT_CHANGES_UNSAVED":
		return "Сначала сохраните или отмените несохранённые изменения проекта."
	case "PROJECT_REVISION_UNAVAILABLE":
		return "Не удалось безопасно прочитать сохранённую ревизию проекта."
	case "RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND":
		return "Для выбранного сервиса в текущем режиме секреты не требуются."
	case "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE":
		return "Не удалось получить требования к секретам от Core на узле выполнения. Проверьте доступность узла и повторите запуск этого плана; секреты не удалены."
	case "RUNTIME_SECRET_DESCRIPTORS_UNSUPPORTED":
		return "Активный runtime узла выполнения не поддерживает проверку секретов сервисов. Обновите набор установки и подготовьте узел заново."
	case "RUNTIME_SECRET_DESCRIPTORS_RESPONSE_INVALID":
		return "Узел выполнения вернул некорректный ответ о требованиях к секретам. Запуск не начат; проверьте активный runtime узла."
	case "RUNTIME_SECRET_DESCRIPTORS_STALE", "RUNTIME_SECRET_INPUT_EXPIRED":
		return "Введённые секреты больше не соответствуют свежему плану или истекли. Введите их заново."
	case "RUNTIME_SECRET_INPUT_INVALID":
		return "Секрет должен быть непустым корректным текстом и укладываться в допустимый размер."
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
	case "APPLICATION_CONFIG_UPGRADE_REQUIRED":
		return "Обновите config/application.yml: добавьте приоритеты сервисов и установите schemaVersion: 2."
	case "APPLICATION_CONFIG_SERVICE_PRIORITIES_INVALID", "APPLICATION_CONFIG_SERVICE_PRIORITY_INVALID", "APPLICATION_CONFIG_SERVICE_PRIORITY_DUPLICATE":
		return "В config/application.yml проверьте список serviceExecutionPriorities: каждому типу сервиса нужен один уникальный неотрицательный приоритет."
	case "DEPLOYMENT_ORDER_RUNTIME_UNSUPPORTED":
		return "Узел выполнения использует runtime без поддержки упорядоченного плана. Опубликуйте и привяжите актуальный runtime bundle, затем подготовьте узел заново."
	case "DEPLOYMENT_ORDER_REQUEST_INVALID", "DEPLOYMENT_ORDER_INVALID":
		return "Список сервисов для плана некорректен. Обновите приложение и повторите построение плана."
	case "DEPLOYMENT_ORDER_REQUEST_VERSION_REQUIRED":
		return "Runtime узла не поддерживает обязательный формат порядка сервисов. Обновите bundle и подготовьте узел заново."
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
		return "Удаление заблокировано: в проекте остались ссылки на удаляемый объект."
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
	case "CORE_OPERATION_FAILED":
		return "Core на узле выполнения не смог завершить операцию. Проверьте код ошибки и диагностику runtime; проект на диске не изменён."
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

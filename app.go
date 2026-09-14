package main

import (
	"context"
	"errors"
	"sort"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

// projectSnapshotReader is intentionally narrower than the future editor
// backend: UI-01B can only obtain an authoritative read-only Core projection.
type projectSnapshotReader interface {
	BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error)
}

type candidateProjectSnapshotReader interface {
	BuildCandidateProjectSnapshot(context.Context, executionnode.Node, string, map[string]any, executionnode.CandidateProjectSnapshotRequest) (*coreadapter.Snapshot, error)
}

type candidateReadyReader interface{ CheckCandidateReady(context.Context) error }

type projectReader struct {
	transport      projectSnapshotReader
	node           executionnode.Node
	runtimeRelease map[string]any
}

func (r projectReader) BuildSnapshot(ctx context.Context, root string) (*coreadapter.Snapshot, error) {
	if r.transport == nil || r.node.ID == "" || len(r.runtimeRelease) == 0 {
		return nil, errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return r.transport.BuildProjectSnapshot(ctx, r.node, root, r.runtimeRelease)
}

func (r projectReader) BuildCandidateSnapshot(ctx context.Context, root string, owned []string, project *projectlifecycle.Project) (*coreadapter.Snapshot, error) {
	transport, ok := r.transport.(candidateProjectSnapshotReader)
	if !ok || project == nil {
		return nil, errors.New("PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED")
	}
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		return nil, err
	}
	return transport.BuildCandidateProjectSnapshot(ctx, r.node, root, r.runtimeRelease, executionnode.CandidateProjectSnapshotRequest{
		ProjectIdentity: project.ID, CandidateProjectRevision: revision, ArtifactLockDigest: project.Source.BundleDigest,
		CatalogLockDigest: project.Source.CatalogDigest, InstallerOwnedLogicalPaths: owned,
	})
}

func (r projectReader) CheckCandidateReady(ctx context.Context) error {
	checker, ok := r.transport.(interface {
		CheckCandidateProjectSnapshotCapability(context.Context, executionnode.Node, map[string]any) error
	})
	if !ok || r.node.ID == "" || len(r.runtimeRelease) == 0 {
		return errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return checker.CheckCandidateProjectSnapshotCapability(ctx, r.node, r.runtimeRelease)
}

type candidateCoreAdapter struct {
	reader interface {
		BuildCandidateSnapshot(context.Context, string, []string, *projectlifecycle.Project) (*coreadapter.Snapshot, error)
	}
	project *projectlifecycle.Project
}

func (a candidateCoreAdapter) BuildSnapshot(ctx context.Context, root string, owned []string) (*coreadapter.Snapshot, error) {
	return a.reader.BuildCandidateSnapshot(ctx, root, owned, a.project)
}

type unavailableProjectReader struct{}

func (unavailableProjectReader) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return nil, errors.New("EXECUTION_NODE_NOT_CONFIGURED")
}

type ProjectOpenResult struct {
	Status         string                    `json:"status"`
	Root           string                    `json:"root,omitempty"`
	Classification string                    `json:"classification,omitempty"`
	Project        *projectlifecycle.Project `json:"project,omitempty"`
	Counts         projectlifecycle.Counts   `json:"counts"`
	Snapshot       *coreadapter.Snapshot     `json:"snapshot,omitempty"`
	Diagnostics    []ApplicationDiagnostic   `json:"diagnostics,omitempty"`
	Error          *ProjectOpenError         `json:"error,omitempty"`
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

type App struct {
	ctx    context.Context
	reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	lifecycle     projectLifecycle
	current       ProjectOpenResult
	sessions      *installer.EditSessionStore
	editor        *installer.Backend
	activeSession string
	editMu        sync.Mutex
	config        appconfig.Config
	configErr     error
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

type projectLifecycle interface {
	CreateProject(context.Context, projectlifecycle.CreateProjectRequest) (projectlifecycle.Result, error)
	OpenProject(context.Context, string) (projectlifecycle.Result, error)
}

func NewApp(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, lifecycle projectLifecycle, options ...AppOption) *App {
	app := &App{reader: reader, lifecycle: lifecycle, sessions: installer.NewEditSessionStore(), current: ProjectOpenResult{Status: "NO_PROJECT"}, configErr: errors.New("APPLICATION_CONFIG_NOT_FOUND")}
	for _, option := range options {
		option(app)
	}
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

func (a *App) startup(ctx context.Context) { a.ctx = ctx }

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

func (a *App) CreateProject(request projectlifecycle.CreateProjectRequest) ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	if a.lifecycle == nil {
		return a.failure("PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE")
	}
	result, err := a.lifecycle.CreateProject(context.Background(), request)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	a.current = ProjectOpenResult{Status: "OPEN", Root: result.Root, Classification: result.Classification, Project: result.Project, Counts: result.Counts}
	return a.current
}

func (a *App) OpenProject(root string) ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	if a.lifecycle == nil {
		return a.failure("PROJECT_OPEN_BLOCKED")
	}
	local, err := a.lifecycle.OpenProject(context.Background(), root)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	if local.Classification == "EMPTY_MANAGED_PROJECT" {
		a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project, Counts: local.Counts}
		return a.current
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	snapshot, err := a.reader.BuildSnapshot(ctx, local.Root)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project, Counts: local.Counts, Snapshot: snapshot, Diagnostics: a.serverTypeDiagnostics(snapshot)}
	return a.current
}

func (a *App) CloseProject() ProjectOpenResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.activeSession != "" {
		return a.failure("EDIT_SESSION_ACTIVE")
	}
	a.current = ProjectOpenResult{Status: "NO_PROJECT"}
	return a.current
}

type EditOperationResult struct {
	Status      string                      `json:"status"`
	Session     *installer.EditSession      `json:"session,omitempty"`
	Plan        *installer.EditPlan         `json:"plan,omitempty"`
	Commit      *installer.EditCommitResult `json:"commit,omitempty"`
	Diagnostics []ApplicationDiagnostic     `json:"diagnostics,omitempty"`
	Error       *ProjectOpenError           `json:"error,omitempty"`
}

func (a *App) editFailure(err error) EditOperationResult {
	code := projectErrorCode(err)
	return EditOperationResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func (a *App) StartEditSession() EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return a.editFailure(errors.New("PROJECT_NOT_OPEN"))
	}
	reader, ok := a.reader.(interface {
		BuildCandidateSnapshot(context.Context, string, []string, *projectlifecycle.Project) (*coreadapter.Snapshot, error)
	})
	if !ok {
		return a.editFailure(errors.New("PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED"))
	}
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
	a.editor = installer.NewBackend(candidateCoreAdapter{reader: reader, project: a.current.Project}, installer.WithServerTypes(typeIDs))
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
	case "CreateServer", "UpdateServer", "DeleteServer":
	default:
		return a.editFailure(errors.New("EDIT_OPERATION_NOT_AVAILABLE"))
	}
	session, err := a.sessions.Append(sessionID, command, a.editor)
	if err != nil {
		return a.editFailure(err)
	}
	result := EditOperationResult{Status: "EDITING", Session: &session}
	if command.ServerType != "" && a.configErr == nil && !a.config.HasServerType(command.ServerType) {
		result.Diagnostics = []ApplicationDiagnostic{{Code: "UNKNOWN_CONFIGURED_SERVER_TYPE", Severity: "WARNING", HostID: command.HostID, SafeMessage: "Server type is not present in the current application configuration"}}
	}
	return result
}

func (a *App) ReviewEditSession(sessionID string) EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.editor == nil || sessionID == "" || sessionID != a.activeSession {
		return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	plan, err := a.sessions.Review(ctx, a.editor, sessionID)
	if err != nil {
		return a.editFailure(err)
	}
	return EditOperationResult{Status: plan.Status, Plan: plan}
}

func (a *App) CommitEditPlan(sessionID, planID string) EditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if a.editor == nil || sessionID == "" || sessionID != a.activeSession {
		return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	if _, err := a.sessions.BeginCommit(sessionID, planID); err != nil {
		return a.editFailure(err)
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	ready, ok := a.reader.(candidateReadyReader)
	if !ok {
		a.sessions.FinishCommit(sessionID, planID, false)
		return a.editFailure(errors.New("EXECUTION_NODE_NOT_CONFIGURED"))
	}
	if err := ready.CheckCandidateReady(ctx); err != nil {
		a.sessions.FinishCommit(sessionID, planID, false)
		return a.editFailure(err)
	}
	result := a.editor.CommitEditPlanV2(ctx, planID)
	if result.Status == "COMMITTED" || result.Status == "COMMITTED_REFRESH_FAILED" {
		if !a.sessions.FinishCommit(sessionID, planID, true) {
			return a.editFailure(errors.New("EDIT_SESSION_EXPIRED"))
		}
		a.activeSession = ""
		a.editor = nil
		if snapshot, ok := result.Snapshot.(*coreadapter.Snapshot); ok {
			a.current.Snapshot = snapshot
			a.current.Diagnostics = a.serverTypeDiagnostics(snapshot)
			a.current.Classification = projectlifecycle.ClassificationManaged
		} else if result.Status == "COMMITTED_REFRESH_FAILED" {
			// The transaction committed, but no post-commit Core projection is
			// authoritative. Never leave a previous snapshot visible as current.
			a.current.Snapshot = nil
			a.current.Diagnostics = nil
			a.current.Classification = projectlifecycle.ClassificationManaged
		}
	}
	if result.Status != "COMMITTED" && result.Status != "COMMITTED_REFRESH_FAILED" {
		a.sessions.FinishCommit(sessionID, planID, false)
	}
	return EditOperationResult{Status: result.Status, Commit: &result}
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
	return EditOperationResult{Status: "DISCARDED"}
}

func (a *App) reconcileEditSessionLocked() {
	if a.activeSession != "" && !a.sessions.Active(a.activeSession) {
		a.activeSession, a.editor = "", nil
	}
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
	case "PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED":
		return "Активный Execution Node не поддерживает проверку edit candidate."
	case "WRITE_OWNERSHIP_REQUIRED", "WRITE_NOT_ALLOWED", "DOCUMENT_CHANGED", "PROJECT_CHANGED":
		return "Сохранение заблокировано: проект или владение документами изменилось."
	case "PROJECT_INPUT_INCOMPLETE", "MANAGED_PROJECT_INVALID", "PROJECT_OPEN_BLOCKED":
		return "Выбранный проект нельзя безопасно открыть в текущем режиме."
	default:
		return "Не удалось открыть проект в режиме только чтения. Проект на диске не изменён."
	}
}

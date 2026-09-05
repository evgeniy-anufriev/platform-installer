package main

import (
	"context"
	"errors"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/projectlifecycle"
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
	Status         string                    `json:"status"`
	Root           string                    `json:"root,omitempty"`
	Classification string                    `json:"classification,omitempty"`
	Project        *projectlifecycle.Project `json:"project,omitempty"`
	Counts         projectlifecycle.Counts   `json:"counts"`
	Snapshot       *coreadapter.Snapshot     `json:"snapshot,omitempty"`
	Error          *ProjectOpenError         `json:"error,omitempty"`
}

type ProjectOpenError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type App struct {
	ctx    context.Context
	reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	lifecycle projectLifecycle
	current   ProjectOpenResult
}

type projectLifecycle interface {
	CreateProject(context.Context, projectlifecycle.CreateProjectRequest) (projectlifecycle.Result, error)
	OpenProject(context.Context, string) (projectlifecycle.Result, error)
}

func NewApp(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}, lifecycle projectLifecycle) *App {
	return &App{reader: reader, lifecycle: lifecycle, current: ProjectOpenResult{Status: "NO_PROJECT"}}
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
		return a.current
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
	a.current = ProjectOpenResult{Status: "OPEN", Root: local.Root, Classification: local.Classification, Project: local.Project, Counts: local.Counts, Snapshot: snapshot}
	return a.current
}

func (a *App) CloseProject() ProjectOpenResult {
	a.current = ProjectOpenResult{Status: "NO_PROJECT"}
	return a.current
}

func (a *App) CurrentProject() ProjectOpenResult { return a.current }

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
	case "PROJECT_INPUT_INCOMPLETE", "MANAGED_PROJECT_INVALID", "PROJECT_OPEN_BLOCKED":
		return "Выбранный проект нельзя безопасно открыть в текущем режиме."
	default:
		return "Не удалось открыть проект в режиме только чтения. Проект на диске не изменён."
	}
}

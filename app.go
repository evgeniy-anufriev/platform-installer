package main

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
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
	Status   string                `json:"status"`
	Root     string                `json:"root,omitempty"`
	Snapshot *coreadapter.Snapshot `json:"snapshot,omitempty"`
	Error    *ProjectOpenError     `json:"error,omitempty"`
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
	current ProjectOpenResult
}

func NewApp(reader interface {
	BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
}) *App {
	return &App{reader: reader, current: ProjectOpenResult{Status: "NO_PROJECT"}}
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

func (a *App) OpenProject(root string) ProjectOpenResult {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return a.failure("PROJECT_PATH_INVALID")
	}
	info, err := os.Lstat(absolute)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return a.failure("PROJECT_PATH_INVALID")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	snapshot, err := a.reader.BuildSnapshot(ctx, absolute)
	if err != nil {
		return a.failure(projectErrorCode(err))
	}
	a.current = ProjectOpenResult{Status: "OPEN", Root: absolute, Snapshot: snapshot}
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
	default:
		return "Не удалось открыть проект в режиме только чтения. Проект на диске не изменён."
	}
}

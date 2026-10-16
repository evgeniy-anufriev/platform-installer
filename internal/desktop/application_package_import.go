package desktop

import (
	"errors"
	"time"
)

func (a *App) ChooseApplicationPackageDirectory() string {
	if a.ctx == nil {
		return ""
	}
	root, err := a.openDirectory(a.ctx, DialogOptions{Title: "Выбрать пакет приложения или библиотеки"})
	if err != nil {
		return ""
	}
	return root
}

// Only plans a data-only package through the existing active edit session.
// CommitStructuralEditPlan handles revision, transaction, recovery and refresh.
func (a *App) ReviewApplicationPackageImport(sessionID, source, kind, name, version, digest string) StructuralEditOperationResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	if sessionID == "" || sessionID != a.activeSession || a.editor == nil {
		return a.structuralEditFailure(errors.New("EDIT_SESSION_EXPIRED"))
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	plan, err := a.sessions.ReviewApplicationPackageImport(ctx, a.editor, sessionID, source, kind, name, version, digest)
	if err != nil {
		return a.structuralEditFailure(err)
	}
	return StructuralEditOperationResult{Status: plan.Status, Plan: plan}
}

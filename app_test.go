package main

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

type snapshotReaderStub struct {
	snapshot *coreadapter.Snapshot
	err      error
}

type editorReaderStub struct{ readyErr error }

type acceptanceReader struct {
	projectReader
	t *testing.T
}

func (r acceptanceReader) BuildCandidateSnapshot(ctx context.Context, root string, owned []string, project *projectlifecycle.Project) (*coreadapter.Snapshot, error) {
	revision, _ := installer.ProjectRevision(root)
	r.t.Logf("candidate request: project=%s revision=%s bundle=%s catalog=%s owned=%v", project.ID, revision, project.Source.BundleDigest, project.Source.CatalogDigest, owned)
	snapshot, err := r.projectReader.BuildCandidateSnapshot(ctx, root, owned, project)
	if err != nil {
		r.t.Logf("candidate snapshot error: %v", err)
		var executionErr *executionnode.ExecutionError
		if errors.As(err, &executionErr) {
			r.t.Logf("candidate snapshot findings: %+v", executionErr.Findings)
		}
	}
	return snapshot, err
}

func (editorReaderStub) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return nil, errors.New("not used")
}
func (r editorReaderStub) CheckCandidateReady(context.Context) error { return r.readyErr }
func (editorReaderStub) BuildCandidateSnapshot(_ context.Context, root string, _ []string, _ *projectlifecycle.Project) (*coreadapter.Snapshot, error) {
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		return nil, err
	}
	return &coreadapter.Snapshot{Status: "PASS", ProjectRevision: revision, SnapshotFingerprint: "sha256:" + string(make([]byte, 64)), Hosts: map[string]map[string]any{"node1": {"type": "infra"}}}, nil
}

func testApplicationConfig() AppOption {
	return WithApplicationConfig(appconfig.Config{SchemaVersion: 1, ServerTypes: []appconfig.ServerType{{ID: "infra", DisplayName: "Инфраструктура"}}}, nil)
}

func (s snapshotReaderStub) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return s.snapshot, s.err
}

type lifecycleStub struct {
	result projectlifecycle.Result
	err    error
}

func (s lifecycleStub) CreateProject(context.Context, projectlifecycle.CreateProjectRequest) (projectlifecycle.Result, error) {
	return s.result, s.err
}
func (s lifecycleStub) OpenProject(context.Context, string) (projectlifecycle.Result, error) {
	return s.result, s.err
}

func TestAppOpenProjectIsReadOnlyAndRetainsNoErrorState(t *testing.T) {
	root := t.TempDir()
	app := NewApp(snapshotReaderStub{snapshot: &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision"}}, lifecycleStub{result: projectlifecycle.Result{Root: root, Classification: "MANAGED_PROJECT"}})
	result := app.OpenProject(root)
	if result.Status != "OPEN" || result.Root == "" || result.Snapshot == nil {
		t.Fatalf("result=%+v", result)
	}
	if closed := app.CloseProject(); closed.Status != "NO_PROJECT" || closed.Snapshot != nil {
		t.Fatalf("closed=%+v", closed)
	}
}

func TestAppReturnsSafeFailure(t *testing.T) {
	app := NewApp(snapshotReaderStub{err: errors.New("EXECUTION_NODE_UNAVAILABLE")}, lifecycleStub{result: projectlifecycle.Result{Root: t.TempDir(), Classification: "MANAGED_PROJECT"}})
	result := app.OpenProject(t.TempDir())
	if result.Status != "ERROR" || result.Error == nil || result.Error.Code != "EXECUTION_NODE_UNAVAILABLE" || result.Error.Message == "EXECUTION_NODE_UNAVAILABLE" {
		t.Fatalf("result=%+v", result)
	}
}

func TestApplicationConfigFailureDoesNotBlockReadOnlyOpen(t *testing.T) {
	snapshot := &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision", SnapshotFingerprint: "sha256:fingerprint", Hosts: map[string]map[string]any{"node1": {"type": "scada"}}}
	app := NewApp(snapshotReaderStub{snapshot: snapshot}, lifecycleStub{result: projectlifecycle.Result{Root: t.TempDir(), Classification: "MANAGED_PROJECT"}})
	result := app.OpenProject(t.TempDir())
	if result.Status != "OPEN" || result.Snapshot != snapshot {
		t.Fatalf("read-only open blocked: %#v", result)
	}
	if config := app.GetApplicationConfig(); config.Status != "ERROR" || config.Error == nil {
		t.Fatalf("config=%#v", config)
	}
}

func TestApplicationConfigFailureBlocksNewServerWithoutWriting(t *testing.T) {
	root := t.TempDir()
	manifest := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services: {}\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa", Name: "Test"}
	app := NewApp(editorReaderStub{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: project}
	started := app.StartEditSession()
	result := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", Address: "192.0.2.10"})
	if result.Error == nil || result.Error.Code != "APPLICATION_CONFIG_UNAVAILABLE" {
		t.Fatalf("result=%#v", result)
	}
	if _, err := os.Stat(filepath.Join(root, "inventory")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("blocked command wrote inventory: %v", err)
	}
}

func TestUnknownAndLegacyServerTypesArePresentationDiagnosticsOnly(t *testing.T) {
	snapshot := &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision", SnapshotFingerprint: "sha256:unchanged", Validation: map[string]any{"status": "PASS"}, Hosts: map[string]map[string]any{"known": {"type": "infra"}, "unknown": {"type": "scada"}, "legacy": {}}}
	app := NewApp(snapshotReaderStub{snapshot: snapshot}, lifecycleStub{result: projectlifecycle.Result{Root: t.TempDir(), Classification: "MANAGED_PROJECT"}}, testApplicationConfig())
	result := app.OpenProject(t.TempDir())
	if result.Snapshot != snapshot || snapshot.Status != "PASS" || snapshot.SnapshotFingerprint != "sha256:unchanged" || snapshot.Validation["status"] != "PASS" {
		t.Fatal("application diagnostics mutated authoritative snapshot")
	}
	if len(result.Diagnostics) != 2 || result.Diagnostics[0].Severity != "WARNING" || result.Diagnostics[1].Severity != "WARNING" {
		t.Fatalf("diagnostics=%#v", result.Diagnostics)
	}
}

func TestUnknownNewServerTypeReturnsNonBlockingDiagnostic(t *testing.T) {
	root := t.TempDir()
	manifest := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services: {}\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	app := NewApp(editorReaderStub{}, lifecycleStub{}, testApplicationConfig())
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
	started := app.StartEditSession()
	if started.Error != nil || started.Session == nil {
		t.Fatalf("start=%#v", started)
	}
	result := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "scada", Address: "192.0.2.10"})
	if result.Error != nil || result.Status != "EDITING" || len(result.Diagnostics) != 1 || result.Diagnostics[0].Code != "UNKNOWN_CONFIGURED_SERVER_TYPE" {
		t.Fatalf("result=%#v", result)
	}
	if currentRevision, err := installer.ProjectRevision(root); err != nil || currentRevision != revision {
		t.Fatalf("revision=%q err=%v", currentRevision, err)
	}
}

func TestAppKeepsEmptyProjectLocalWithoutSnapshotCall(t *testing.T) {
	project := &projectlifecycle.Project{ID: "project-0123456789abcdef", Name: "Empty"}
	app := NewApp(snapshotReaderStub{err: errors.New("snapshot must not be called")}, lifecycleStub{result: projectlifecycle.Result{Root: t.TempDir(), Classification: "EMPTY_MANAGED_PROJECT", Project: project}})
	result := app.OpenProject(t.TempDir())
	if result.Status != "OPEN" || result.Classification != "EMPTY_MANAGED_PROJECT" || result.Project != project || result.Snapshot != nil {
		t.Fatalf("result=%+v", result)
	}
	created := app.CreateProject(projectlifecycle.CreateProjectRequest{ProjectRoot: t.TempDir(), DisplayName: "Empty", CompatibilitySourceID: "default"})
	if created.Status != "OPEN" || created.Snapshot != nil {
		t.Fatalf("created=%+v", created)
	}
}

func TestAppFirstSaveRequiresReviewAndConsumesSession(t *testing.T) {
	root := t.TempDir()
	manifest := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services:\n    kafka:\n      definitionVersion: 1.0.0\n      digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa", Name: "Test", Source: projectlifecycle.CompatibilitySourceSummary{BundleDigest: "sha256:" + string(make([]byte, 64)), CatalogDigest: "sha256:" + string(make([]byte, 64))}}
	app := NewApp(editorReaderStub{}, lifecycleStub{}, testApplicationConfig())
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: project}
	started := app.StartEditSession()
	if started.Status != "EDITING" || started.Session == nil {
		t.Fatalf("started=%#v", started)
	}
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("appended=%#v", appended)
	}
	plan := app.ReviewEditSession(started.Session.SessionID)
	if plan.Plan == nil || !plan.Plan.CommitAllowed {
		t.Fatalf("plan=%#v", plan)
	}
	latest := app.ReviewEditSession(started.Session.SessionID)
	if latest.Plan == nil || latest.Plan.PlanID == plan.Plan.PlanID {
		t.Fatalf("latest plan=%#v", latest)
	}
	stale := app.CommitEditPlan(started.Session.SessionID, plan.Plan.PlanID)
	if stale.Status != "BLOCKED" {
		t.Fatalf("stale commit=%#v", stale)
	}
	if _, err := os.Stat(filepath.Join(root, "ansible.cfg")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("stale plan mutated project: %v", err)
	}
	app.reader = editorReaderStub{readyErr: errors.New("EXECUTION_NODE_UNAVAILABLE")}
	unavailable := app.CommitEditPlan(started.Session.SessionID, latest.Plan.PlanID)
	if unavailable.Status != "BLOCKED" || unavailable.Error == nil || unavailable.Error.Code != "EXECUTION_NODE_UNAVAILABLE" {
		t.Fatalf("unavailable commit=%#v", unavailable)
	}
	if _, err := os.Stat(filepath.Join(root, "ansible.cfg")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("unavailable node commit mutated project: %v", err)
	}
	app.reader = editorReaderStub{}
	committed := app.CommitEditPlan(started.Session.SessionID, latest.Plan.PlanID)
	if committed.Status != "COMMITTED" || app.activeSession != "" {
		t.Fatalf("committed=%#v", committed)
	}
	if _, err := os.Stat(filepath.Join(root, "inventory", "hosts.yml")); err != nil {
		t.Fatal(err)
	}
}

func TestAppReleasesExpiredSessionState(t *testing.T) {
	newExpired := func(t *testing.T) (*App, string) {
		t.Helper()
		app := NewApp(unavailableProjectReader{}, lifecycleStub{})
		session, err := app.sessions.Start("project-expiry", t.TempDir(), projectlifecycle.ClassificationEmpty, "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
		if err != nil {
			t.Fatal(err)
		}
		app.activeSession = session.SessionID
		app.editor = installer.NewBackend(nil)
		if !app.sessions.Discard(session.SessionID, app.editor) {
			t.Fatal("could not simulate transient-store expiry")
		}
		return app, session.SessionID
	}
	t.Run("close reconciles absent session", func(t *testing.T) {
		app, _ := newExpired(t)
		if result := app.CloseProject(); result.Status != "NO_PROJECT" || app.activeSession != "" || app.editor != nil {
			t.Fatalf("close did not release expired session: result=%#v", result)
		}
	})
	t.Run("discard is idempotent after expiry", func(t *testing.T) {
		app, sessionID := newExpired(t)
		if result := app.DiscardEditSession(sessionID); result.Status != "DISCARDED" || app.activeSession != "" || app.editor != nil {
			t.Fatalf("discard did not release expired session: result=%#v", result)
		}
	})
}

// TestUI01BRemoteOpenAcceptance exercises the same read-only backend wired to
// Wails. It is opt-in so normal unit tests never require a reachable node.
func TestUI01BRemoteOpenAcceptance(t *testing.T) {
	required := func(name string) string {
		t.Helper()
		value := os.Getenv(name)
		if value == "" {
			t.Skipf("set %s for the controlled UI-01B remote acceptance", name)
		}
		return value
	}
	bundle := required("UI01B_E2E_BUNDLE")
	verified, err := executionbundle.ValidateRoot(bundle)
	if err != nil {
		t.Fatal(err)
	}
	node := executionnode.Node{
		ID:            "ui-01b-acceptance",
		Address:       required("UI01B_E2E_ADDRESS"),
		User:          required("UI01B_E2E_USER"),
		Port:          22,
		CredentialRef: "runtime:ssh",
		HostKey:       executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: required("UI01B_E2E_KNOWN_HOSTS"), Fingerprint: required("UI01B_E2E_FINGERPRINT")},
	}
	reader := projectReader{
		transport: executionnode.OpenSSHTransport{Identity: desktopIdentity{required("UI01B_E2E_IDENTITY")}},
		node:      node,
		runtimeRelease: map[string]any{
			"bundleDigest":     verified.Digest,
			"coreVersion":      verified.Manifest.CoreVersion,
			"catalogDigest":    verified.Manifest.CatalogDigest,
			"planningProtocol": executionbundle.ProtocolVersion,
		},
	}
	result := NewApp(reader, projectlifecycle.NewService(map[string]string{})).OpenProject(required("UI01B_E2E_PROJECT"))
	if result.Status != "OPEN" || result.Snapshot == nil || result.Snapshot.Status != "PASS" {
		t.Fatalf("remote read-only open result=%+v error=%+v", result, result.Error)
	}
}

// TestUI01DRemoteFirstSaveAcceptance exercises the Wails-bound create,
// transient edit, authoritative remote review and explicit commit path. It is
// opt-in so normal unit tests never require a reachable Execution Node.
func TestUI01DRemoteFirstSaveAcceptance(t *testing.T) {
	required := func(name string) string {
		t.Helper()
		value := os.Getenv(name)
		if value == "" {
			t.Skipf("set %s for the controlled UI-01D remote acceptance", name)
		}
		return value
	}
	bundle := required("UI01D_E2E_BUNDLE")
	verified, err := executionbundle.ValidateRoot(bundle)
	if err != nil {
		t.Fatal(err)
	}
	node := executionnode.Node{
		ID:            "ui-01d-acceptance",
		Address:       required("UI01D_E2E_ADDRESS"),
		User:          required("UI01D_E2E_USER"),
		Port:          22,
		CredentialRef: "runtime:ssh",
		HostKey: executionnode.HostKeyPolicy{
			State: "TRUSTED", KnownHosts: required("UI01D_E2E_KNOWN_HOSTS"), Fingerprint: required("UI01D_E2E_FINGERPRINT"),
		},
	}
	reader := projectReader{
		transport: executionnode.OpenSSHTransport{Identity: desktopIdentity{required("UI01D_E2E_IDENTITY")}},
		node:      node,
		runtimeRelease: map[string]any{
			"bundleDigest":     verified.Digest,
			"coreVersion":      verified.Manifest.CoreVersion,
			"catalogDigest":    verified.Manifest.CatalogDigest,
			"planningProtocol": executionbundle.ProtocolVersion,
		},
	}
	app := NewApp(acceptanceReader{projectReader: reader, t: t}, projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle}), testApplicationConfig())
	root := os.Getenv("UI01D_E2E_PROJECT_ROOT")
	if root == "" {
		root = filepath.Join(t.TempDir(), "ui-01d-first-save")
	} else if _, statErr := os.Lstat(root); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("UI01D_E2E_PROJECT_ROOT must not exist: %v", statErr)
	}
	created := app.CreateProject(projectlifecycle.CreateProjectRequest{ProjectRoot: root, DisplayName: "UI-01D acceptance", CompatibilitySourceID: projectlifecycle.DefaultCompatibilitySourceID})
	if created.Status != "OPEN" || created.Classification != projectlifecycle.ClassificationEmpty {
		t.Fatalf("create result=%+v", created)
	}
	manifestBefore := fileDigest(t, filepath.Join(root, "project.yml"))
	started := app.StartEditSession()
	if started.Session == nil {
		t.Fatalf("start result=%+v", started)
	}
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("append result=%+v", appended)
	}
	reviewed := app.ReviewEditSession(started.Session.SessionID)
	if reviewed.Plan == nil || reviewed.Plan.Status != "READY" || !reviewed.Plan.CommitAllowed {
		if reviewed.Plan != nil {
			t.Fatalf("review status=%s plan=%+v", reviewed.Status, *reviewed.Plan)
		}
		t.Fatalf("review result=%+v", reviewed)
	}
	committed := app.CommitEditPlan(started.Session.SessionID, reviewed.Plan.PlanID)
	if committed.Commit == nil || committed.Status != "COMMITTED" {
		t.Fatalf("commit result=%+v", committed)
	}
	if after := fileDigest(t, filepath.Join(root, "project.yml")); after != manifestBefore {
		t.Fatalf("project.yml mutated: before=%s after=%s", manifestBefore, after)
	}
	for _, relative := range []string{"ansible.cfg", "inventory/hosts.yml", "inventory/group_vars/all/platform-installer.yml"} {
		if info, statErr := os.Stat(filepath.Join(root, filepath.FromSlash(relative))); statErr != nil || !info.Mode().IsRegular() {
			t.Fatalf("required first-save file %s: %v", relative, statErr)
		}
	}
	if _, statErr := os.Stat(filepath.Join(root, "inventory", "host_vars")); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("unexpected host_vars materialization: %v", statErr)
	}
	t.Logf("remote UI-01D first save PASS: plan=%s revision=%s", reviewed.Plan.PlanID, committed.Commit.NewProjectRevision)
}

func fileDigest(t *testing.T, path string) string {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return fmt.Sprintf("sha256:%x", sha256.Sum256(content))
}

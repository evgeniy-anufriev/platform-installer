package main

import (
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

type snapshotReaderStub struct {
	snapshot *coreadapter.Snapshot
	err      error
}

type verificationReader struct {
	calls   int
	status  string
	partial bool
	err     error
}

type verificationTransportStub struct{}

func (verificationTransportStub) BuildProjectSnapshot(ctx context.Context, node executionnode.Node, root string, release map[string]any) (*coreadapter.Snapshot, error) {
	result, err := (verificationTransportStub{}).BuildProjectVerificationSnapshot(ctx, node, root, release)
	return result.Snapshot, err
}

func (verificationTransportStub) BuildProjectVerificationSnapshot(_ context.Context, _ executionnode.Node, root string, _ map[string]any) (executionnode.ProjectVerificationSnapshot, error) {
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		return executionnode.ProjectVerificationSnapshot{}, err
	}
	return executionnode.ProjectVerificationSnapshot{Snapshot: &coreadapter.Snapshot{Status: "PASS", ProjectRevision: revision}, Runtime: executionnode.RuntimeEvidence{
		BundleDigest: "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", CoreVersion: "test-core",
		CatalogDigest: "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", Protocol: executionbundle.ProtocolVersion,
	}}, nil
}

type executionLifecycleStub struct {
	inspectCalls, prepareCalls int
	inspection                 executionnode.Inspection
	plan                       executionnode.Plan
	prepared                   executionnode.Result
}

func (s *executionLifecycleStub) InspectExecutionNode(context.Context, executionnode.Node) (executionnode.Inspection, error) {
	s.inspectCalls++
	return s.inspection, nil
}
func (s *executionLifecycleStub) PlanExecutionNodePreparation(context.Context, executionnode.Node, string) (executionnode.Plan, error) {
	return s.plan, nil
}
func (s *executionLifecycleStub) Prepare(context.Context, executionnode.Node, string, string) (executionnode.Result, error) {
	s.prepareCalls++
	return s.prepared, nil
}

func (r *verificationReader) BuildSnapshot(_ context.Context, root string) (*coreadapter.Snapshot, error) {
	r.calls++
	if r.err != nil {
		return nil, r.err
	}
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		return nil, err
	}
	return &coreadapter.Snapshot{Status: r.status, Partial: r.partial, ProjectRevision: revision,
		Findings: []map[string]any{{"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding", "code": "REFERENCE_IN_USE", "status": "BLOCKED", "safeMessage": "Host remains referenced"}}}, nil
}

func (*verificationReader) RuntimeIdentityDigest() string {
	return "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
}

func (r *verificationReader) BuildVerificationSnapshot(ctx context.Context, root string) (verificationSnapshot, error) {
	snapshot, err := r.BuildSnapshot(ctx, root)
	if err != nil {
		return verificationSnapshot{}, err
	}
	return verificationSnapshot{Snapshot: snapshot, NodeID: "qa-node", Runtime: executionnode.RuntimeEvidence{
		BundleDigest: "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
		CoreVersion:  "test-core", CatalogDigest: "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
		Protocol: "platform.installer/execution-runtime/v1alpha1"}}, nil
}

type editorReaderStub struct{}

func (editorReaderStub) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return nil, errors.New("not used")
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

func TestServerWriterBlockersHaveSafeMessages(t *testing.T) {
	for _, code := range []string{"INVALID_EDIT_COMMAND", "SERVER_METADATA_REQUIRED", "REFERENCE_IN_USE", "EDIT_SHADOWED", "PLAN_EXPIRED", "WRITE_FAILED"} {
		if message := projectErrorMessage(code); message == "" || message == projectErrorMessage("UNRELATED_UNKNOWN_ERROR") {
			t.Fatalf("code=%q message=%q", code, message)
		}
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
	result := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10"})
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
	result := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "scada", DesiredHostname: "node1.example.internal", Address: "192.0.2.10"})
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

func TestAppOpenRetriesWholeLocalObservationOnceOnRevisionChange(t *testing.T) {
	root := t.TempDir()
	project := &projectlifecycle.Project{ID: "project-0123456789abcdef", Name: "Empty"}
	app := NewApp(snapshotReaderStub{err: errors.New("snapshot must not be called")}, lifecycleStub{result: projectlifecycle.Result{Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: project}})
	revisions := []string{"sha256:one", "sha256:two", "sha256:three", "sha256:three"}
	app.projectRevision = func(string) (string, error) {
		value := revisions[0]
		revisions = revisions[1:]
		return value, nil
	}
	result := app.OpenProject(root)
	if result.Status != "OPEN" || result.Project != project || len(revisions) != 0 {
		t.Fatalf("result=%#v remaining=%v", result, revisions)
	}
}

func TestAppOpenRejectsSecondChangedLocalObservation(t *testing.T) {
	root := t.TempDir()
	project := &projectlifecycle.Project{ID: "project-0123456789abcdef", Name: "Empty"}
	app := NewApp(snapshotReaderStub{err: errors.New("snapshot must not be called")}, lifecycleStub{result: projectlifecycle.Result{Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: project}})
	revisions := []string{"sha256:one", "sha256:two", "sha256:three", "sha256:four"}
	app.projectRevision = func(string) (string, error) {
		value := revisions[0]
		revisions = revisions[1:]
		return value, nil
	}
	result := app.OpenProject(root)
	if result.Status != "ERROR" || result.Error == nil || result.Error.Code != "PROJECT_CHANGED" || len(revisions) != 0 {
		t.Fatalf("result=%#v remaining=%v", result, revisions)
	}
}

func TestRuntimeEvidenceRequiresExactPlanningProtocol(t *testing.T) {
	expected := map[string]any{"bundleDigest": "sha256:" + strings.Repeat("a", 64), "coreVersion": "1.0.0", "catalogDigest": "sha256:" + strings.Repeat("b", 64), "planningProtocol": "v1alpha1"}
	actual := executionnode.RuntimeEvidence{BundleDigest: expected["bundleDigest"].(string), CoreVersion: "1.0.0", CatalogDigest: expected["catalogDigest"].(string), Protocol: "v1alpha1"}
	if !runtimeEvidenceMatchesExpected(actual, expected) {
		t.Fatal("exact attested protocol was rejected")
	}
	for name, mutate := range map[string]func(*executionnode.RuntimeEvidence, map[string]any){
		"protocol mismatch":         func(value *executionnode.RuntimeEvidence, _ map[string]any) { value.Protocol = "v2alpha1" },
		"missing attested protocol": func(value *executionnode.RuntimeEvidence, _ map[string]any) { value.Protocol = "" },
		"missing expected protocol": func(_ *executionnode.RuntimeEvidence, value map[string]any) { delete(value, "planningProtocol") },
	} {
		t.Run(name, func(t *testing.T) {
			candidate, configured := actual, maps.Clone(expected)
			mutate(&candidate, configured)
			if runtimeEvidenceMatchesExpected(candidate, configured) {
				t.Fatal("protocol mismatch was accepted")
			}
		})
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
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("appended=%#v", appended)
	}
	plan := app.ReviewStructuralEditSession(started.Session.SessionID)
	if plan.Plan == nil || !plan.Plan.SaveAllowed {
		t.Fatalf("plan=%#v", plan)
	}
	latest := app.ReviewStructuralEditSession(started.Session.SessionID)
	if latest.Plan == nil || latest.Plan.PlanID == plan.Plan.PlanID {
		t.Fatalf("latest plan=%#v", latest)
	}
	stale := app.CommitStructuralEditPlan(started.Session.SessionID, plan.Plan.PlanID)
	if stale.Status != "BLOCKED" {
		t.Fatalf("stale commit=%#v", stale)
	}
	if _, err := os.Stat(filepath.Join(root, "ansible.cfg")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("stale plan mutated project: %v", err)
	}
	app.reader = editorReaderStub{}
	committed := app.CommitStructuralEditPlan(started.Session.SessionID, latest.Plan.PlanID)
	if committed.Status != "COMMITTED" || app.activeSession != "" {
		t.Fatalf("committed=%#v", committed)
	}
	if committed.Current == nil || committed.Current.Managed == nil || committed.Current.Verification.Status != "UNVERIFIED" {
		t.Fatalf("local save did not return managed state: %#v", committed)
	}
	if _, err := os.Stat(filepath.Join(root, "inventory", "hosts.yml")); err != nil {
		t.Fatal(err)
	}
}

func TestLocalSaveReopenVerifyAndStaleEvidence(t *testing.T) {
	root := t.TempDir()
	manifest := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services:\n    kafka:\n      definitionVersion: 1.0.0\n      digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	reader := &verificationReader{err: errors.New("CORE_MUST_NOT_BE_CALLED_BY_SAVE")}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa", Name: "Test"}
	app := NewApp(reader, projectlifecycle.NewService(nil), testApplicationConfig())
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: project, Verification: notVerified()}
	started := app.StartEditSession()
	if started.Session == nil {
		t.Fatalf("start=%#v", started)
	}
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10"})
	if appended.Session == nil {
		t.Fatalf("append=%#v", appended)
	}
	beforeRevision, err := installer.ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	reviewed := app.ReviewStructuralEditSession(started.Session.SessionID)
	if reviewed.Plan == nil || !reviewed.Plan.SaveAllowed || reader.calls != 0 {
		t.Fatalf("local review called Core or failed: review=%#v plan=%+v finding=%+v calls=%d", reviewed, reviewed.Plan, reviewed.Plan.Finding, reader.calls)
	}
	if current, _ := installer.ProjectRevision(root); current != beforeRevision {
		t.Fatalf("review changed canonical bytes: before=%s after=%s", beforeRevision, current)
	}
	saved := app.CommitStructuralEditPlan(started.Session.SessionID, reviewed.Plan.PlanID)
	if saved.Status != "COMMITTED" || reader.calls != 0 || saved.Current == nil || saved.Current.Managed.Servers["node1"].Address != "192.0.2.10" {
		t.Fatalf("local save=%#v calls=%d", saved, reader.calls)
	}
	if err := os.MkdirAll(filepath.Join(root, "inventory", "host_vars", "node1"), 0o755); err != nil {
		t.Fatal(err)
	}
	desired := string(managedHeaderForTest()) + "platform_desired_state:\n  endpointGroups:\n    edge: {address: {domain: edge.example.test, wildcard: true}}\n  serviceDeployments:\n    kafka-main: {serviceType: kafka, mode: single, endpointGroup: edge}\n"
	placement := string(managedHeaderForTest()) + "platform_deployments:\n  kafka-main:\n    members:\n      member-1: {roles: [broker]}\n  dns-main:\n    roles: [primary]\n"
	if err := os.WriteFile(filepath.Join(root, "inventory", "group_vars", "all", "platform-installer.yml"), []byte(desired), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml"), []byte(placement), 0o600); err != nil {
		t.Fatal(err)
	}
	if closed := app.CloseProject(); closed.Status != "NO_PROJECT" {
		t.Fatalf("close=%#v", closed)
	}
	originalRevision := app.projectRevision
	revisionCalls := 0
	app.projectRevision = func(projectRoot string) (string, error) {
		revisionCalls++
		value, err := originalRevision(projectRoot)
		if revisionCalls == 1 && err == nil {
			content, readErr := os.ReadFile(filepath.Join(projectRoot, "inventory", "host_vars", "node1", "platform-installer.yml"))
			if readErr != nil {
				return "", readErr
			}
			if writeErr := os.WriteFile(filepath.Join(projectRoot, "inventory", "host_vars", "node1", "platform-installer.yml"), append(content, []byte("# coherent retry\n")...), 0o600); writeErr != nil {
				return "", writeErr
			}
		}
		return value, err
	}
	reopened := app.OpenProject(root)
	if reopened.Status != "OPEN" || reopened.Managed == nil || reopened.Managed.Servers["node1"].DesiredHostname != "node1.example.internal" || len(reopened.Managed.MemberPlacements) != 1 || len(reopened.Managed.HostPlacements) != 1 || reader.calls != 0 || revisionCalls != 4 {
		t.Fatalf("local reopen=%#v calls=%d", reopened, reader.calls)
	}

	reader.err, reader.status = nil, "PASS"
	canonicalBefore := fileDigest(t, filepath.Join(root, "inventory", "hosts.yml"))
	verified := app.VerifyProject()
	if verified.Status != "VERIFIED" || reader.calls != 1 || verified.ProjectRevision != reopened.Managed.ProjectRevision || verified.Runtime == nil {
		t.Fatalf("verify=%#v calls=%d", verified, reader.calls)
	}
	if after := fileDigest(t, filepath.Join(root, "inventory", "hosts.yml")); after != canonicalBefore {
		t.Fatalf("Verify mutated canonical bytes: before=%s after=%s", canonicalBefore, after)
	}

	reader.status = "BLOCKED"
	invalid := app.VerifyProject()
	if invalid.Status != "INVALID" || len(invalid.Findings) != 1 || fileDigest(t, filepath.Join(root, "inventory", "hosts.yml")) != canonicalBefore {
		t.Fatalf("invalid verify=%#v", invalid)
	}
	reader.status = "PASS"
	if app.VerifyProject().Status != "VERIFIED" {
		t.Fatal("could not restore verified evidence")
	}
	update := app.StartEditSession()
	app.AppendEditCommand(update.Session.SessionID, installer.EditCommand{Operation: "UpdateServer", HostID: "node1", Address: "192.0.2.11"})
	updatePlan := app.ReviewStructuralEditSession(update.Session.SessionID)
	updated := app.CommitStructuralEditPlan(update.Session.SessionID, updatePlan.Plan.PlanID)
	if updated.Status != "COMMITTED" || updated.Current == nil || updated.Current.Verification.Status != "UNVERIFIED" || reader.calls != 3 {
		t.Fatalf("save did not stale evidence or called Core: %#v calls=%d", updated, reader.calls)
	}
}

func managedHeaderForTest() []byte {
	return []byte("# Managed by Platform Installer.\n# This is standard Ansible YAML; formatting may be normalized.\n")
}

func TestVerifyWithoutReadyNodeReturnsPrerequisiteWithoutPreparation(t *testing.T) {
	root := t.TempDir()
	projectFile := filepath.Join(root, "project.yml")
	if err := os.WriteFile(projectFile, []byte("name: unchanged\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	reader := &verificationReader{err: errors.New("EXECUTION_NODE_NOT_CONFIGURED")}
	app := NewApp(reader, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}, Verification: notVerified()}
	before := fileDigest(t, projectFile)
	result := app.VerifyProject()
	if result.Status != "UNVERIFIED" || result.Error == nil || result.Error.Code != "EXECUTION_NODE_READY_REQUIRED" || reader.calls != 1 {
		t.Fatalf("result=%#v calls=%d", result, reader.calls)
	}
	if after := fileDigest(t, projectFile); after != before {
		t.Fatalf("Verify prerequisite path mutated project: before=%s after=%s", before, after)
	}
}

func TestE5TrustedBindingAndPreparationContinuation(t *testing.T) {
	root := t.TempDir()
	projectFile := filepath.Join(root, "project.yml")
	if err := os.WriteFile(projectFile, []byte("name: unchanged\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	node := executionnode.Node{ID: "desktop-qa", Address: "192.0.2.10", User: "qa", Port: 22, CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: "known_hosts", Fingerprint: "SHA256:qa"}}
	stub := &executionLifecycleStub{
		inspection: executionnode.Inspection{State: executionnode.Ready},
		plan:       executionnode.Plan{ID: "prepare-plan", Digest: "sha256:plan", State: executionnode.PreparationRequired, ExpiresAt: time.Now().Add(time.Minute)},
		prepared:   executionnode.Result{State: executionnode.Ready},
	}
	reader := projectReader{transport: verificationTransportStub{}, node: node, runtimeRelease: map[string]any{
		"bundleDigest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "coreVersion": "test-core",
		"catalogDigest": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "planningProtocol": executionbundle.ProtocolVersion,
	}}
	app := NewApp(reader, lifecycleStub{}, WithExplicitExecutionNode(node.ID, node.Address), WithTrustedExecutionNodeBinding(executionNodeBinding{node: node, reader: reader, service: stub, bundleRoot: "bundle"}))
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}, Verification: notVerified()}
	app.bindExecutionLocked(root, app.current.Project, map[string]map[string]any{"node1": {"ansibleHost": "192.0.2.11"}})

	if readiness := app.CheckExecutionNode(); readiness.Status != "READY" || stub.inspectCalls != 1 {
		t.Fatalf("readiness=%#v inspectCalls=%d", readiness, stub.inspectCalls)
	}
	if _, err := app.SelectExecutionNode("node1"); err != nil {
		t.Fatal(err)
	}
	if readiness := app.CheckExecutionNode(); readiness.Error == nil || readiness.Error.Code != "BINDING_REQUIRED" {
		t.Fatalf("project candidate unexpectedly received binding: %#v", readiness)
	}
	app.execution.bind(root, app.current.Project.ID, map[string]map[string]any{"node1": {"ansibleHost": "192.0.2.11"}})
	preparation := app.PlanExecutionNodePreparation()
	if preparation.Status != "CONFIRMATION_REQUIRED" || preparation.PlanID != "prepare-plan" {
		t.Fatalf("preparation=%#v", preparation)
	}
	completed := app.PrepareExecutionNode(preparation.PlanID)
	if completed.Status != "PREPARED" || completed.Verification == nil || completed.Verification.Status != "VERIFIED" || stub.prepareCalls != 1 || stub.inspectCalls < 2 {
		t.Fatalf("completed=%#v prepareCalls=%d inspectCalls=%d", completed, stub.prepareCalls, stub.inspectCalls)
	}
}

func TestE5PreparationRejectsRevisionChange(t *testing.T) {
	root := t.TempDir()
	projectFile := filepath.Join(root, "project.yml")
	if err := os.WriteFile(projectFile, []byte("name: original\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	node := executionnode.Node{ID: "desktop-qa", Address: "192.0.2.10", User: "qa", Port: 22, CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: "known_hosts", Fingerprint: "SHA256:qa"}}
	stub := &executionLifecycleStub{inspection: executionnode.Inspection{State: executionnode.PreparationRequired}, plan: executionnode.Plan{ID: "prepare-plan", Digest: "sha256:plan", State: executionnode.PreparationRequired, ExpiresAt: time.Now().Add(time.Minute)}, prepared: executionnode.Result{State: executionnode.Ready}}
	reader := projectReader{transport: verificationTransportStub{}, node: node, runtimeRelease: map[string]any{"bundleDigest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd", "coreVersion": "test-core", "catalogDigest": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "planningProtocol": executionbundle.ProtocolVersion}}
	app := NewApp(reader, lifecycleStub{}, WithExplicitExecutionNode(node.ID, node.Address), WithTrustedExecutionNodeBinding(executionNodeBinding{node: node, reader: reader, service: stub, bundleRoot: "bundle"}))
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}, Verification: notVerified()}
	app.bindExecutionLocked(root, app.current.Project, nil)
	preparation := app.PlanExecutionNodePreparation()
	if preparation.Status != "CONFIRMATION_REQUIRED" {
		t.Fatalf("preparation=%#v", preparation)
	}
	if err := os.WriteFile(projectFile, []byte("name: changed\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	result := app.PrepareExecutionNode(preparation.PlanID)
	if result.Error == nil || result.Error.Code != "PROJECT_REVISION_CHANGED" || stub.prepareCalls != 0 {
		t.Fatalf("result=%#v prepareCalls=%d", result, stub.prepareCalls)
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

// TestUI01E2RemoteServerCRUDAcceptance exercises the Wails-bound first save
// and subsequent server CRUD through authoritative remote review and explicit
// commits. It is opt-in so normal unit tests never require a reachable
// Execution Node.
func TestUI01E2RemoteServerCRUDAcceptance(t *testing.T) {
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
	app := NewApp(reader, projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle}), testApplicationConfig())
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
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("append result=%+v", appended)
	}
	reviewed := app.ReviewStructuralEditSession(started.Session.SessionID)
	if reviewed.Plan == nil || reviewed.Plan.Status != "READY" || !reviewed.Plan.SaveAllowed {
		if reviewed.Plan != nil {
			t.Fatalf("review status=%s plan=%+v", reviewed.Status, *reviewed.Plan)
		}
		t.Fatalf("review result=%+v", reviewed)
	}
	committed := app.CommitStructuralEditPlan(started.Session.SessionID, reviewed.Plan.PlanID)
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
	second := app.StartEditSession()
	if second.Session == nil {
		t.Fatalf("start second session result=%+v", second)
	}
	added := app.AppendEditCommand(second.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node2", ServerType: "app", DesiredHostname: "node2.example.internal", Address: "192.0.2.11", SSHPort: 22})
	if added.Session == nil || added.Session.CommandCount != 1 {
		t.Fatalf("append second server result=%+v", added)
	}
	secondReview := app.ReviewStructuralEditSession(second.Session.SessionID)
	if secondReview.Plan == nil || secondReview.Plan.Status != "READY" || !secondReview.Plan.SaveAllowed {
		t.Fatalf("second review result=%+v", secondReview)
	}
	if secondCommit := app.CommitStructuralEditPlan(second.Session.SessionID, secondReview.Plan.PlanID); secondCommit.Status != "COMMITTED" {
		t.Fatalf("second commit result=%+v", secondCommit)
	}

	updated := app.StartEditSession()
	if updated.Session == nil {
		t.Fatalf("start update session result=%+v", updated)
	}
	updatedCommand := app.AppendEditCommand(updated.Session.SessionID, installer.EditCommand{Operation: "UpdateServer", HostID: "node1", Address: "192.0.2.12", ClearSSHPort: true})
	if updatedCommand.Session == nil || updatedCommand.Session.CommandCount != 1 {
		t.Fatalf("append update result=%+v", updatedCommand)
	}
	updateReview := app.ReviewStructuralEditSession(updated.Session.SessionID)
	if updateReview.Plan == nil || updateReview.Plan.Status != "READY" || !updateReview.Plan.SaveAllowed {
		t.Fatalf("update review result=%+v", updateReview)
	}
	if updateCommit := app.CommitStructuralEditPlan(updated.Session.SessionID, updateReview.Plan.PlanID); updateCommit.Status != "COMMITTED" {
		t.Fatalf("update commit result=%+v", updateCommit)
	}

	deleted := app.StartEditSession()
	if deleted.Session == nil {
		t.Fatalf("start delete session result=%+v", deleted)
	}
	deletedCommand := app.AppendEditCommand(deleted.Session.SessionID, installer.EditCommand{Operation: "DeleteServer", HostID: "node2"})
	if deletedCommand.Session == nil || deletedCommand.Session.CommandCount != 1 {
		t.Fatalf("append delete result=%+v", deletedCommand)
	}
	deleteReview := app.ReviewStructuralEditSession(deleted.Session.SessionID)
	if deleteReview.Plan == nil || deleteReview.Plan.Status != "READY" || !deleteReview.Plan.SaveAllowed {
		t.Fatalf("delete review result=%+v", deleteReview)
	}
	if deleteCommit := app.CommitStructuralEditPlan(deleted.Session.SessionID, deleteReview.Plan.PlanID); deleteCommit.Status != "COMMITTED" {
		t.Fatalf("delete commit result=%+v", deleteCommit)
	}
	contentBytes, readErr := os.ReadFile(filepath.Join(root, "inventory", "hosts.yml"))
	if readErr != nil {
		t.Fatal(readErr)
	}
	content := string(contentBytes)
	if strings.Contains(content, "node2") || strings.Contains(content, "ansible_port") || !strings.Contains(content, "192.0.2.12") {
		t.Fatalf("unexpected final inventory: %s", content)
	}
	t.Logf("remote UI-01E2 server CRUD PASS: first-save-plan=%s revision=%s", reviewed.Plan.PlanID, committed.Commit.NewProjectRevision)
}

func fileDigest(t *testing.T, path string) string {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return fmt.Sprintf("sha256:%x", sha256.Sum256(content))
}

func TestSessionCredentialIsProjectBoundAndDoesNotMutateProject(t *testing.T) {
	root := t.TempDir()
	projectFile := filepath.Join(root, "project.yml")
	if err := os.WriteFile(projectFile, []byte("name: safe\n"), 0600); err != nil {
		t.Fatal(err)
	}
	before := fileDigest(t, projectFile)
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
	status, err := app.SetSessionCredential(runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "not-in-result", ElevationMode: runtimesecret.ElevationSudo, ElevationPassword: "also-not-in-result"})
	if err != nil || status.Status != runtimesecret.StatusPresent || status.Username != "installer" || status.SudoPasswordStatus != runtimesecret.SudoPresent {
		t.Fatalf("set safe status=%#v err=%v", status, err)
	}
	if strings.Contains(fmt.Sprintf("%#v", status), "not-in-result") {
		t.Fatalf("credential status disclosed secret: %#v", status)
	}
	if after := fileDigest(t, projectFile); after != before {
		t.Fatalf("credential operation mutated project: before=%s after=%s", before, after)
	}
	closed := app.CloseProject()
	if closed.Status != "NO_PROJECT" {
		t.Fatalf("close=%#v", closed)
	}
	if _, err := app.GetSessionCredentialStatus(); err == nil || err.Error() != "PROJECT_NOT_OPEN" {
		t.Fatalf("closed status error=%v", err)
	}
}

func TestFailedOpenPreservesSessionCredential(t *testing.T) {
	root := t.TempDir()
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}
	app := NewApp(unavailableProjectReader{}, lifecycleStub{err: errors.New("PROJECT_PATH_INVALID")})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: project}
	if _, err := app.SetSessionCredential(runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "write-only", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if result := app.OpenProject(t.TempDir()); result.Status != "ERROR" {
		t.Fatalf("open=%#v", result)
	}
	if status, err := app.GetSessionCredentialStatus(); err != nil || status.Status != runtimesecret.StatusPresent {
		t.Fatalf("failed open cleared credential: %#v err=%v", status, err)
	}
	app.clearCredentialForReplacementLocked(t.TempDir(), &projectlifecycle.Project{ID: "project-bbbbbbbbbbbbbbbb"})
	if status, err := app.GetSessionCredentialStatus(); err != nil || status.Status != runtimesecret.StatusMissing {
		t.Fatalf("replacement did not clear credential: %#v err=%v", status, err)
	}
}

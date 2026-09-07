package installer

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"gopkg.in/yaml.v3"
	"platform-installer/internal/coreadapter"
)

type fakeAdapter struct {
	shadow bool
	fail   bool
	failAt int
	calls  int
}

func (adapter *fakeAdapter) BuildSnapshot(_ context.Context, root string, owned []string) (*coreadapter.Snapshot, error) {
	adapter.calls++
	if adapter.fail || (adapter.failAt > 0 && adapter.calls == adapter.failAt) {
		return nil, errors.New("injected core failure")
	}
	documents, revision, err := collectProjectDocuments(root)
	if err != nil {
		return nil, err
	}
	ownedSet := make(map[string]bool)
	for _, path := range owned {
		ownedSet[path] = true
	}
	resultDocuments := make([]coreadapter.Document, 0, len(documents))
	for _, document := range documents {
		ownership := "USER_OWNED_READ_ONLY"
		if document.LogicalPath == generatedDocument {
			ownership = "GENERATED_READ_ONLY"
		} else if ownedSet[document.LogicalPath] {
			ownership = "INSTALLER_OWNED"
		}
		resultDocuments = append(resultDocuments, coreadapter.Document{LogicalPath: document.LogicalPath,
			Digest: document.Digest, Ownership: ownership, RevisionIncluded: document.LogicalPath != generatedDocument})
	}
	content, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(desiredDocument)))
	if err != nil {
		return nil, err
	}
	var desiredDocumentValue map[string]any
	if err := yaml.Unmarshal(content, &desiredDocumentValue); err != nil {
		return nil, err
	}
	state := asMap(desiredDocumentValue["platform_desired_state"])
	deployments := make(map[string]map[string]any)
	for id, raw := range asMap(state["serviceDeployments"]) {
		deployments[id] = asMap(raw)
	}
	settings := map[string]any{
		"port": map[string]any{}, "tlsProfile": map[string]any{}, "zone": map[string]any{},
		"defaultTtl": map[string]any{}, "dnsServerRef": map[string]any{}, "quorumMode": map[string]any{},
		"runtimePathNamespace": map[string]any{}, "haproxyHealthTracking": map[string]any{}, "advancedConfig": map[string]any{},
		"adminSuperuser": map[string]any{},
	}
	catalog := make(map[string]map[string]any)
	for _, serviceType := range []string{"bind", "dns-client", "keepalived", "haproxy", "kafka", "postgresql"} {
		modes := map[string]string{"bind": "authoritative-primary-secondary", "dns-client": "host-resolver",
			"keepalived": "vrrp-unicast", "haproxy": "https-host-routing", "kafka": "kraft-distributed",
			"postgresql": "pg_auto_failover"}
		catalog[serviceType] = map[string]any{"modes": []any{modes[serviceType]},
			"configuration": map[string]any{"settings": settings}}
	}
	effectiveServices := make(map[string]any)
	for id, item := range deployments {
		configuration := make(map[string]any)
		for key, value := range asMap(item["configuration"]) {
			configuration[key] = map[string]any{"value": value, "source": "DEPLOYMENT_OVERRIDE"}
		}
		if item["serviceType"] == "postgresql" && configuration["port"] == nil {
			configuration["port"] = map[string]any{"value": 5432, "source": "ROLE_DEFAULT"}
		}
		if adapter.shadow && id == "postgres-ha" && configuration["port"] != nil {
			configuration["port"] = map[string]any{"value": 5432, "source": "DEPLOYMENT_OVERRIDE"}
		}
		effectiveServices[id] = map[string]any{"configuration": configuration}
	}
	hosts := make(map[string]map[string]any)
	for _, id := range []string{"node1", "node2", "node3"} {
		path := filepath.Join(root, filepath.FromSlash(managedHostDocument(id)))
		hostContent, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil, readErr
		}
		var hostDocument map[string]any
		if err := yaml.Unmarshal(hostContent, &hostDocument); err != nil {
			return nil, err
		}
		hosts[id] = map[string]any{"platformDeployments": hostDocument["platform_deployments"]}
	}
	return &coreadapter.Snapshot{Status: "PASS", ProjectRevision: revision,
		SnapshotFingerprint: digestBytes([]byte(revision)), Documents: resultDocuments,
		Hosts: hosts, ServiceCatalog: catalog, ServiceDeployments: deployments,
		EffectiveConfiguration: map[string]any{"services": effectiveServices},
		EndpointGroups:         asMap(state["endpointGroups"]), Topology: map[string]any{"placementsByHost": hosts},
		Endpoints: map[string]any{}, Integrations: map[string]any{}, PKI: map[string]any{},
		Validation: map[string]any{"status": "PASS"}}, nil
}

func testProject(t *testing.T) (string, func()) {
	t.Helper()
	repository := os.Getenv("PLATFORM_INSTALLER_REPOSITORY")
	if repository == "" {
		current, err := os.Getwd()
		if err != nil {
			t.Fatal(err)
		}
		for {
			if _, err := os.Stat(filepath.Join(current, "go.mod")); err == nil {
				repository = current
				break
			}
			parent := filepath.Dir(current)
			if parent == current {
				t.Fatal("repository root with go.mod was not found")
			}
			current = parent
		}
	}
	root, cleanup, err := copyProject(filepath.Join(repository, "examples", "valid", "ui-project-snapshot"))
	if err != nil {
		t.Fatal(err)
	}
	return root, cleanup
}

func revisionForTest(t *testing.T, adapter coreadapter.Adapter, root string) string {
	t.Helper()
	owned, err := discoverOwnedPaths(root)
	if err != nil {
		t.Fatal(err)
	}
	snapshot, err := adapter.BuildSnapshot(context.Background(), root, owned)
	if err != nil {
		t.Fatal(err)
	}
	return snapshot.ProjectRevision
}

func command(revision, operation string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersion, Kind: "EditCommand",
		BaseProjectRevision: revision, Operation: operation}
}

func findingCode(result EditCommitResult) string {
	if result.Finding == nil {
		return ""
	}
	return result.Finding.Code
}

func TestPlanCommitRemoveOverrideAndNoChange(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{}
	backend := NewBackend(adapter)
	revision := revisionForTest(t, adapter, root)
	desiredPath := filepath.Join(root, filepath.FromSlash(desiredDocument))
	before, _ := os.ReadFile(desiredPath)
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	plan, err := backend.PlanEdit(context.Background(), root, set)
	if err != nil || plan.Status != "READY" || !plan.CommitAllowed || len(plan.AffectedDocuments) != 1 {
		t.Fatalf("unexpected plan: %#v, %v", plan, err)
	}
	afterPlan, _ := os.ReadFile(desiredPath)
	if string(before) != string(afterPlan) {
		t.Fatal("planning changed canonical bytes")
	}
	result := backend.CommitEditPlan(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" || result.NewProjectRevision == revision || !result.ApplyRequired {
		t.Fatalf("unexpected commit: %#v", result)
	}
	remove := command(result.NewProjectRevision, "RemoveServiceConfigurationOverride")
	remove.DeploymentID, remove.Setting = "postgres-ha", "port"
	removePlan, _ := backend.PlanEdit(context.Background(), root, remove)
	removed := backend.CommitEditPlan(context.Background(), removePlan.PlanID)
	if removed.Status != "COMMITTED" {
		t.Fatalf("remove failed: %#v", removed)
	}
	repeat := command(removed.NewProjectRevision, "RemoveServiceConfigurationOverride")
	repeat.DeploymentID, repeat.Setting = "postgres-ha", "port"
	noChange, _ := backend.PlanEdit(context.Background(), root, repeat)
	if noChange.Status != "NO_CHANGE" || noChange.PlanID != "" {
		t.Fatalf("expected NO_CHANGE: %#v", noChange)
	}
}

func TestCommandValidationSecretsAndUserOwnedProtection(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{}
	backend := NewBackend(adapter)
	revision := revisionForTest(t, adapter, root)
	invalid := command(revision, "RawYAML")
	plan, _ := backend.PlanEdit(context.Background(), root, invalid)
	if plan.Validation.Findings[0].Code != "INVALID_EDIT_COMMAND" {
		t.Fatalf("unexpected finding: %#v", plan)
	}
	secret := command(revision, "SetServiceConfigurationValue")
	secret.DeploymentID, secret.Setting = "postgres-ha", "advancedConfig"
	secret.Value = map[string]any{"password": "plain"}
	plan, _ = backend.PlanEdit(context.Background(), root, secret)
	if plan.Validation.Findings[0].Code != "SECRET_VALUE_NOT_ALLOWED" {
		t.Fatalf("secret was not blocked: %#v", plan)
	}
	reference := command(revision, "SetServiceConfigurationValue")
	reference.DeploymentID, reference.Setting = "postgres-ha", "adminSuperuser"
	reference.Value = map[string]any{"username": "admin", "passwordSecretRef": "runtime:postgres-admin"}
	plan, _ = backend.PlanEdit(context.Background(), root, reference)
	if plan.Status != "READY" {
		t.Fatalf("safe credential reference was blocked: %#v", plan)
	}
	backend.DiscardEditPlan(plan.PlanID)
	path := filepath.Join(root, filepath.FromSlash(desiredDocument))
	original, _ := os.ReadFile(path)
	userOwned := strings.TrimPrefix(string(original), string(managedHeader))
	if err := os.WriteFile(path, []byte("# user comment\n"+userOwned), 0o600); err != nil {
		t.Fatal(err)
	}
	revision = revisionForTest(t, adapter, root)
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	plan, _ = backend.PlanEdit(context.Background(), root, set)
	if plan.Validation.Findings[0].Code != "WRITE_NOT_ALLOWED" {
		t.Fatalf("user-owned document was not blocked: %#v", plan)
	}
	preserved, _ := os.ReadFile(path)
	if string(preserved) != "# user comment\n"+userOwned {
		t.Fatal("user-owned bytes changed")
	}
}

func TestPlanStoreExpiryDiscardAndTampering(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{}
	store := NewMemoryPlanStore(time.Minute)
	backend := NewBackend(adapter, WithPlanStore(store))
	revision := revisionForTest(t, adapter, root)
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	plan, _ := backend.PlanEdit(context.Background(), root, set)
	plan.AffectedDocuments[0].LogicalPath = "../outside.yml"
	plan.AffectedDocuments[0].AfterDigest = "tampered"
	if result := backend.CommitEditPlan(context.Background(), plan.PlanID); result.Status != "COMMITTED" {
		t.Fatalf("client plan mutation affected commit: %#v", result)
	}
	revision = revisionForTest(t, adapter, root)
	set.BaseProjectRevision, set.Value = revision, 55433
	plan, _ = backend.PlanEdit(context.Background(), root, set)
	if !backend.DiscardEditPlan(plan.PlanID).Discarded {
		t.Fatal("plan was not discarded")
	}
	if code := findingCode(backend.CommitEditPlan(context.Background(), plan.PlanID)); code != "PLAN_EXPIRED" {
		t.Fatalf("discarded plan accepted: %s", code)
	}
	expiring := NewMemoryPlanStore(time.Nanosecond)
	baseTime := time.Now()
	expiring.now = func() time.Time { return baseTime }
	expiredBackend := NewBackend(adapter, WithPlanStore(expiring))
	expiredBackend.now = func() time.Time { return baseTime }
	set.BaseProjectRevision = revision
	plan, _ = expiredBackend.PlanEdit(context.Background(), root, set)
	expiring.now = func() time.Time { return baseTime.Add(time.Second) }
	if code := findingCode(expiredBackend.CommitEditPlan(context.Background(), plan.PlanID)); code != "PLAN_EXPIRED" {
		t.Fatalf("expired plan accepted: %s", code)
	}
}

func TestProjectAndDocumentConflictGuards(t *testing.T) {
	t.Run("unrelated project edit", func(t *testing.T) {
		root, cleanup := testProject(t)
		defer cleanup()
		adapter := &fakeAdapter{}
		backend := NewBackend(adapter)
		revision := revisionForTest(t, adapter, root)
		set := command(revision, "SetServiceConfigurationValue")
		set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
		plan, _ := backend.PlanEdit(context.Background(), root, set)
		path := filepath.Join(root, "inventory", "group_vars", "all", "platform.yml")
		original, _ := os.ReadFile(path)
		_ = os.WriteFile(path, append(original, []byte("# external\n")...), 0o600)
		if code := findingCode(backend.CommitEditPlan(context.Background(), plan.PlanID)); code != "PROJECT_CHANGED" {
			t.Fatalf("expected PROJECT_CHANGED, got %s", code)
		}
	})
	t.Run("affected document edit", func(t *testing.T) {
		root, cleanup := testProject(t)
		defer cleanup()
		adapter := &fakeAdapter{}
		backend := NewBackend(adapter)
		revision := revisionForTest(t, adapter, root)
		set := command(revision, "SetServiceConfigurationValue")
		set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
		plan, _ := backend.PlanEdit(context.Background(), root, set)
		path := filepath.Join(root, filepath.FromSlash(desiredDocument))
		original, _ := os.ReadFile(path)
		_ = os.WriteFile(path, append(original, []byte("# external\n")...), 0o600)
		if code := findingCode(backend.CommitEditPlan(context.Background(), plan.PlanID)); code != "DOCUMENT_CHANGED" {
			t.Fatalf("expected DOCUMENT_CHANGED, got %s", code)
		}
	})
}

func TestShadowingPathSymlinkAndProjectLock(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{shadow: true}
	backend := NewBackend(adapter)
	revision := revisionForTest(t, adapter, root)
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	plan, _ := backend.PlanEdit(context.Background(), root, set)
	if plan.Validation.Findings[0].Code != "EDIT_SHADOWED" {
		t.Fatalf("shadowed edit accepted: %#v", plan)
	}
	if _, err := safeProjectPath(root, "../outside.yml", true); err == nil {
		t.Fatal("path traversal accepted")
	}
	if runtime.GOOS != "windows" {
		hostDir := filepath.Join(root, "inventory", "host_vars", "node1")
		if err := os.Rename(hostDir, hostDir+"-real"); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(hostDir+"-real", hostDir); err != nil {
			t.Fatal(err)
		}
		if _, err := safeProjectPath(root, managedHostDocument("node1"), false); err == nil {
			t.Fatal("symlink escape accepted")
		}
		if err := os.Remove(hostDir); err != nil {
			t.Fatal(err)
		}
		if err := os.Rename(hostDir+"-real", hostDir); err != nil {
			t.Fatal(err)
		}
	}
	releaseLock, err := acquireWriterLock(t.Context(), root, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer releaseLock()
	backend.lockWait = 10 * time.Millisecond
	adapter.shadow = false
	revision = revisionForTest(t, adapter, root)
	set.BaseProjectRevision = revision
	plan, _ = backend.PlanEdit(context.Background(), root, set)
	if plan.PlanID != "" && findingCode(backend.CommitEditPlan(context.Background(), plan.PlanID)) != "PROJECT_LOCKED" {
		t.Fatal("project lock was not enforced")
	}
}

func TestDeterministicYAMLSpecialValues(t *testing.T) {
	values := []any{"yes", "no", "on", "off", "null", "00123", "1e3", "true", "false",
		"a:b", "a # b", "'quoted'", "Кириллица", true, false, nil, 123, 1.5}
	first, err := deterministicYAML(map[string]any{"values": values, "advancedConfig": map[string]any{"z": 1, "a": 2}})
	if err != nil {
		t.Fatal(err)
	}
	second, _ := deterministicYAML(map[string]any{"advancedConfig": map[string]any{"a": 2, "z": 1}, "values": values})
	if string(first) != string(second) || !strings.HasSuffix(string(first), "\n") {
		t.Fatal("YAML serialization is not deterministic")
	}
	parsed, err := parseManagedYAML(first)
	if err != nil || !semanticEqual(parsed["values"], values) {
		t.Fatalf("special values changed: %#v, %v", parsed["values"], err)
	}
}

func TestMultiDocumentTransactionSuccessAndRollback(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{}
	revision := revisionForTest(t, adapter, root)
	batch := command(revision, "Batch")
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	placement := command(revision, "SetPlacementProperty")
	placement.HostID, placement.DeploymentID, placement.Property, placement.Value = "node1", "keepalived-a", "priority", 140
	batch.Commands = []EditCommand{set, placement}
	backend := NewBackend(adapter)
	plan, _ := backend.PlanEdit(context.Background(), root, batch)
	if len(plan.AffectedDocuments) != 2 {
		t.Fatalf("expected two documents: %#v", plan)
	}
	before := make(map[string][]byte)
	for _, document := range plan.AffectedDocuments {
		before[document.LogicalPath], _ = os.ReadFile(filepath.Join(root, filepath.FromSlash(document.LogicalPath)))
	}
	calls := 0
	failing := NewBackend(adapter, WithPlanStore(backend.plans), withReplace(func(source, target string) error {
		calls++
		if calls == 2 {
			return errors.New("injected replacement failure")
		}
		return atomicReplace(source, target)
	}))
	result := failing.CommitEditPlan(context.Background(), plan.PlanID)
	if findingCode(result) != "WRITE_FAILED" {
		t.Fatalf("unexpected rollback result: %#v", result)
	}
	for logical, original := range before {
		current, _ := os.ReadFile(filepath.Join(root, filepath.FromSlash(logical)))
		if string(current) != string(original) {
			t.Fatalf("rollback did not restore %s", logical)
		}
	}
	entries, _ := os.ReadDir(runtimePath(root, "edit-transactions"))
	if len(entries) != 0 {
		t.Fatalf("transaction artifacts remain: %#v", entries)
	}
	secondRelease, err := acquireWriterLock(t.Context(), root, 0)
	if err != nil {
		t.Fatalf("writer lock was not released: %v", err)
	}
	secondRelease()
	result = backend.CommitEditPlan(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" {
		t.Fatalf("transaction retry failed: %#v", result)
	}
}

func TestGenericEndpointHAProxyPlacementAndDeploymentEdits(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{}
	backend := NewBackend(adapter)
	commit := func(edit EditCommand) EditCommitResult {
		edit.APIVersion, edit.Kind = EditCommandAPIVersion, "EditCommand"
		edit.BaseProjectRevision = revisionForTest(t, adapter, root)
		plan, _ := backend.PlanEdit(context.Background(), root, edit)
		if plan.Status != "READY" {
			t.Fatalf("plan blocked: %#v", plan)
		}
		result := backend.CommitEditPlan(context.Background(), plan.PlanID)
		if result.Status != "COMMITTED" {
			t.Fatalf("commit blocked: %#v", result)
		}
		return result
	}
	commit(EditCommand{Operation: "SetPlacementProperty", HostID: "node1", DeploymentID: "keepalived-a", Property: "priority", Value: 140})
	commit(EditCommand{Operation: "CreateEndpointGroup", EndpointGroupID: "unused",
		EndpointGroup: map[string]any{"address": map[string]any{"domain": "unused.example.test", "wildcard": false}}})
	commit(EditCommand{Operation: "UpdateEndpointGroup", EndpointGroupID: "unused",
		EndpointGroup: map[string]any{"address": map[string]any{"domain": "changed.example.test", "wildcard": false}}})
	commit(EditCommand{Operation: "DeleteEndpointGroup", EndpointGroupID: "unused"})
	commit(EditCommand{Operation: "ClearHAProxyIntegration", DeploymentID: "postgres-ha"})
	commit(EditCommand{Operation: "SetHAProxyIntegration", DeploymentID: "postgres-ha", HAProxyDeploymentID: "haproxy-a",
		Backend: map[string]any{"balance": "leastconn", "check": true, "fall": 3, "rise": 2, "ssl": true, "sslVerify": "required"}})
	commit(EditCommand{Operation: "ClearServiceEndpointGroup", DeploymentID: "postgres-ha"})
	commit(EditCommand{Operation: "SetServiceEndpointGroup", DeploymentID: "postgres-ha", EndpointGroupID: "asutp-a"})
	createBatch := EditCommand{Operation: "Batch", Commands: []EditCommand{
		{Operation: "CreateServiceDeployment", DeploymentID: "dns-client-extra",
			Deployment: map[string]any{"serviceType": "dns-client", "mode": "host-resolver", "configuration": map[string]any{"dnsServerRef": "bind-main"}}},
		{Operation: "AssignServiceToHost", HostID: "node1", DeploymentID: "dns-client-extra", Placement: map[string]any{}},
	}}
	// Assign in the same batch is intentionally rejected until the staged deployment exists in the base snapshot.
	commit(createBatch)
	deleteResult := commit(EditCommand{Operation: "Batch", Commands: []EditCommand{
		{Operation: "RemoveServiceFromHost", HostID: "node1", DeploymentID: "dns-client-extra"},
		{Operation: "DeleteServiceDeployment", DeploymentID: "dns-client-extra"},
	}})
	if deleteResult.Status != "COMMITTED" {
		t.Fatal("deployment delete failed")
	}
}

func TestRecoverInterruptedTransaction(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	path := filepath.Join(root, filepath.FromSlash(desiredDocument))
	original, _ := os.ReadFile(path)
	_, beforeDigest, beforeIdentity, err := inspectWriterFile(path)
	if err != nil {
		t.Fatal(err)
	}
	beforeSecurity := mustCaptureCanonicalSecurity(t, path)
	identifier := strings.Repeat("a", 32)
	directory := runtimePath(root, "edit-transactions", identifier)
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "000.before"), original, 0o600); err != nil {
		t.Fatal(err)
	}
	partial := []byte("partial")
	temporaryPath := filepath.Join(filepath.Dir(path), ".crash-output")
	if err := os.WriteFile(temporaryPath, partial, 0o600); err != nil {
		t.Fatal(err)
	}
	mustApplyCanonicalSecurity(t, temporaryPath, beforeSecurity)
	_, _, outputIdentity, err := inspectWriterFile(temporaryPath)
	if err != nil {
		t.Fatal(err)
	}
	if err := atomicReplace(temporaryPath, path); err != nil {
		t.Fatal(err)
	}
	journal := transactionJournal{TransactionID: identifier, Phase: "REPLACING", Replacing: 0, Published: 0,
		Documents: []transactionDocument{{LogicalPath: desiredDocument, Existed: true, Mode: 0o600,
			Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
			BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity, AfterDigest: digestBytes(partial), OutputIdentity: outputIdentity}}}
	content, _ := json.Marshal(journal)
	if err := os.WriteFile(filepath.Join(directory, "journal.json"), content, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatal(err)
	}
	recovered, _ := os.ReadFile(path)
	if string(recovered) != string(original) {
		t.Fatal("crash recovery did not restore exact bytes")
	}
}

func TestCommittedRefreshFailureReportsCommittedState(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	adapter := &fakeAdapter{failAt: 4}
	backend := NewBackend(adapter)
	revision := revisionForTest(t, adapter, root)
	set := command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	plan, _ := backend.PlanEdit(context.Background(), root, set)
	result := backend.CommitEditPlan(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED_REFRESH_FAILED" || !result.Changed || result.NewProjectRevision == revision {
		t.Fatalf("refresh failure lost commit boundary: %#v", result)
	}
	if code := findingCode(backend.CommitEditPlan(context.Background(), plan.PlanID)); code != "PLAN_EXPIRED" {
		t.Fatalf("committed plan was retained: %s", code)
	}
}

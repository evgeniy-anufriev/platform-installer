package installer

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"gopkg.in/yaml.v3"
	"platform-installer/internal/coreadapter"
)

type firstWriteAdapter struct{ calls int }

func (a *firstWriteAdapter) BuildSnapshot(_ context.Context, root string, owned []string) (*coreadapter.Snapshot, error) {
	a.calls++
	content, err := os.ReadFile(filepath.Join(root, "inventory", "hosts.yml"))
	if err != nil {
		return nil, err
	}
	var inventory map[string]any
	if err := yaml.Unmarshal(content, &inventory); err != nil {
		return nil, err
	}
	hostValues := asMap(asMap(inventory["all"])["hosts"])
	hosts := make(map[string]map[string]any, len(hostValues))
	for id, raw := range hostValues {
		hosts[id] = asMap(raw)
		if platformHost := asMap(hosts[id]["platform_host"]); platformHost != nil {
			hosts[id]["type"] = platformHost["type"]
		}
	}
	documents, revision, err := collectProjectDocuments(root)
	if err != nil {
		return nil, err
	}
	resultDocuments := make([]coreadapter.Document, 0, len(documents))
	for _, item := range documents {
		ownership := "USER_OWNED_READ_ONLY"
		for _, logical := range owned {
			if logical == item.LogicalPath {
				ownership = "INSTALLER_OWNED"
			}
		}
		resultDocuments = append(resultDocuments, coreadapter.Document{LogicalPath: item.LogicalPath, Digest: item.Digest, Ownership: ownership, RevisionIncluded: true})
	}
	return &coreadapter.Snapshot{Status: "PASS", ProjectRevision: revision, SnapshotFingerprint: digestBytes([]byte(revision)),
		Documents: resultDocuments, Hosts: hosts, ServiceCatalog: map[string]map[string]any{}, ServiceDeployments: map[string]map[string]any{},
		EffectiveConfiguration: map[string]any{}, EndpointGroups: map[string]any{}, Topology: map[string]any{}, Endpoints: map[string]any{}, Integrations: map[string]any{}, PKI: map[string]any{}}, nil
}

func emptyManagedProject(t *testing.T) (string, string) {
	t.Helper()
	root := t.TempDir()
	manifest := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services:\n    kafka:\n      definitionVersion: 1.0.0\n      digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	_, revision, err := collectProjectDocuments(root)
	if err != nil {
		t.Fatal(err)
	}
	return root, revision
}

func TestFirstSaveSessionCreatesCompleteCandidateAndCommitsOnce(t *testing.T) {
	root, revision := emptyManagedProject(t)
	adapter := &firstWriteAdapter{}
	backend := NewBackend(adapter, WithServerTypes([]string{"infra"}))
	sessions := NewEditSessionStore()
	session, err := sessions.Start("project-aaaaaaaaaaaaaaaa", root, "EMPTY_MANAGED_PROJECT", revision)
	if err != nil {
		t.Fatal(err)
	}
	command := EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", Address: "192.0.2.10"}
	if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
		t.Fatal(err)
	}
	plan, err := sessions.Review(context.Background(), backend, session.SessionID)
	if err != nil {
		t.Fatal(err)
	}
	if plan.Status != "READY" || plan.APIVersion != EditPlanAPIVersionV2 || !plan.CommitAllowed || len(plan.AffectedDocuments) != 3 || adapter.calls != 1 {
		t.Fatalf("plan=%#v calls=%d", plan, adapter.calls)
	}
	for _, change := range plan.AffectedDocuments {
		if change.Before == nil || change.Before.State != "ABSENT" || change.After == nil || change.After.State != "PRESENT" {
			t.Fatalf("change=%#v", change)
		}
	}
	result := backend.CommitEditPlan(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" || adapter.calls != 2 {
		t.Fatalf("result=%#v calls=%d", result, adapter.calls)
	}
	if !sessions.ConsumePlan(session.SessionID, plan.PlanID) {
		t.Fatal("reviewed session was not consumed")
	}
	expired := backend.CommitEditPlanV2(context.Background(), plan.PlanID)
	if code := findingCode(expired); code != "PLAN_EXPIRED" || expired.APIVersion != EditResultAPIVersionV2 {
		t.Fatalf("second commit=%#v code=%s", expired, code)
	}
	if string(mustRead(t, filepath.Join(root, "ansible.cfg"))) != string(firstSaveAnsibleConfig) {
		t.Fatal("ansible.cfg template drift")
	}
	inventory := string(mustRead(t, filepath.Join(root, "inventory", "hosts.yml")))
	if inventory != string(firstSaveInventory([]firstSaveServer{{id: "node1", typeID: "infra", address: "192.0.2.10"}})) {
		t.Fatalf("inventory=%s", inventory)
	}
}

func TestFirstSaveCollisionBlocksWithoutCanonicalWrites(t *testing.T) {
	root, revision := emptyManagedProject(t)
	if err := os.MkdirAll(filepath.Join(root, "inventory"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "inventory", "hosts.yml"), []byte("user-owned\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	backend := NewBackend(&firstWriteAdapter{})
	plan, err := backend.planFirstWrite(context.Background(), root, revision, []EditCommand{{APIVersion: EditCommandAPIVersionV2, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "CreateServer", HostID: "node1", Address: "192.0.2.10"}})
	if err != nil {
		t.Fatal(err)
	}
	if plan.Status != "BLOCKED" || plan.Validation.Findings[0].Code != "WRITE_OWNERSHIP_REQUIRED" {
		t.Fatalf("plan=%#v", plan)
	}
	if string(mustRead(t, filepath.Join(root, "inventory", "hosts.yml"))) != "user-owned\n" {
		t.Fatal("collision was mutated")
	}
}

func TestFirstSaveUnknownConfiguredTypePlansWithoutCanonicalWrites(t *testing.T) {
	root, revision := emptyManagedProject(t)
	manifestBefore := append([]byte(nil), mustRead(t, filepath.Join(root, "project.yml"))...)
	backend := NewBackend(&firstWriteAdapter{}, WithServerTypes([]string{"infra"}))
	plan, err := backend.planFirstWrite(context.Background(), root, revision, []EditCommand{{APIVersion: EditCommandAPIVersionV3, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "CreateServer", HostID: "node1", ServerType: "scada", Address: "192.0.2.10"}})
	if err != nil || plan.Status != "READY" || !plan.CommitAllowed {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
	if string(mustRead(t, filepath.Join(root, "project.yml"))) != string(manifestBefore) {
		t.Fatal("planning unknown type mutated project.yml")
	}
	if _, err := os.Stat(filepath.Join(root, "inventory")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("planning unknown type created inventory: %v", err)
	}
}

func mustRead(t *testing.T, path string) []byte {
	t.Helper()
	value, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return value
}

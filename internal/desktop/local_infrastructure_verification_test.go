package desktop

import (
	"os"
	"platform-installer/internal/executionnode"
	"strings"
	"testing"
	"time"
)

func infrastructureRecord(t *testing.T) localInfrastructureVerification {
	t.Helper()
	root, err := canonicalRunProjectRoot(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	fingerprint, revision := "sha256:"+strings.Repeat("a", 64), "sha256:"+strings.Repeat("b", 64)
	return localInfrastructureVerification{Version: 1, ProjectRoot: root, ProjectID: "project-one", ExecutionNodeBinding: "node-address-hostkey", RuntimeBundleDigest: "sha256:" + strings.Repeat("c", 64), ObservedAt: "2026-10-14T10:00:00Z", Verification: executionnode.InfrastructureVerification{Status: "PASS", InfrastructureFingerprint: &fingerprint, EvidenceRevision: &revision, Deployments: []executionnode.InfrastructureDeploymentVerification{}}}
}

func TestInfrastructureCacheRoundtripAndBinding(t *testing.T) {
	store, r := t.TempDir(), infrastructureRecord(t)
	if err := writeLocalInfrastructureVerification(store, r); err != nil {
		t.Fatal(err)
	}
	got, err := readLocalInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, r.ExecutionNodeBinding, r.RuntimeBundleDigest)
	if err != nil || got == nil || got.Verification.Status != "PASS" {
		t.Fatalf("got=%v err=%v", got, err)
	}
	for _, binding := range []struct{ node, bundle string }{{"other-node", r.RuntimeBundleDigest}, {r.ExecutionNodeBinding, "sha256:" + strings.Repeat("d", 64)}} {
		if got, err := readLocalInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, binding.node, binding.bundle); got != nil || err == nil {
			t.Fatal("cache binding mismatch accepted")
		}
	}
	// Relocation never transfers an observation to a different project root.
	got, err = readLocalInfrastructureVerification(store, t.TempDir(), r.ProjectID, r.ExecutionNodeBinding, r.RuntimeBundleDigest)
	if got != nil || err != nil {
		t.Fatalf("relocation got=%v err=%v", got, err)
	}
}

func TestInfrastructureCacheCorruptionNeverReturnsPass(t *testing.T) {
	for _, corrupt := range []string{`{`, `{"version":99}`, strings.Repeat("x", maxInfrastructureRecordBytes+1)} {
		store, r := t.TempDir(), infrastructureRecord(t)
		path, err := localRunRecordPath(store, r.ProjectRoot, r.ProjectID)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(corrupt), 0o600); err != nil {
			t.Fatal(err)
		}
		if got, err := readLocalInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, r.ExecutionNodeBinding, r.RuntimeBundleDigest); got != nil || err == nil {
			t.Fatal("corrupt cache accepted")
		}
	}
}

func TestInfrastructureCacheFailureDoesNotAlterRunRecord(t *testing.T) {
	store, run := testLocalRunRecord(t)
	if err := writeLocalRunRecord(store, run); err != nil {
		t.Fatal(err)
	}
	r := infrastructureRecord(t)
	r.Version = 2
	if err := writeLocalInfrastructureVerification(store, r); err == nil {
		t.Fatal("unknown cache version accepted")
	}
	got, err := readLocalRunRecord(store, run.ProjectRoot, run.ProjectID)
	if err != nil || got == nil || *got != run {
		t.Fatal("legacy run record changed")
	}
}

func TestInfrastructureCacheIsObservationAndAccountIndependent(t *testing.T) {
	store, r := t.TempDir(), infrastructureRecord(t)
	node := executionnode.Node{ID: "node1", Address: "192.0.2.1", Port: 22, User: "first"}
	plan := executionnode.DeploymentPlan{ProjectIdentity: r.ProjectID, InfrastructureVerification: &r.Verification, RuntimeRelease: map[string]any{"bundleDigest": r.RuntimeBundleDigest}}
	if err := cacheInfrastructurePlan(store, r.ProjectRoot, node, plan, time.Now()); err != nil {
		t.Fatal(err)
	}
	node.User = "second"
	view := cachedInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, node, r.RuntimeBundleDigest)
	if view.Availability != "UNKNOWN" || view.Previous == nil || view.Previous.Status != "PASS" {
		t.Fatal("cache either lost observation or authorized current state")
	}
	node.Address = "192.0.2.2"
	if got := cachedInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, node, r.RuntimeBundleDigest); got.Previous != nil || got.Availability != "UNKNOWN" {
		t.Fatal("different node inherited cache")
	}
}

func TestInfrastructureCacheRejectsSymlinkAndWriteFailure(t *testing.T) {
	store, r := t.TempDir(), infrastructureRecord(t)
	path, err := localRunRecordPath(store, r.ProjectRoot, r.ProjectID)
	if err != nil {
		t.Fatal(err)
	}
	target := t.TempDir() + "/outside"
	if err := os.WriteFile(target, []byte("outside"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, path); err == nil {
		if err := writeLocalInfrastructureVerification(store, r); err == nil {
			t.Fatal("symlink overwritten")
		}
		if got, err := readLocalInfrastructureVerification(store, r.ProjectRoot, r.ProjectID, r.ExecutionNodeBinding, r.RuntimeBundleDigest); got != nil || err == nil {
			t.Fatal("symlink read")
		}
		if data, _ := os.ReadFile(target); string(data) != "outside" {
			t.Fatal("outside target changed")
		}
	}
	if err := writeLocalInfrastructureVerification(target, r); err == nil {
		t.Fatal("file used as store")
	}
}

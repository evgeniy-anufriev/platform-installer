package executionnode

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"platform-installer/internal/executionbundle"
	"testing"
	"time"
)

func TestPreparationStepErrorDoesNotExposeTransportDetail(t *testing.T) {
	cause := errors.New("private-key-path and remote output must stay internal")
	for _, code := range []string{
		"EXECUTION_NODE_PREPARE_INSPECT_FAILED",
		"EXECUTION_NODE_PREPARE_WORKSPACE_FAILED",
		"EXECUTION_NODE_PREPARE_STAGE_FAILED",
		"EXECUTION_NODE_PREPARE_ACTIVATE_FAILED",
	} {
		err := &PreparationStepError{Code: code, cause: cause}
		if err.Error() != code || !errors.Is(err, cause) {
			t.Fatalf("unsafe step error %q: %v", code, err)
		}
	}
}

type fakeTransport struct {
	inspection       Inspection
	workspaceCalls   int
	workspaceChanged bool
	workspaceErr     error
}

func (f *fakeTransport) InspectExecutionNode(context.Context, Node) (Inspection, error) {
	return f.inspection, nil
}
func (f *fakeTransport) ReconcileWorkspaceOwnership(context.Context, Node) (bool, error) {
	f.workspaceCalls++
	return f.workspaceChanged, f.workspaceErr
}
func (f *fakeTransport) StageVerifiedBundle(context.Context, Node, executionbundle.Verified) (string, error) {
	return "stage", nil
}

func TestPreparationPlanIncludesWorkspaceOwnershipReconciliation(t *testing.T) {
	for _, state := range []State{Ready, Unprepared, UpdateRequired} {
		steps := preparationSteps(state)
		found := false
		for _, step := range steps {
			if step.ID == "reconcile-workspace" {
				found = step.Mutates && step.Action == "RECONCILE"
			}
		}
		if !found {
			t.Fatalf("state %s omits mutating workspace reconciliation: %+v", state, steps)
		}
	}
}

func TestPrepareReconcilesWorkspaceEvenWhenRuntimeIsAlreadyReady(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "core"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "core", "capabilities.yml"), []byte("---\n"), 0600); err != nil {
		t.Fatal(err)
	}
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:f52d711103d50a437830c6fbcd04fb4bab49a0f82f6d26d1c791c6e8488dd090\n    size: 4\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0600); err != nil {
		t.Fatal(err)
	}
	bundle, err := executionbundle.ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	transport := &fakeTransport{workspaceChanged: true, inspection: Inspection{
		State: Ready, OS: "redos", OSVersion: "8", Architecture: "x86_64", Elevation: true, FreeBytes: 1,
		Runtime: Runtime{BundleDigest: bundle.Digest, Protocol: executionbundle.ProtocolVersion, Ansible: true, Capabilities: true},
	}}
	service := NewService(transport)
	plan, err := service.PlanExecutionNodePreparation(context.Background(), testNode(), root)
	if err != nil {
		t.Fatal(err)
	}
	result, err := service.Prepare(context.Background(), testNode(), root, plan.ID)
	if err != nil || result.State != Ready || !result.Changed || transport.workspaceCalls != 1 {
		t.Fatalf("result=%+v err=%v workspace reconciliations=%d", result, err, transport.workspaceCalls)
	}
}
func (f *fakeTransport) ActivateStagedRuntime(context.Context, Node, string, executionbundle.Verified) (Runtime, error) {
	return f.inspection.Runtime, nil
}
func (f *fakeTransport) DiscardStagedRuntime(context.Context, Node, string) error { return nil }
func testNode() Node {
	return Node{ID: "node1", Address: "192.0.2.1", User: "installer", Port: 22, CredentialRef: "runtime:key", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: "runtime/known_hosts", Fingerprint: "SHA256:test"}}
}
func TestInspectBlocksUntrustedHostKey(t *testing.T) {
	service := NewService(&fakeTransport{})
	node := testNode()
	node.HostKey.State = "UNKNOWN"
	result, err := service.InspectExecutionNode(context.Background(), node)
	if err != nil || result.State != Broken || result.Findings[0].Code != "EXECUTION_NODE_HOST_KEY_UNTRUSTED" {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestPrepareRejectsPlanTampering(t *testing.T) {
	service := NewService(&fakeTransport{})
	service.plans["plan"] = Plan{ID: "plan", Digest: "changed"}
	result, err := service.Prepare(context.Background(), testNode(), t.TempDir(), "plan")
	if err != nil || result.Findings[0].Code != "EXECUTION_NODE_PLAN_INVALID" {
		t.Fatalf("%+v %v", result, err)
	}
}

func TestPreparationPlanDefaultTTLIsOneHour(t *testing.T) {
	service := NewService(&fakeTransport{})
	if service.ttl != time.Hour {
		t.Fatalf("preparation plan TTL=%s, want 1h", service.ttl)
	}
}

func TestRequiredStateRejectsIncompatibleBundle(t *testing.T) {
	bundle := executionbundle.Verified{Manifest: executionbundle.Manifest{Platforms: []executionbundle.Platform{{OS: "alt", Version: "10", Architecture: "x86_64"}}}}
	inspection := Inspection{OS: "redos", OSVersion: "8.0.3", Architecture: "x86_64", Elevation: true, FreeBytes: 1}
	if got := requiredState(inspection, bundle); got != Incompatible {
		t.Fatalf("expected incompatible, got %s", got)
	}
}

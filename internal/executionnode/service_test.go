package executionnode

import (
	"context"
	"platform-installer/internal/executionbundle"
	"testing"
)

type fakeTransport struct{ inspection Inspection }

func (f *fakeTransport) InspectExecutionNode(context.Context, Node) (Inspection, error) {
	return f.inspection, nil
}
func (f *fakeTransport) StageVerifiedBundle(context.Context, Node, executionbundle.Verified) (string, error) {
	return "stage", nil
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

func TestRequiredStateRejectsIncompatibleBundle(t *testing.T) {
	bundle := executionbundle.Verified{Manifest: executionbundle.Manifest{Platforms: []executionbundle.Platform{{OS: "alt", Version: "10", Architecture: "x86_64"}}}}
	inspection := Inspection{OS: "redos", OSVersion: "8.0.3", Architecture: "x86_64", Elevation: true, FreeBytes: 1}
	if got := requiredState(inspection, bundle); got != Incompatible {
		t.Fatalf("expected incompatible, got %s", got)
	}
}

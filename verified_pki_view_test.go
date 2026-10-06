package main

import (
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func verifiedPKISnapshot() *coreadapter.Snapshot {
	return &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision", PKI: map[string]any{
		"status": "PASS",
		"certificateIdentities": []any{map[string]any{
			"id":           "platform-tls--kafka-main",
			"scope":        "DEPLOYMENT",
			"tlsProfileId": "platform-tls",
			"dnsNames":     []any{"kafka.example.test", "*.example.test"},
			"ipAddresses":  []any{"192.0.2.44", "2001:db8::44"},
			"consumers":    []any{map[string]any{"deploymentId": "kafka-main", "memberId": "kafka-kafka-1", "hostId": "node1", "tlsProfileRef": "platform-tls"}},
		}},
	}}
}

func TestBuildVerifiedPKIViewIsTypedBoundedAndFailClosed(t *testing.T) {
	view, err := buildVerifiedPKIView(verifiedPKISnapshot())
	if err != nil || view.Status != "CURRENT" || len(view.Identities) != 1 || view.Identities[0].TLSProfileID != "platform-tls" || len(view.Identities[0].Consumers) != 1 {
		t.Fatalf("view=%#v err=%v", view, err)
	}
	bad := verifiedPKISnapshot()
	bad.PKI["certificateIdentities"] = []any{map[string]any{"id": "raw", "scope": "HOST"}}
	if _, err := buildVerifiedPKIView(bad); err == nil {
		t.Fatal("partial raw identity unexpectedly projected")
	}
	oversized := verifiedPKISnapshot()
	identities := make([]any, maxVerifiedPKIIdentities+1)
	for index := range identities {
		identities[index] = verifiedPKISnapshot().PKI["certificateIdentities"].([]any)[0]
	}
	oversized.PKI["certificateIdentities"] = identities
	if _, err := buildVerifiedPKIView(oversized); err == nil {
		t.Fatal("oversized identity collection unexpectedly projected")
	}
}

func TestVerifiedPKIViewRequiresExactCurrentEvidence(t *testing.T) {
	node := executionnode.Node{ID: "qa-node"}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}
	app := NewApp(snapshotReaderStub{}, lifecycleStub{}, WithExplicitExecutionNode(node.ID, "192.0.2.10"), WithTrustedExecutionNodeBinding(executionNodeBinding{node: node, reader: projectReader{runtimeRelease: map[string]any{"bundleDigest": "sha256:bundle", "coreVersion": "core", "catalogDigest": "sha256:catalog", "planningProtocol": "protocol"}}}))
	app.current = ProjectOpenResult{Status: "OPEN", Root: t.TempDir(), Project: project, Managed: &installer.ManagedProjectView{ProjectRevision: "sha256:revision"}, Snapshot: verifiedPKISnapshot(), Verification: ProjectVerification{Status: "VERIFIED", ProjectIdentity: project.ID, ProjectRevision: "sha256:revision", ExecutionNodeID: node.ID, Runtime: &executionnode.RuntimeEvidence{BundleDigest: "sha256:bundle", CoreVersion: "core", CatalogDigest: "sha256:catalog", Protocol: "protocol"}}}
	app.execution.bind(app.current.Root, project.ID, nil)
	if current := app.GetVerifiedPKIView(); current.Status != "CURRENT" || len(current.Identities) != 1 {
		t.Fatalf("current=%#v", current)
	}
	app.current.Verification.Status = "STALE"
	if stale := app.GetVerifiedPKIView(); stale.Status != "STALE" || len(stale.Identities) != 0 || len(stale.Findings) != 0 {
		t.Fatalf("stale=%#v", stale)
	}
	app.current.Verification = ProjectVerification{Status: "INVALID", Findings: []VerificationFinding{{Code: "CERTIFICATE_REISSUE_REQUIRED", Summary: "safe"}}}
	invalid := app.GetVerifiedPKIView()
	if invalid.Status != "INVALID" || len(invalid.Identities) != 0 || len(invalid.Findings) != 1 {
		t.Fatalf("invalid=%#v", invalid)
	}
	app.current.Verification = ProjectVerification{Status: "VERIFIED", ProjectIdentity: project.ID, ProjectRevision: "sha256:other", ExecutionNodeID: node.ID, Runtime: &executionnode.RuntimeEvidence{}}
	if stale := app.GetVerifiedPKIView(); stale.Status != "STALE" || len(stale.Identities) != 0 {
		t.Fatalf("stale=%#v", stale)
	}
}

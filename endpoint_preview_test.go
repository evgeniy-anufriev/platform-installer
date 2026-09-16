package main

import (
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func previewSnapshot() *coreadapter.Snapshot {
	addresses := []any{map[string]any{"address": "192.0.2.44", "interface": "eth0"}}
	return &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision", ServiceDeployments: map[string]map[string]any{
		"proxy-main": {"endpointGroupRef": "edge", "virtualRouterId": float64(42), "virtualAddresses": addresses},
	}, Endpoints: map[string]any{"deployments": map[string]any{
		"kafka-main": map[string]any{"fqdn": "kafka-main.edge.example.test"},
	}}, Integrations: map[string]any{"addressProvidersByEndpointGroup": map[string]any{
		"edge": []any{map[string]any{"deploymentId": "proxy-main", "virtualAddresses": addresses}},
	}}}
}

func TestBuildEndpointPreviewIsTypedBoundedAndFailClosed(t *testing.T) {
	preview, err := buildEndpointPreview(previewSnapshot())
	if err != nil || preview.Status != "CURRENT" || len(preview.Endpoints) != 1 || len(preview.Providers) != 1 || preview.Providers[0].VirtualRouterID != 42 {
		t.Fatalf("preview=%#v err=%v", preview, err)
	}
	bad := previewSnapshot()
	bad.Integrations["addressProvidersByEndpointGroup"] = map[string]any{"edge": []any{map[string]any{"deploymentId": "proxy-main", "virtualAddresses": []any{"raw"}}}}
	if _, err := buildEndpointPreview(bad); err == nil {
		t.Fatal("malformed provider address unexpectedly projected")
	}
	limited := previewSnapshot()
	endpoints := map[string]any{}
	for index := 0; index < 65; index++ {
		id := "service-" + string(rune('a'+index%26)) + "-" + string(rune('a'+(index/26)))
		endpoints[id] = map[string]any{"fqdn": id + ".edge.example.test"}
	}
	limited.Endpoints["deployments"] = endpoints
	projection, err := buildEndpointPreview(limited)
	if err != nil || len(projection.Endpoints) != maxEndpointPreviewEndpoints || !projection.Truncated {
		t.Fatalf("bounded projection=%#v err=%v", projection, err)
	}
}

func TestEndpointPreviewInvalidAndSelectionChangeNeverExposeRows(t *testing.T) {
	node := executionnode.Node{ID: "qa-node"}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}
	app := NewApp(snapshotReaderStub{}, lifecycleStub{}, WithExplicitExecutionNode(node.ID, "192.0.2.10"), WithTrustedExecutionNodeBinding(executionNodeBinding{node: node}))
	app.current = ProjectOpenResult{Status: "OPEN", Root: t.TempDir(), Project: project, Managed: &installer.ManagedProjectView{ProjectRevision: "sha256:revision"}, Snapshot: previewSnapshot(), Verification: ProjectVerification{Status: "INVALID", ProjectIdentity: project.ID, ProjectRevision: "sha256:revision", Findings: []VerificationFinding{{Code: "INVALID", Summary: "safe"}}}}
	app.execution.bind(app.current.Root, project.ID, nil)
	invalid := app.GetEndpointPreview()
	if invalid.Status != "INVALID" || len(invalid.Endpoints) != 0 || len(invalid.Providers) != 0 || len(invalid.Findings) != 1 {
		t.Fatalf("invalid=%#v", invalid)
	}
	app.current.Verification = ProjectVerification{Status: "VERIFIED", ProjectIdentity: project.ID, ProjectRevision: "sha256:revision", ExecutionNodeID: node.ID, Runtime: &executionnode.RuntimeEvidence{BundleDigest: "sha256:bundle", CoreVersion: "core", CatalogDigest: "sha256:catalog", Protocol: "protocol"}}
	if current := app.GetEndpointPreview(); current.Status != "CURRENT" || len(current.Endpoints) != 1 {
		t.Fatalf("current=%#v", current)
	}
	app.execution.bind(app.current.Root, project.ID, map[string]map[string]any{"node1": {"ansibleHost": "192.0.2.11"}})
	if _, err := app.SelectExecutionNode("node1"); err != nil {
		t.Fatal(err)
	}
	if app.current.Snapshot != nil || app.current.Verification.Status != "UNVERIFIED" {
		t.Fatalf("selection retained evidence: %#v", app.current)
	}
}

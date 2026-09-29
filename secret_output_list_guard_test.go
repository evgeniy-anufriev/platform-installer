package main

import (
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/projectlifecycle"
)

func TestPendingOutputListRejectsChangedContextDuringRemoteCall(t *testing.T) {
	changes := map[string]func(*App){
		"generation": func(a *App) { a.installationGeneration++ },
		"project":    func(a *App) { a.current.Project.ID = "different-project" },
		"root":       func(a *App) { a.current.Root += "-different" },
		"closed":     func(a *App) { a.current.Status = "CLOSED" },
		"readiness":  func(a *App) { a.execution.context.Status = "NOT_PREPARED" },
		"selection":  func(a *App) { a.execution.external.hostID = "another-node" },
		"binding":    func(a *App) { clone := *a.binding; a.binding = &clone },
		"address":    func(a *App) { a.binding.node.Address = "192.0.2.11" },
		"runtime":    func(a *App) { a.binding.reader.runtimeRelease["bundleDigest"] = "sha256:" + strings.Repeat("d", 64) },
	}
	for name, change := range changes {
		t.Run(name, func(t *testing.T) {
			root := t.TempDir()
			node := executionnode.Node{ID: "desktop-qa", Address: "192.0.2.10"}
			transport := &secretOutputTransportStub{}
			reader := projectReader{transport: transport, node: node, runtimeRelease: map[string]any{
				"bundleDigest": "sha256:" + strings.Repeat("b", 64), "coreVersion": "test-core",
				"catalogDigest": "sha256:" + strings.Repeat("c", 64), "planningProtocol": executionbundle.ProtocolVersion}}
			app := NewApp(reader, lifecycleStub{}, WithExplicitExecutionNode(node.ID, node.Address),
				WithTrustedExecutionNodeBinding(executionNodeBinding{node: node, reader: reader, service: &executionLifecycleStub{}, bundleRoot: "bundle"}))
			app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
			app.bindExecutionLocked(root, app.current.Project, nil)
			app.execution.context.Status = "READY"
			entered, resume := make(chan struct{}), make(chan struct{})
			transport.onList = func() { close(entered); <-resume }
			completed := make(chan SecretOutputPackagesOperation, 1)
			go func() { completed <- app.ListPendingSecretOutputs(nil) }()
			<-entered
			app.editMu.Lock()
			change(app)
			app.editMu.Unlock()
			close(resume)
			result := <-completed
			if result.Status != "UNAVAILABLE" || result.Error == nil || result.Error.Code != "PROJECT_CHANGED" || len(result.Packages) != 0 {
				t.Fatalf("changed context admitted: %#v", result)
			}
		})
	}
}

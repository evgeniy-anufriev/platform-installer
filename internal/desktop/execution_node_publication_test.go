package desktop

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

func v02TestBundle(t *testing.T) executionbundle.Verified {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "catalog"), 0o700); err != nil {
		t.Fatal(err)
	}
	catalog := []byte("apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions: {}\n")
	if err := os.WriteFile(filepath.Join(root, "catalog", "service-catalog.yml"), catalog, 0o600); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(catalog)
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: test\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: catalog/service-catalog.yml\n    sha256: sha256:" + hex.EncodeToString(sum[:]) + "\n    size: " + strconv.Itoa(len(catalog)) + "\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	verified, err := executionbundle.ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	return verified
}

func TestV02ActualLeaseExpiryDuringInspectCannotPublishReady(t *testing.T) {
	verified := v02TestBundle(t)
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("name: unchanged\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	keyPath := filepath.Join(t.TempDir(), "qa.pem")
	if err := os.WriteFile(keyPath, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0o600); err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	broker := runtimesecret.NewBroker(runtimesecret.WithClock(func() time.Time { return now }), runtimesecret.WithTTL(time.Minute))
	projectID := "project-aaaaaaaaaaaaaaaa"
	secretBinding := runtimesecret.Binding{Root: root, ID: projectID}
	if _, err := broker.Set(secretBinding, runtimesecret.Input{Username: "platform-automation", SSHMode: runtimesecret.SSHPrivateKey, PrivateKeyPath: keyPath, ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	identity, err := broker.CurrentExecutionIdentity(secretBinding)
	if err != nil {
		t.Fatal(err)
	}
	node := executionnode.Node{ID: "node1", Address: "192.0.2.10", User: identity.Username, Port: 22}
	release := map[string]any{"bundleDigest": verified.Digest, "coreVersion": verified.Manifest.CoreVersion, "catalogDigest": verified.Manifest.CatalogDigest, "planningProtocol": executionbundle.ProtocolVersion}
	reader := projectReader{transport: verificationTransportStub{}, node: node, runtimeRelease: release}
	stub := &executionLifecycleStub{inspection: executionnode.Inspection{State: executionnode.Ready}}
	app := NewApp(unavailableProjectReader{}, lifecycleStub{}, WithAvailableExecutionBundle(verified.Root))
	app.secrets = broker
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: projectID, Source: projectlifecycle.CompatibilitySourceSummary{BundleDigest: verified.Digest, CatalogDigest: verified.Manifest.CatalogDigest}}, Managed: &installer.ManagedProjectView{Servers: map[string]installer.ManagedServer{"node1": {HostID: "node1", Address: node.Address}}}, Verification: notVerified()}
	app.execution.bind(root, projectID, managedSnapshotHosts(app.current.Managed))
	app.binding = &executionNodeBinding{node: node, reader: reader, service: stub, bundleRoot: verified.Root, dynamic: true, credentialGeneration: identity.Generation, hostKeyPin: &approvedExecutionHostKey{}, commandGuard: func() (func(), error) { return func() {}, nil }}
	stub.onInspect = func() { now = now.Add(2 * time.Minute) }
	result := app.CheckExecutionNode()
	if stub.inspectCalls != 1 || result.Error == nil || app.binding != nil || app.execution.context.Status == "READY" || app.current.Snapshot != nil {
		t.Fatalf("expired lease published READY: %#v", result)
	}
}

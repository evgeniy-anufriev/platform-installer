package main

import (
	"context"
	"errors"
	"os"
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
)

type snapshotReaderStub struct {
	snapshot *coreadapter.Snapshot
	err      error
}

func (s snapshotReaderStub) BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error) {
	return s.snapshot, s.err
}

func TestAppOpenProjectIsReadOnlyAndRetainsNoErrorState(t *testing.T) {
	root := t.TempDir()
	app := NewApp(snapshotReaderStub{snapshot: &coreadapter.Snapshot{Status: "PASS", ProjectRevision: "sha256:revision"}})
	result := app.OpenProject(root)
	if result.Status != "OPEN" || result.Root == "" || result.Snapshot == nil {
		t.Fatalf("result=%+v", result)
	}
	if closed := app.CloseProject(); closed.Status != "NO_PROJECT" || closed.Snapshot != nil {
		t.Fatalf("closed=%+v", closed)
	}
}

func TestAppReturnsSafeFailure(t *testing.T) {
	app := NewApp(snapshotReaderStub{err: errors.New("EXECUTION_NODE_UNAVAILABLE")})
	result := app.OpenProject(t.TempDir())
	if result.Status != "ERROR" || result.Error == nil || result.Error.Code != "EXECUTION_NODE_UNAVAILABLE" || result.Error.Message == "EXECUTION_NODE_UNAVAILABLE" {
		t.Fatalf("result=%+v", result)
	}
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
	result := NewApp(reader).OpenProject(required("UI01B_E2E_PROJECT"))
	if result.Status != "OPEN" || result.Snapshot == nil || result.Snapshot.Status != "PASS" {
		t.Fatalf("remote read-only open result=%+v", result)
	}
}

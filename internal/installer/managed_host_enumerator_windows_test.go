//go:build windows

package installer

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEnumerateManagedHostDocumentsRejectsJunction(t *testing.T) {
	root := t.TempDir()
	hostVars := filepath.Join(root, "inventory", "host_vars")
	outside := t.TempDir()
	if err := os.MkdirAll(hostVars, 0o700); err != nil {
		t.Fatal(err)
	}
	makeJunction(t, filepath.Join(hostVars, "node1"), outside)
	if _, err := enumerateManagedHostDocuments(root); err == nil {
		t.Fatal("managed host junction was accepted")
	}
}

func TestEnumeratedManagedHostDocumentRejectsJunctionReplacement(t *testing.T) {
	root := t.TempDir()
	hostDir := filepath.Join(root, "inventory", "host_vars", "node1")
	if err := os.MkdirAll(hostDir, 0o700); err != nil {
		t.Fatal(err)
	}
	logical := managedHostDocument("node1")
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(logical)), append(append([]byte(nil), managedHeader...), []byte("platform_deployments: {}\n")...), 0o600); err != nil {
		t.Fatal(err)
	}
	paths, err := enumerateManagedHostDocuments(root)
	if err != nil || len(paths) != 1 || paths[0] != logical {
		t.Fatalf("paths=%v err=%v", paths, err)
	}
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "platform-installer.yml"), append(append([]byte(nil), managedHeader...), []byte("platform_deployments: {}\n")...), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.RemoveAll(hostDir); err != nil {
		t.Fatal(err)
	}
	makeJunction(t, hostDir, outside)
	if _, _, _, err := (&managedReadBudget{}).ownedDocumentOptionalBytes(root, logical); err == nil {
		t.Fatal("enumeration-to-open junction replacement authorized a document")
	}
}

package installer

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestEnumerateManagedHostDocumentsIsSortedAndBounded(t *testing.T) {
	root := t.TempDir()
	hostVars := filepath.Join(root, "inventory", "host_vars")
	for _, hostID := range []string{"node-b", "node-a"} {
		if err := os.MkdirAll(filepath.Join(hostVars, hostID), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	paths, err := enumerateManagedHostDocuments(root)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{managedHostDocument("node-a"), managedHostDocument("node-b")}
	if len(paths) != len(want) || paths[0] != want[0] || paths[1] != want[1] {
		t.Fatalf("paths=%v want=%v", paths, want)
	}

	for index := 0; index < maxManagedHostDocuments-2; index++ {
		if err := os.Mkdir(filepath.Join(hostVars, fmt.Sprintf("host-%04d", index)), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	if paths, err = enumerateManagedHostDocuments(root); err != nil || len(paths) != maxManagedHostDocuments {
		t.Fatalf("exact limit paths=%d err=%v", len(paths), err)
	}
	if err := os.Mkdir(filepath.Join(hostVars, "overflow"), 0o700); err != nil {
		t.Fatal(err)
	}
	if _, err := enumerateManagedHostDocuments(root); err == nil {
		t.Fatal("4,097th managed host directory was accepted")
	}
}

func TestEnumerateManagedHostDocumentsRejectsInvalidAndLinkEntries(t *testing.T) {
	t.Run("invalid identifier", func(t *testing.T) {
		root := t.TempDir()
		if err := os.MkdirAll(filepath.Join(root, "inventory", "host_vars", "invalid host"), 0o700); err != nil {
			t.Fatal(err)
		}
		if _, err := enumerateManagedHostDocuments(root); err == nil {
			t.Fatal("invalid host directory identifier was accepted")
		}
	})
	t.Run("link", func(t *testing.T) {
		root := t.TempDir()
		hostVars := filepath.Join(root, "inventory", "host_vars")
		outside := t.TempDir()
		if err := os.MkdirAll(hostVars, 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.Symlink(outside, filepath.Join(hostVars, "node1")); err != nil {
			if runtime.GOOS == "windows" {
				t.Skipf("directory symlink creation unavailable: %v", err)
			}
			t.Fatal(err)
		}
		if _, err := enumerateManagedHostDocuments(root); err == nil {
			t.Fatal("managed host link entry was accepted")
		}
	})
}

func TestEnumeratedHostDocumentReplacementIsRejectedByOpenedObjectRead(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows reparse replacement is covered by the Windows-specific junction test")
	}
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
	if err := os.Symlink(outside, hostDir); err != nil {
		t.Fatal(err)
	}
	if _, _, _, err := (&managedReadBudget{}).ownedDocumentOptionalBytes(root, logical); err == nil {
		t.Fatal("enumeration-to-open replacement authorized a linked document")
	}
}

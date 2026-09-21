//go:build linux

package installer

import (
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/sys/unix"
)

func TestProjectExportCleanupRejectsSwappedStagingSibling(t *testing.T) {
	parent := t.TempDir()
	destination, err := openExportDestinationDirectory(parent)
	if err != nil {
		t.Fatal(err)
	}
	defer destination.close()

	staging, stagingName, err := destination.createStaging("portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	defer staging.close()
	replacementName := ".attacker-replacement"
	replacementPath := filepath.Join(parent, replacementName)
	if err := os.Mkdir(replacementPath, 0o700); err != nil {
		t.Fatal(err)
	}
	markerPath := filepath.Join(replacementPath, "must-survive")
	if err := os.WriteFile(markerPath, []byte("replacement"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := unix.Renameat2(destination.fd, stagingName, destination.fd, replacementName, unix.RENAME_EXCHANGE); err != nil {
		t.Fatal(err)
	}

	if err := destination.removeOwnedTree(staging, stagingName); err == nil {
		t.Fatal("cleanup unexpectedly accepted a swapped staging path")
	}
	if _, err := os.Stat(filepath.Join(parent, stagingName, "must-survive")); err != nil {
		t.Fatalf("replacement sibling was removed or changed: %v", err)
	}
}

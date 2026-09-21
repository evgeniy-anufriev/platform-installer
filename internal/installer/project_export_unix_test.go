//go:build linux

package installer

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
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

func TestProjectExportFailureRetainsLinuxStagingWithoutPublishing(t *testing.T) {
	source, destination := t.TempDir(), t.TempDir()
	writeExportFixture(t, source, "project.yml", "apiVersion: platform.installer/project/v1alpha1\n")
	export, plan, err := PlanProjectExport(source, destination, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	export.writeObservation = func(*exportDirectory, exportObservation) error {
		return errors.New("injected write failure")
	}
	result := export.Commit(plan.PlanDigest)
	if result.Status != "FAILED" || result.ErrorCode != "EXPORT_STAGING_RETAINED" {
		t.Fatalf("result=%#v", result)
	}
	if _, err := os.Stat(filepath.Join(destination, "portable-copy")); !os.IsNotExist(err) {
		t.Fatalf("destination was published after failed export: %v", err)
	}
	entries, err := os.ReadDir(destination)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || !strings.HasPrefix(entries[0].Name(), ".platform-export-") {
		t.Fatalf("retained staging=%v", entries)
	}
}

//go:build windows

package installer

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestProjectExportRejectsWindowsJunctionSource(t *testing.T) {
	parent, source, destination := t.TempDir(), t.TempDir(), t.TempDir()
	if err := os.WriteFile(filepath.Join(source, "project.yml"), []byte("apiVersion: platform.installer/v2alpha1\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	junction := filepath.Join(parent, "source")
	makeJunction(t, junction, source)
	if _, _, err := PlanProjectExport(junction, destination, "portable-copy"); err == nil || err.Error() != "EXPORT_SOURCE_UNSAFE" {
		t.Fatalf("junction source err=%v", err)
	}
}

func TestProjectExportFailureCleansWindowsStaging(t *testing.T) {
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
	if result.Status != "FAILED" || result.ErrorCode != "EXPORT_WRITE_FAILED" {
		t.Fatalf("result=%#v", result)
	}
	entries, err := os.ReadDir(destination)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("staging was not cleaned: %v", entries)
	}
}

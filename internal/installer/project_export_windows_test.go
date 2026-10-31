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

func TestProjectExportFailureCleansNestedWindowsStaging(t *testing.T) {
	source, destination := t.TempDir(), t.TempDir()
	writeExportFixture(t, source, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	export, plan, err := PlanProjectExport(source, destination, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	export.writeObservation = func(staging *exportDirectory, observation exportObservation) error {
		child, err := staging.createDirectory("inventory")
		if err != nil {
			return err
		}
		defer child.close()
		if err := child.writeFile("hosts.yml", []byte("all: {}\n")); err != nil {
			return err
		}
		return errors.New("injected write failure after nested directory")
	}
	result := export.Commit(plan.PlanDigest)
	if result.ErrorCode != "EXPORT_WRITE_FAILED" {
		t.Fatalf("result=%#v", result)
	}
	entries, err := os.ReadDir(destination)
	if err != nil || len(entries) != 0 {
		t.Fatalf("staging remains: %v err=%v", entries, err)
	}
}

func TestProjectExportFailureRetainsWindowsJunctionWithoutDeletingTarget(t *testing.T) {
	source, destination, outside := t.TempDir(), t.TempDir(), t.TempDir()
	writeExportFixture(t, source, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	marker := filepath.Join(outside, "marker")
	if err := os.WriteFile(marker, []byte("preserved"), 0600); err != nil {
		t.Fatal(err)
	}
	export, plan, err := PlanProjectExport(source, destination, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	export.writeObservation = func(*exportDirectory, exportObservation) error {
		entries, err := export.destination.entries()
		if err != nil || len(entries) != 1 {
			t.Fatalf("staging entries=%v err=%v", entries, err)
		}
		makeJunction(t, filepath.Join(destination, entries[0].name, "external"), outside)
		return errors.New("injected write failure with junction")
	}
	result := export.Commit(plan.PlanDigest)
	if result.ErrorCode != "EXPORT_STAGING_RETAINED" {
		t.Fatalf("result=%#v", result)
	}
	content, err := os.ReadFile(marker)
	if err != nil || string(content) != "preserved" {
		t.Fatalf("outside target changed: %v", err)
	}
	if _, err := os.Stat(filepath.Join(destination, "portable-copy")); !os.IsNotExist(err) {
		t.Fatalf("failed export published: %v", err)
	}
}

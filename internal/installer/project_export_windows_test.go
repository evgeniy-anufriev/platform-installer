//go:build windows

package installer

import (
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

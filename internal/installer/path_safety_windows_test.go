//go:build windows

package installer

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func makeJunction(t *testing.T, link, target string) {
	t.Helper()
	if output, err := exec.Command("cmd.exe", "/d", "/c", "mklink", "/J", link, target).CombinedOutput(); err != nil {
		t.Skipf("junction creation unavailable: %v (%s)", err, output)
	}
	t.Cleanup(func() { _ = os.Remove(link) })
}

func TestProjectRevisionRejectsWindowsJunctionRoot(t *testing.T) {
	parent, outside := t.TempDir(), t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "project.yml"), []byte("project"), 0o600); err != nil {
		t.Fatal(err)
	}
	junction := filepath.Join(parent, "project")
	makeJunction(t, junction, outside)
	if _, err := ProjectRevision(junction); err == nil || !strings.Contains(err.Error(), "PATH_UNSAFE") {
		t.Fatalf("junction err=%v", err)
	}
}

func TestWriterRejectsJunctionRuntimeDirectory(t *testing.T) {
	root, outside := t.TempDir(), t.TempDir()
	makeJunction(t, filepath.Join(root, ".runtime"), outside)
	if _, err := acquireWriterLock(t.Context(), root, 0); err == nil || !strings.Contains(err.Error(), "PATH_UNSAFE") {
		t.Fatalf("runtime junction err=%v", err)
	}
}

func TestWriterRuntimeACLDoesNotInherit(t *testing.T) {
	root := t.TempDir()
	release, err := acquireWriterLock(t.Context(), root, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer release()
	output, err := exec.Command("icacls.exe", filepath.Join(root, ".runtime", "project-writer.lock")).CombinedOutput()
	if err != nil {
		t.Fatalf("icacls: %v (%s)", err, output)
	}
	if strings.Contains(string(output), "(I)") {
		t.Fatalf("writer lock inherited ACL: %s", output)
	}
}

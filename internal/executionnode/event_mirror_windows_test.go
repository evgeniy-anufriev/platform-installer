package executionnode

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestEventMirrorRejectsWindowsJunctionRuntimeRoot(t *testing.T) {
	parent := t.TempDir()
	outside := t.TempDir()
	junction := filepath.Join(parent, "runtime-junction")
	command := exec.Command("cmd.exe", "/d", "/c", "mklink", "/J", junction, outside)
	if output, err := command.CombinedOutput(); err != nil {
		t.Skipf("junction creation unavailable: %v (%s)", err, output)
	}
	defer os.Remove(junction)
	if _, err := OpenEventMirror(junction, "installer-111", testMirrorFingerprint); err == nil || err.Error() != "EXECUTION_MIRROR_PATH_UNSAFE" {
		t.Fatalf("junction err=%v", err)
	}
}

func TestEventMirrorWindowsJournalDoesNotInheritRuntimeACL(t *testing.T) {
	mirror, err := OpenEventMirror(t.TempDir(), "installer-112", testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer mirror.Close()
	output, err := exec.Command("icacls.exe", mirror.Path()).CombinedOutput()
	if err != nil {
		t.Fatalf("icacls: %v (%s)", err, output)
	}
	if strings.Contains(string(output), "(I)") {
		t.Fatalf("journal inherited ACL: %s", output)
	}
}

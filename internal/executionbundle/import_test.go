package executionbundle

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPrepareRuntimeInputRejectsUnsafeOrMismatchedLocalArtifact(t *testing.T) {
	root := t.TempDir()
	artifact := filepath.Join(root, "kafka.tgz")
	if err := os.WriteFile(artifact, []byte("kafka"), 0o600); err != nil {
		t.Fatal(err)
	}
	bundle := Verified{Root: root}
	if _, _, err := PrepareRuntimeInput(bundle, artifact, "runtime/../escape", "sha256:"+strings.Repeat("a", 64)); err == nil {
		t.Fatal("unsafe artifact ref was accepted")
	}
	if _, _, err := PrepareRuntimeInput(bundle, artifact, "runtime/artifacts/kafka.tgz", "sha256:"+strings.Repeat("a", 64)); err == nil {
		t.Fatal("mismatched artifact was accepted")
	}
}

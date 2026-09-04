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

func TestPrepareRuntimeInputReusesOnlyAnIdenticalImmutableRef(t *testing.T) {
	root := t.TempDir()
	bundleRoot := filepath.Join(root, "bundle")
	existing := filepath.Join(bundleRoot, "runtime", "artifacts", "kafka.tgz")
	if err := os.MkdirAll(filepath.Dir(existing), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(existing, []byte("kafka"), 0o600); err != nil {
		t.Fatal(err)
	}
	source := filepath.Join(root, "source.tgz")
	if err := os.WriteFile(source, []byte("kafka"), 0o600); err != nil {
		t.Fatal(err)
	}
	expected, err := digestPath(source)
	if err != nil {
		t.Fatal(err)
	}
	input, cleanup, err := PrepareRuntimeInput(Verified{Root: bundleRoot}, source, "runtime/artifacts/kafka.tgz", expected)
	if err != nil {
		t.Fatal(err)
	}
	cleanup()
	if input == "" {
		t.Fatal("identical immutable ref did not produce runtime input")
	}
	if err := os.WriteFile(source, []byte("different"), 0o600); err != nil {
		t.Fatal(err)
	}
	different, err := digestPath(source)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := PrepareRuntimeInput(Verified{Root: bundleRoot}, source, "runtime/artifacts/kafka.tgz", different); err == nil || err.Error() != "EXECUTION_ARTIFACT_IMPORT_REF_CONFLICT" {
		t.Fatalf("immutable ref conflict was not rejected: %v", err)
	}
}

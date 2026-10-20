package executionbundle

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestContainerImageIndexRequiresUniqueComponentBoundIdentity(t *testing.T) {
	root := writeBundle(t, validManifest)
	path := filepath.Join(root, "manifest.yaml")
	original, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	entry := "  - reference: example.test/app:1\n    imageId: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n    platform: {os: linux, architecture: amd64}\n    archiveRef: core/capabilities.yml\n"
	// An index cannot designate an arbitrary Core component as an archive.
	if err := os.WriteFile(path, append(original, []byte("containerImages:\n"+entry)...), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateRoot(root); err == nil {
		t.Fatal("accepted non-artifact component")
	}
	if err := os.WriteFile(path, original, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateRoot(root); err != nil {
		t.Fatalf("legacy bundle rejected: %v", err)
	}
}

func TestContainerImageIndexAcceptsVerifiedArtifactAndRejectsDuplicate(t *testing.T) {
	root := writeBundle(t, validManifest)
	archive := filepath.Join(root, "runtime", "artifacts", "app.tar")
	if err := os.MkdirAll(filepath.Dir(archive), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(archive, []byte("---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	entry := "  - reference: example.test/app:1\n    imageId: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n    platform: {os: linux, architecture: amd64}\n    archiveRef: runtime/artifacts/app.tar\n"
	manifest := strings.Replace(validManifest, "core/capabilities.yml", "runtime/artifacts/app.tar", 1) + "containerImages:\n" + entry
	path := filepath.Join(root, "manifest.yaml")
	if err := os.WriteFile(path, []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateRoot(root); err != nil {
		t.Fatalf("valid image index rejected: %v", err)
	}
	if err := os.WriteFile(path, []byte(manifest+entry), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateRoot(root); err == nil {
		t.Fatal("duplicate image identity accepted")
	}
}

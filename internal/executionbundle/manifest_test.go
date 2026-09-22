package executionbundle

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidateRootAcceptsOnlyComponentBoundArtifactSource(t *testing.T) {
	root := t.TempDir()
	artifact := []byte("kafka")
	path := filepath.Join(root, "runtime", "artifacts", "kafka", "kafka.tgz")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, artifact, 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(artifact)
	digest := fmt.Sprintf("sha256:%x", sum)
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\nartifactSources:\n  - serviceType: kafka\n    requirementId: kafka-binary\n    name: kafka\n    version: 4.3.1\n    os: redos\n    architecture: x86_64\n    digest: " + digest + "\n    ref: runtime/artifacts/kafka/kafka.tgz\n    sha256: " + digest + "\n    size: 5\n    type: archive\ncomponents:\n  - path: runtime/artifacts/kafka/kafka.tgz\n    sha256: " + digest + "\n    size: 5\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ValidateRoot(root); err != nil {
		t.Fatal(err)
	}
	for _, broken := range []string{
		strings.Replace(manifest, "runtime/artifacts/kafka/kafka.tgz", "runtime/artifacts/kafka/other.tgz", 1),
		strings.Replace(manifest, "size: 5\n    type: archive", "size: 6\n    type: archive", 1),
		strings.Replace(manifest, "digest: "+digest, "digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1),
		strings.Replace(manifest, "sha256: "+digest+"\n    size: 5\n    type: archive", "sha256: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n    size: 5\n    type: archive", 1),
	} {
		if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(broken), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := ValidateRoot(root); err == nil || err.Error() != "EXECUTION_BUNDLE_ARTIFACT_SOURCE_INVALID" {
			t.Fatalf("err=%v", err)
		}
	}
}

func writeBundle(t *testing.T, manifest string) string {
	t.Helper()
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "core"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "core", "capabilities.yml"), []byte("---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	return root
}

func TestValidateRootAcceptsVerifiedDeterministicBundle(t *testing.T) {
	root := writeBundle(t, "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:f52d711103d50a437830c6fbcd04fb4bab49a0f82f6d26d1c791c6e8488dd090\n    size: 4\n")
	verified, err := ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	if verified.Manifest.BundleVersion != "1" || verified.Digest == "" {
		t.Fatalf("unexpected result: %+v", verified)
	}
	content, err := ReadVerifiedComponent(verified, "core/capabilities.yml", 8)
	if err != nil || string(content) != "---\n" {
		t.Fatalf("content=%q err=%v", content, err)
	}
	if _, err := ReadVerifiedComponent(verified, "core/missing.yml", 8); err == nil || err.Error() != "EXECUTION_BUNDLE_COMPONENT_INVALID" {
		t.Fatalf("err=%v", err)
	}
}

func TestValidateRootRejectsTraversalAndSymlink(t *testing.T) {
	root := writeBundle(t, "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: ../escape\n    sha256: sha256:31b04b2080fa592bb9753d97a60d93a7e0aa30aef2bfcbe6b05e218e7a0a3f76\n    size: 4\n")
	if _, err := ValidateRoot(root); err == nil || err.Error() != "EXECUTION_BUNDLE_COMPONENT_INVALID" {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestReadVerifiedComponentRejectsReplacementBySymlink(t *testing.T) {
	root := writeBundle(t, "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:f52d711103d50a437830c6fbcd04fb4bab49a0f82f6d26d1c791c6e8488dd090\n    size: 4\n")
	verified, err := ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	component := filepath.Join(root, "core", "capabilities.yml")
	if err := os.Remove(component); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(root, "manifest.yaml"), component); err != nil {
		t.Skipf("symlink creation is unavailable: %v", err)
	}
	if _, err := ReadVerifiedComponent(verified, "core/capabilities.yml", 8); err == nil {
		t.Fatal("reparse replacement was accepted")
	}
}

func TestReadVerifiedComponentRejectsOpenedRootIdentityReplacement(t *testing.T) {
	root := writeBundle(t, "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:f52d711103d50a437830c6fbcd04fb4bab49a0f82f6d26d1c791c6e8488dd090\n    size: 4\n")
	verified, err := ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	moved := root + "-moved"
	if err := os.Rename(root, moved); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "core"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "core", "capabilities.yml"), []byte("---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadVerifiedComponent(verified, "core/capabilities.yml", 8); err == nil {
		t.Fatal("replacement root identity was accepted")
	}
}

package executionbundle

import (
	"os"
	"path/filepath"
	"testing"
)

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
}

func TestValidateRootRejectsTraversalAndSymlink(t *testing.T) {
	root := writeBundle(t, "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: ../escape\n    sha256: sha256:31b04b2080fa592bb9753d97a60d93a7e0aa30aef2bfcbe6b05e218e7a0a3f76\n    size: 4\n")
	if _, err := ValidateRoot(root); err == nil || err.Error() != "EXECUTION_BUNDLE_COMPONENT_INVALID" {
		t.Fatalf("unexpected error: %v", err)
	}
}

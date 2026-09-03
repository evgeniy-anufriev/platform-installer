package executionbundle

import (
	"os"
	"path/filepath"
	"testing"
)

const validManifest = "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: '1'\nbootstrapProtocol: v1alpha1\ncoreVersion: '0.1.0'\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nplatforms:\n  - os: redos\n    version: 8.0\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:f52d711103d50a437830c6fbcd04fb4bab49a0f82f6d26d1c791c6e8488dd090\n    size: 4\n"

func TestCachePublishesOnlyVerifiedBundleAndResolvesPlatform(t *testing.T) {
	root := writeBundle(t, validManifest)
	cache := Cache{Root: filepath.Join(t.TempDir(), "execution-node")}
	published, err := cache.Publish(root)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(cache.Root, published.Digest[7:], "manifest.yaml")); err != nil {
		t.Fatal(err)
	}
	resolved, err := cache.Resolve("", Platform{OS: "redos", Version: "8.0", Architecture: "x86_64"})
	if err != nil || resolved.Digest != published.Digest {
		t.Fatalf("%+v %v", resolved, err)
	}
}

func TestCacheDoesNotExposeStagingOrWrongPlatform(t *testing.T) {
	cache := Cache{Root: t.TempDir()}
	if err := os.Mkdir(filepath.Join(cache.Root, ".staging-partial"), 0o700); err != nil {
		t.Fatal(err)
	}
	if _, err := cache.Resolve("", Platform{OS: "redos", Version: "8.0", Architecture: "x86_64"}); err == nil || err.Error() != "EXECUTION_NODE_BUNDLE_MISSING" {
		t.Fatalf("unexpected error: %v", err)
	}
}

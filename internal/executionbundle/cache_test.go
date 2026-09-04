package executionbundle

import (
	"os"
	"path/filepath"
	"strings"
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

func TestCacheRetainsOnlyCurrentDigest(t *testing.T) {
	cache := Cache{Root: filepath.Join(t.TempDir(), "execution-node")}
	first, err := cache.Publish(writeBundle(t, validManifest))
	if err != nil {
		t.Fatal(err)
	}
	second, err := cache.Publish(writeBundle(t, strings.Replace(validManifest, "bundleVersion: '1'", "bundleVersion: '2'", 1)))
	if err != nil {
		t.Fatal(err)
	}
	if first.Digest == second.Digest {
		t.Fatal("test bundles must have distinct digests")
	}
	if _, err := os.Stat(filepath.Join(cache.Root, first.Digest[7:])); !os.IsNotExist(err) {
		t.Fatalf("previous digest remains in cache: %v", err)
	}
	entries, err := os.ReadDir(cache.Root)
	if err != nil || len(entries) != 1 || entries[0].Name() != second.Digest[7:] {
		t.Fatalf("cache entries=%+v err=%v", entries, err)
	}
}

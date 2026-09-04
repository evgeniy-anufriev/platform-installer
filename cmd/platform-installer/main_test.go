package main

import (
	"path/filepath"
	"testing"
)

func TestInsideBundleCache(t *testing.T) {
	cache := filepath.Join(t.TempDir(), "bundle")
	if !insideBundleCache(filepath.Join(cache, "artifacts", "kafka.tgz"), cache) {
		t.Fatal("bundle-local DEV source must be rejected")
	}
	if insideBundleCache(filepath.Join(filepath.Dir(cache), "artifact.tgz"), cache) {
		t.Fatal("external DEV source must be accepted")
	}
}

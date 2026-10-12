package desktop

import (
	"path/filepath"
	"testing"
)

func TestBundleCacheDirectoryUsesExecutableLocation(t *testing.T) {
	executable := filepath.Join("C:", "work", "platform-installer", "build", "bin", "platform-installer-ui.exe")
	want := filepath.Join("C:", "work", "platform-installer", "cache")
	if got := bundleCacheDirectory(executable); got != want {
		t.Fatalf("bundle cache=%q want=%q", got, want)
	}
}

func TestExplicitBundleRootWinsWithoutDiscovery(t *testing.T) {
	if got := resolveBundleRoot(`C:\approved\bundle`); got != `C:\approved\bundle` {
		t.Fatalf("bundle root=%q", got)
	}
}

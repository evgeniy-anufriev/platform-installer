//go:build windows

package desktop

import (
	"crypto/sha256"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBindingGuardRejectsSameBytesAtReplacementPath(t *testing.T) {
	parent := filepath.Join(t.TempDir(), "identity")
	if err := os.Mkdir(parent, 0700); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(parent, "key.pem")
	content := []byte("private-test-identity")
	if err := os.WriteFile(path, content, 0600); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	release, err := holdVerifiedBindingFile(path, info, sha256.Sum256(content), 1024)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Rename(parent, parent+"-moved"); err == nil {
		release()
		t.Fatal("held parent was renamed")
	}
	if err := os.Rename(path, path+"-old"); err == nil {
		release()
		t.Fatal("held identity was renamed")
	}
	release()
	if err := os.Rename(path, path+"-old"); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, content, 0600); err != nil {
		t.Fatal(err)
	}
	if release, err := holdVerifiedBindingFile(path, info, sha256.Sum256(content), 1024); err == nil {
		release()
		t.Fatal("same bytes in different file admitted")
	}
}

func TestUIBindingEffectiveSSHConfigHasNoGlobalTrust(t *testing.T) {
	knownHosts := filepath.Join(t.TempDir(), "known_hosts")
	if err := verifyIsolatedHostKeyConfiguration(knownHosts, "127.0.0.1"); err != nil {
		t.Fatalf("isolated ssh config unavailable: %v", err)
	}
}

func TestSessionKnownHostsRemovedByExactOpenedIdentity(t *testing.T) {
	line := testScannedED25519("192.0.2.10")
	kind, key, _, err := parseScannedHostKey([]byte(line), "192.0.2.10", 22)
	if err != nil {
		t.Fatal(err)
	}
	path, info, dir, dirInfo, digest, err := createSessionKnownHosts("192.0.2.10", 22, kind, key)
	if err != nil {
		t.Fatal(err)
	}
	release, err := holdVerifiedBindingFile(path, info, digest, maxSessionKnownHostsBytes)
	if err != nil {
		t.Fatal(err)
	}
	removeSessionKnownHosts(path, info, dir, dirInfo)
	if _, err := os.Stat(path); err != nil {
		release()
		t.Fatal("active session pin was deleted")
	}
	release()
	removeSessionKnownHosts(path, info, dir, dirInfo)
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("pin retained after safe cleanup: %v", err)
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatalf("private directory retained after safe cleanup: %v", err)
	}
}

func TestSessionKnownHostsFailureDoesNotLeavePrivateDirectory(t *testing.T) {
	// The length gate runs after exclusive directory/file creation.
	before, err := filepath.Glob(filepath.Join(os.TempDir(), "platform-installer-v02-*"))
	if err != nil {
		t.Fatal(err)
	}
	if _, _, _, _, _, err := createSessionKnownHosts("192.0.2.10", 22, "ssh-ed25519", strings.Repeat("A", maxSessionKnownHostsBytes)); err == nil {
		t.Fatal("oversized pin accepted")
	}
	after, err := filepath.Glob(filepath.Join(os.TempDir(), "platform-installer-v02-*"))
	if err != nil {
		t.Fatal(err)
	}
	if len(after) != len(before) {
		t.Fatalf("post-creation failure left a private directory: before=%d after=%d", len(before), len(after))
	}
}

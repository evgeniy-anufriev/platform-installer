package desktop

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"reflect"
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

func TestLateUIBindingConfiguresCredentialLeaseProvider(t *testing.T) {
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	plans := executionnode.NewExecutionService(nil, nil)
	provider := reflect.ValueOf(plans).Elem().FieldByName("credentialProvider")
	if !provider.IsValid() || !provider.IsNil() {
		t.Fatal("new plan service did not start without a provider")
	}
	app.bindDynamicExecutionNode(&executionNodeBinding{dynamic: true, plans: plans})
	if app.binding == nil || app.binding.plans != plans || provider.IsNil() {
		t.Fatal("late UI binding did not register its credential lease provider")
	}
}

func testScannedED25519(host string) string {
	keyType := []byte("ssh-ed25519")
	blob := make([]byte, 4+len(keyType)+4+32)
	binary.BigEndian.PutUint32(blob[:4], uint32(len(keyType)))
	copy(blob[4:], keyType)
	binary.BigEndian.PutUint32(blob[4+len(keyType):], 32)
	copy(blob[8+len(keyType):], bytes.Repeat([]byte{7}, 32))
	return fmt.Sprintf("%s ssh-ed25519 %s\n", host, base64.StdEncoding.EncodeToString(blob))
}

func TestHostKeyScanParserExactHostAndFingerprint(t *testing.T) {
	line := testScannedED25519("[192.0.2.10]:2222")
	kind, key, fingerprint, err := parseScannedHostKey([]byte(line), "192.0.2.10", 2222)
	if err != nil || kind != "ssh-ed25519" || key == "" || !strings.HasPrefix(fingerprint, "SHA256:") {
		t.Fatalf("valid scan rejected: %v", err)
	}
	decoded, _ := base64.StdEncoding.DecodeString(key)
	digest := sha256.Sum256(decoded)
	if fingerprint != "SHA256:"+base64.RawStdEncoding.EncodeToString(digest[:]) {
		t.Fatal("fingerprint does not bind exact key bytes")
	}
	for _, bad := range []string{
		testScannedED25519("192.0.2.11"),
		line + strings.ReplaceAll(line, "ssh-ed25519", "ssh-rsa"),
		"[192.0.2.10]:2222 ssh-ed25519 not-base64\n",
		"[192.0.2.10]:2222 ssh-ed25519 " + base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{1}, 40)) + "\n",
	} {
		if _, _, _, err := parseScannedHostKey([]byte(bad), "192.0.2.10", 2222); err == nil {
			t.Fatalf("invalid scan admitted: %q", bad)
		}
	}
}

func TestExecutionAddressCannotBecomeSSHOption(t *testing.T) {
	for _, bad := range []string{"-Fnone", "host name", "host/other", "host..example", "host\noption"} {
		if validExecutionAddress(bad) {
			t.Fatalf("unsafe address admitted: %q", bad)
		}
	}
	for _, good := range []string{"192.0.2.10", "node1.example.test", "2001:db8::1"} {
		if !validExecutionAddress(good) {
			t.Fatalf("valid address rejected: %q", good)
		}
	}
	for _, bad := range []string{"other@host", "user name", "-oProxyCommand", "user:port"} {
		if executionUsername.MatchString(bad) {
			t.Fatalf("unsafe SSH username admitted: %q", bad)
		}
	}
	if !executionUsername.MatchString("platform-automation") {
		t.Fatal("supported technical user rejected")
	}
}

func TestUIBindingUsesOnlySavedServerAndBlocksDraft(t *testing.T) {
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: "project", Project: &projectlifecycle.Project{ID: "project-a"}, Managed: &installer.ManagedProjectView{Servers: map[string]installer.ManagedServer{"node1": {HostID: "node1", Address: "192.0.2.10"}}}}
	app.execution.bind("project", "project-a", managedSnapshotHosts(app.current.Managed))
	id, address, port, err := app.selectedSavedExecutionServerLocked()
	if err != nil || id != "node1" || address != "192.0.2.10" || port != 22 {
		t.Fatalf("saved server=%q %q %d %v", id, address, port, err)
	}
	app.activeSession = "draft"
	if _, _, _, err := app.selectedSavedExecutionServerLocked(); err == nil {
		t.Fatal("draft-derived server admitted as saved transport")
	}
	app.activeSession = ""
	app.current.Managed.Servers["node1"] = installer.ManagedServer{HostID: "node1", Address: "-oProxyCommand=evil"}
	if _, _, _, err := app.selectedSavedExecutionServerLocked(); err == nil {
		t.Fatal("SSH option address admitted")
	}
}

func TestHostKeyTrustActionsAreBlockedDuringActiveInstallation(t *testing.T) {
	registry := newInstallationRunRegistry()
	registry.rememberRun("installer-active")
	if _, ok := registry.startMonitor("installer-active"); !ok {
		t.Fatal("active run monitor did not start")
	}
	app := &App{installationRuns: registry, secrets: runtimesecret.NewBroker()}
	app.pendingHostKey = &pendingExecutionHostKey{id: "pending-probe"}

	probe := app.ProbeExecutionNodeHostKey()
	if probe.Status != "BLOCKED" || probe.Error == nil || probe.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("probe result=%#v, want active-run block", probe)
	}
	if app.pendingHostKey == nil || app.pendingHostKey.id != "pending-probe" {
		t.Fatal("blocked host-key probe mutated pending trust state")
	}
	decline := app.DeclineExecutionNodeHostKey()
	if decline.Status != "BLOCKED" || decline.Error == nil || decline.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("decline result=%#v, want active-run block", decline)
	}
	if app.pendingHostKey == nil || app.pendingHostKey.id != "pending-probe" {
		t.Fatal("blocked decline mutated pending trust state")
	}
	approve := app.ApproveExecutionNodeHostKey("pending-probe")
	if approve.Status != "BLOCKED" || approve.Error == nil || approve.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("approve result=%#v, want active-run block", approve)
	}
	if app.pendingHostKey == nil || app.pendingHostKey.id != "pending-probe" {
		t.Fatal("blocked approval consumed pending trust state")
	}
	registry.clear()
}

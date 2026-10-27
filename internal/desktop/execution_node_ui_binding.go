package desktop

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"platform-installer/internal/commandwindow"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
)

const maxSessionKnownHostsBytes = 4096

var executionAddressName = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$`)
var executionUsername = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_.-]{0,63}$`)

type HostKeyProbeResult struct {
	Status      string            `json:"status"`
	ProbeID     string            `json:"probeId,omitempty"`
	SafeLabel   string            `json:"safeLabel,omitempty"`
	KeyType     string            `json:"keyType,omitempty"`
	Fingerprint string            `json:"fingerprint,omitempty"`
	Error       *ProjectOpenError `json:"error,omitempty"`
}

type pendingExecutionHostKey struct {
	id, hostID, address, keyType, publicKey, fingerprint string
	port                                                 uint16
	credentialGeneration                                 uint64
	expires                                              time.Time
}

type approvedExecutionHostKey struct {
	knownHosts           string
	fileInfo             os.FileInfo
	directory            string
	directoryInfo        os.FileInfo
	digest               [sha256.Size]byte
	credentialGeneration uint64
}

func hostKeyProbeFailure(code string) HostKeyProbeResult {
	return HostKeyProbeResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

// Host-key trust changes replace the transport binding and its pinned
// known_hosts file. Never allow that while a run still relies on its captured
// binding, even if run-monitor bookkeeping is temporarily unavailable.
func (a *App) activeInstallationTrustLocked() bool {
	return a.startInFlight ||
		a.recoveredRunActiveLocked() ||
		(a.installationRuns != nil && a.installationRuns.hasActiveRun()) ||
		(a.secrets != nil && a.secrets.HasAnyRunExecutionIdentityHold())
}

func validExecutionAddress(value string) bool {
	if net.ParseIP(value) != nil {
		return true
	}
	return !strings.Contains(value, "..") && !strings.HasSuffix(value, ".") && executionAddressName.MatchString(value)
}

func (a *App) selectedSavedExecutionServerLocked() (string, string, uint16, error) {
	if a.current.Status != "OPEN" || a.current.Managed == nil || a.activeSession != "" || a.execution.context.SelectionKind != "PROJECT_SERVER" {
		return "", "", 0, errors.New("BINDING_REQUIRED")
	}
	id := a.execution.context.SelectedHostID
	server, ok := a.current.Managed.Servers[id]
	if !ok || !validExecutionAddress(server.Address) {
		return "", "", 0, errors.New("EXECUTION_NODE_SELECTION_INVALID")
	}
	port := 22
	if server.SSHPort != nil {
		port = *server.SSHPort
	}
	if port < 1 || port > 65535 {
		return "", "", 0, errors.New("EXECUTION_NODE_SELECTION_INVALID")
	}
	return id, server.Address, uint16(port), nil
}

func (a *App) ProbeExecutionNodeHostKey() HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.activeInstallationTrustLocked() && !a.canRenewRecoveredConnectionLocked() {
		return hostKeyProbeFailure("INSTALLATION_RUN_ACTIVE")
	}
	a.pauseRecoveredObservationLocked()
	a.pendingHostKey = nil
	// A probe does not replace an approved pin. Retain the current binding
	// until the operator approves an actually different connection/key.
	id, address, port, err := a.selectedSavedExecutionServerLocked()
	if err != nil {
		return hostKeyProbeFailure(projectErrorCode(err))
	}
	if a.recoveredRunActiveLocked() && (id != a.recoveredRun.NodeID || address != a.recoveredRun.NodeAddress || port != a.recoveredRun.NodePort) {
		return hostKeyProbeFailure("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return hostKeyProbeFailure(projectErrorCode(err))
	}
	identity, err := a.secrets.CurrentExecutionIdentity(binding)
	if err != nil {
		return hostKeyProbeFailure("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	if !executionUsername.MatchString(identity.Username) {
		return hostKeyProbeFailure("EXECUTION_NODE_USER_INVALID")
	}
	ctx, cancel := a.operationContext(9 * time.Second)
	defer cancel()
	keyType, publicKey, fingerprint, err := probeExecutionHostKey(ctx, address, port)
	if err != nil {
		return hostKeyProbeFailure("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
	}
	if a.recoveredRunActiveLocked() && (identity.Username != a.recoveredRun.NodeUser || fingerprint != a.recoveredRun.HostKeyFingerprint) {
		return hostKeyProbeFailure("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return hostKeyProbeFailure("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
	}
	probeID := hex.EncodeToString(nonce)
	a.pendingHostKey = &pendingExecutionHostKey{id: probeID, hostID: id, address: address, port: port, keyType: keyType, publicKey: publicKey, fingerprint: fingerprint, credentialGeneration: identity.Generation, expires: time.Now().Add(2 * time.Minute)}
	return HostKeyProbeResult{Status: "APPROVAL_REQUIRED", ProbeID: probeID, SafeLabel: a.execution.context.SafeLabel, KeyType: keyType, Fingerprint: fingerprint}
}

func (a *App) DeclineExecutionNodeHostKey() HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.activeInstallationTrustLocked() {
		return hostKeyProbeFailure("INSTALLATION_RUN_ACTIVE")
	}
	a.pendingHostKey = nil
	a.invalidateDynamicBindingLocked()
	return HostKeyProbeResult{Status: "DECLINED"}
}

func (a *App) ApproveExecutionNodeHostKey(probeID string) HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.activeInstallationTrustLocked() && !a.canRenewRecoveredConnectionLocked() {
		return hostKeyProbeFailure("INSTALLATION_RUN_ACTIVE")
	}
	pending := a.pendingHostKey
	a.pendingHostKey = nil
	if pending == nil || pending.id != probeID || !time.Now().Before(pending.expires) {
		return hostKeyProbeFailure("EXECUTION_NODE_HOST_KEY_APPROVAL_STALE")
	}
	id, address, port, err := a.selectedSavedExecutionServerLocked()
	if err != nil || id != pending.hostID || address != pending.address || port != pending.port {
		return hostKeyProbeFailure("EXECUTION_NODE_HOST_KEY_APPROVAL_STALE")
	}
	credentialBinding, err := a.credentialBindingLocked()
	if err != nil {
		return hostKeyProbeFailure("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	identity, err := a.secrets.CurrentExecutionIdentity(credentialBinding)
	if err != nil || identity.Generation != pending.credentialGeneration {
		return hostKeyProbeFailure("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	if !executionUsername.MatchString(identity.Username) {
		return hostKeyProbeFailure("EXECUTION_NODE_USER_INVALID")
	}
	if a.recoveredRunActiveLocked() && (id != a.recoveredRun.NodeID || address != a.recoveredRun.NodeAddress || port != a.recoveredRun.NodePort || identity.Username != a.recoveredRun.NodeUser || pending.fingerprint != a.recoveredRun.HostKeyFingerprint) {
		return hostKeyProbeFailure("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	verified, bundleErr := a.verifySelectedBundleLocked()
	if previous := a.binding; previous != nil && previous.dynamic &&
		previous.node.ID == id && previous.node.Address == address && previous.node.Port == port &&
		previous.node.User == identity.Username && previous.credentialGeneration == identity.Generation &&
		previous.node.HostKey.Fingerprint == pending.fingerprint {
		sameRuntime := bundleErr == nil && previous.reader.runtimeRelease["bundleDigest"] == verified.Digest
		if bundleErr != nil && previous.bundleRoot == "" && len(previous.reader.runtimeRelease) == 0 {
			sameRuntime = true // Trust may be confirmed before runtime preparation.
		}
		if sameRuntime {
			if current, err := a.resolveTrustedExecutionConnectionLocked(); err == nil && current == previous {
				return HostKeyProbeResult{Status: "APPROVED", SafeLabel: a.execution.context.SafeLabel,
					KeyType: pending.keyType, Fingerprint: pending.fingerprint}
			}
		}
	}
	knownHosts, fileInfo, directory, directoryInfo, digest, err := createSessionKnownHosts(address, port, pending.keyType, pending.publicKey)
	if err != nil {
		return hostKeyProbeFailure("EXECUTION_NODE_BINDING_INVALID")
	}
	if err := verifyIsolatedHostKeyConfiguration(knownHosts, address); err != nil {
		removeSessionKnownHosts(knownHosts, fileInfo, directory, directoryInfo)
		return hostKeyProbeFailure("EXECUTION_NODE_BINDING_INVALID")
	}
	a.invalidateDynamicBindingLocked()
	pin := approvedExecutionHostKey{knownHosts: knownHosts, fileInfo: fileInfo, directory: directory, directoryInfo: directoryInfo, digest: digest, credentialGeneration: identity.Generation}
	transport := a.executionTransport(identity, credentialBinding, knownHosts, pin.fileInfo, pin.digest)
	guard := transport.CommandGuard
	node := executionnode.Node{ID: id, Address: address, Port: port, User: identity.Username, CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: pending.fingerprint}}
	reader := projectReader{transport: transport, node: node}
	binding := &executionNodeBinding{node: node, reader: reader, service: executionnode.NewService(transport), dynamic: true, credentialGeneration: identity.Generation, hostKeyPin: &pin, commandGuard: guard}
	if bundleErr == nil {
		binding.reader.runtimeRelease = map[string]any{"bundleDigest": verified.Digest, "coreVersion": verified.Manifest.CoreVersion, "catalogDigest": verified.Manifest.CatalogDigest, "planningProtocol": executionbundle.ProtocolVersion}
		binding.plans = executionnode.NewExecutionService(transport, transport)
		binding.bundleRoot = a.availableBundleRoot
		a.reader = binding.reader
	} else {
		a.reader = unavailableProjectReader{}
	}
	a.bindDynamicExecutionNode(binding)
	a.execution.setStatus(executionNodeNotPrepared)
	return HostKeyProbeResult{Status: "APPROVED", SafeLabel: a.execution.context.SafeLabel, KeyType: pending.keyType, Fingerprint: pending.fingerprint}
}

// A UI-selected node is bound after NewApp. Its newly created plan service
// must receive the same runtime-only credential lease provider as a startup
// binding before it can accept a credentialed Start.
func (a *App) bindDynamicExecutionNode(binding *executionNodeBinding) {
	a.binding = binding
	a.configureTargetCredentialLease()
	a.configureTargetHostTrust()
}

func (a *App) verifySelectedBundleLocked() (executionbundle.Verified, error) {
	if a.availableBundleRoot == "" || a.current.Project == nil {
		return executionbundle.Verified{}, errors.New("EXECUTION_BUNDLE_UNAVAILABLE")
	}
	verified, err := executionbundle.ValidateRoot(a.availableBundleRoot)
	if err != nil || verified.Digest != a.current.Project.Source.BundleDigest || verified.Manifest.CatalogDigest != a.current.Project.Source.CatalogDigest {
		return executionbundle.Verified{}, errors.New("EXECUTION_BUNDLE_UNAVAILABLE")
	}
	return verified, nil
}

func (a *App) invalidateDynamicBindingLocked() {
	if a.binding == nil || !a.binding.dynamic {
		return
	}
	pin := a.binding.hostKeyPin
	a.binding = nil
	if pin != nil {
		removeSessionKnownHosts(pin.knownHosts, pin.fileInfo, pin.directory, pin.directoryInfo)
	}
	a.reader = unavailableProjectReader{}
	a.execution.setStatus(executionNodeNotPrepared)
	a.current.Snapshot = nil
	a.current.Verification = notVerified()
	a.continuation = nil
	a.installationPlanID = ""
	a.installationGeneration++
	a.clearRuntimeSecretDescriptorEvidenceLocked()
}

func probeExecutionHostKey(ctx context.Context, address string, port uint16) (string, string, string, error) {
	if !validExecutionAddress(address) || port == 0 {
		return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
	}
	command := exec.CommandContext(ctx, "ssh-keyscan", "-T", "5", "-p", strconv.Itoa(int(port)), "-t", "ed25519,ecdsa,rsa", address)
	commandwindow.Configure(command)
	var output cappedHostKeyOutput
	command.Stdout = &output
	command.Stderr = nil
	if err := command.Run(); err != nil || output.overflow {
		return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
	}
	return parseScannedHostKey(output.Bytes(), address, port)
}

func parseScannedHostKey(output []byte, address string, port uint16) (string, string, string, error) {
	expectedHost := address
	if port != 22 {
		expectedHost = fmt.Sprintf("[%s]:%d", address, port)
	}
	seen := map[string]string{}
	for _, line := range strings.Split(string(output), "\n") {
		fields := strings.Fields(line)
		if len(fields) != 3 || strings.HasPrefix(line, "#") {
			continue
		}
		if fields[0] != expectedHost {
			return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
		}
		kind := fields[1]
		if kind != "ssh-ed25519" && kind != "ecdsa-sha2-nistp256" && kind != "ssh-rsa" {
			continue
		}
		decoded, err := base64.StdEncoding.DecodeString(fields[2])
		if err != nil || len(decoded) < 32 || len(decoded) > 8192 || len(decoded) < 4 || int(binary.BigEndian.Uint32(decoded[:4])) != len(kind) || len(decoded) < 4+len(kind) || string(decoded[4:4+len(kind)]) != kind {
			return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
		}
		if previous, exists := seen[kind]; exists && previous != fields[2] {
			return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
		}
		seen[kind] = fields[2]
	}
	for _, kind := range []string{"ssh-ed25519", "ecdsa-sha2-nistp256", "ssh-rsa"} {
		if key, ok := seen[kind]; ok {
			decoded, _ := base64.StdEncoding.DecodeString(key)
			digest := sha256.Sum256(decoded)
			return kind, key, "SHA256:" + base64.RawStdEncoding.EncodeToString(digest[:]), nil
		}
	}
	return "", "", "", errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
}

type cappedHostKeyOutput struct {
	bytes.Buffer
	overflow bool
	limit    int
}

func (b *cappedHostKeyOutput) Write(p []byte) (int, error) {
	limit := b.limit
	if limit == 0 {
		limit = 16384
	}
	if b.Len()+len(p) > limit {
		b.overflow = true
		return 0, errors.New("EXECUTION_NODE_HOST_KEY_PROBE_FAILED")
	}
	return b.Buffer.Write(p)
}

func createSessionKnownHosts(address string, port uint16, kind, key string) (string, os.FileInfo, string, os.FileInfo, [sha256.Size]byte, error) {
	var empty [sha256.Size]byte
	root, err := os.MkdirTemp("", "platform-installer-v02-")
	if err != nil {
		return "", nil, "", nil, empty, err
	}
	var directoryInfo, fileInfo os.FileInfo
	success := false
	name := filepath.Join(root, "known_hosts")
	defer func() {
		if success || directoryInfo == nil {
			return
		}
		if fileInfo != nil {
			removeSessionKnownHosts(name, fileInfo, root, directoryInfo)
		} else {
			removeSessionDirectory(root, directoryInfo)
		}
	}()
	dir, err := os.Open(root)
	if err != nil {
		return "", nil, "", nil, empty, err
	}
	directoryInfo, err = dir.Stat()
	if err != nil {
		_ = dir.Close()
		return "", nil, "", nil, empty, err
	}
	if err = hardenBindingPath(dir); err != nil {
		_ = dir.Close()
		return "", nil, "", nil, empty, err
	}
	_ = dir.Close()
	file, err := os.OpenFile(name, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return "", nil, "", nil, empty, err
	}
	defer file.Close()
	fileInfo, err = file.Stat()
	if err != nil {
		return "", nil, "", nil, empty, err
	}
	if err = hardenBindingPath(file); err != nil {
		return "", nil, "", nil, empty, err
	}
	host := address
	if port != 22 {
		host = fmt.Sprintf("[%s]:%d", address, port)
	}
	content := []byte(host + " " + kind + " " + key + "\n")
	if len(content) > maxSessionKnownHostsBytes {
		return "", nil, "", nil, empty, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	if _, err = file.Write(content); err != nil {
		return "", nil, "", nil, empty, err
	}
	if err = file.Sync(); err != nil {
		return "", nil, "", nil, empty, err
	}
	info, err := file.Stat()
	if err != nil {
		return "", nil, "", nil, empty, err
	}
	success = true
	return name, info, root, directoryInfo, sha256.Sum256(content), nil
}

func verifyIsolatedHostKeyConfiguration(knownHosts, address string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	args := []string{"-G", "-F", "none", "-o", "GlobalKnownHostsFile=none", "-o", "KnownHostsCommand=none", "-o", "UpdateHostKeys=no", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + knownHosts, address}
	command := exec.CommandContext(ctx, "ssh", args...)
	commandwindow.Configure(command)
	var output cappedHostKeyOutput
	output.limit = 65536
	command.Stdout = &output
	if err := command.Run(); err != nil || output.overflow {
		return errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	settings := map[string]string{}
	for _, line := range strings.Split(output.String(), "\n") {
		parts := strings.SplitN(line, " ", 2)
		if len(parts) == 2 {
			settings[strings.ToLower(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	if settings["globalknownhostsfile"] != "none" || settings["userknownhostsfile"] != knownHosts || settings["stricthostkeychecking"] != "true" || (settings["knownhostscommand"] != "" && settings["knownhostscommand"] != "none") {
		return errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	return nil
}

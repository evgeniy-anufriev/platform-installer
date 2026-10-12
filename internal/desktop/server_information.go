package desktop

import (
	"crypto/rand"
	"encoding/hex"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
	"time"
)

type serverInformationProbe struct {
	id, root, projectID, revision, hostID, address, keyType, publicKey, fingerprint string
	port                                                                            uint16
	identity                                                                        runtimesecret.ExecutionIdentity
	expires                                                                         time.Time
	execution                                                                       bool
}

type ServerInformationResult struct {
	Status      string                           `json:"status"`
	HostID      string                           `json:"hostId,omitempty"`
	Information *executionnode.ServerInformation `json:"information,omitempty"`
	Error       *ProjectOpenError                `json:"error,omitempty"`
}

func informationFailure(hostID string) ServerInformationResult {
	return ServerInformationResult{Status: "UNAVAILABLE", HostID: hostID, Error: &ProjectOpenError{Code: "SERVER_INFORMATION_UNAVAILABLE", Message: "Не удалось проверить сервер. Проверьте доступность узла, учётные данные SSH-сеанса и подтверждённый SSH-ключ."}}
}

func informationStageFailure(hostID, code string) ServerInformationResult {
	result := informationFailure(hostID)
	result.Error.Code = code
	return result
}

func (a *App) ProbeServerInformation(hostID string) HostKeyProbeResult {
	a.editMu.Lock()
	a.pendingServerInformation = nil
	address, port, revision, err := a.savedTargetServerLocked(hostID)
	if err != nil {
		a.editMu.Unlock()
		return hostKeyProbeFailure(projectErrorCode(err))
	}
	credentialBinding, err := a.credentialBindingLocked()
	if err != nil {
		a.editMu.Unlock()
		return hostKeyProbeFailure("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	identity, err := a.secrets.CurrentExecutionIdentity(credentialBinding)
	if err != nil {
		a.editMu.Unlock()
		return hostKeyProbeFailure("SESSION_CREDENTIAL_UNAVAILABLE")
	}
	p := &serverInformationProbe{root: a.current.Root, projectID: a.current.Project.ID, revision: revision, hostID: hostID, address: address, port: port, identity: identity, execution: a.execution.context.SelectedHostID == hostID, expires: time.Now().Add(2 * time.Minute)}
	// Reserve this request before network I/O. React StrictMode or another
	// dialog may start a newer probe while the first keyscan is still running.
	a.pendingServerInformation = p
	a.editMu.Unlock()
	var result HostKeyProbeResult
	var keyType, publicKey, fingerprint string
	if p.execution {
		result = a.ProbeExecutionNodeHostKey()
		if result.Status != "APPROVAL_REQUIRED" {
			return result
		}
	} else {
		ctx, cancel := a.operationContext(9 * time.Second)
		defer cancel()
		keyType, publicKey, fingerprint, err = probeExecutionHostKey(ctx, address, port)
		if err != nil {
			return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
		}
		var token [16]byte
		if _, err = rand.Read(token[:]); err != nil {
			return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
		}
		result = HostKeyProbeResult{Status: "APPROVAL_REQUIRED", ProbeID: hex.EncodeToString(token[:]), SafeLabel: hostID + " · " + address, KeyType: keyType, Fingerprint: fingerprint}
	}
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.pendingServerInformation != p || !a.serverInformationProbeCurrentLocked(p) {
		return hostKeyProbeFailure("TARGET_HOST_KEY_APPROVAL_STALE")
	}
	p.id = result.ProbeID
	p.keyType, p.publicKey, p.fingerprint = keyType, publicKey, fingerprint
	if p.execution {
		pending := a.pendingHostKey
		if pending == nil || pending.id != p.id || pending.hostID != p.hostID || pending.address != p.address || pending.port != p.port {
			return hostKeyProbeFailure("TARGET_HOST_KEY_APPROVAL_STALE")
		}
		p.keyType, p.publicKey, p.fingerprint = pending.keyType, pending.publicKey, pending.fingerprint
	}
	a.pendingServerInformation = p
	return result
}

func (a *App) serverInformationProbeCurrentLocked(p *serverInformationProbe) bool {
	if a.current.Project == nil || a.current.Root != p.root || a.current.Project.ID != p.projectID {
		return false
	}
	address, port, revision, err := a.savedTargetServerLocked(p.hostID)
	if err != nil || address != p.address || port != p.port || revision != p.revision {
		return false
	}
	identity, err := a.secrets.CurrentExecutionIdentity(runtimesecret.Binding{Root: p.root, ID: p.projectID})
	return err == nil && sameTransportIdentity(identity, p.identity)
}

// CheckServerInformation confirms one pinned key for information and installation.
// Installation still requires its independently reviewed and approved Core plan.
func (a *App) CheckServerInformation(probeID string) ServerInformationResult {
	a.editMu.Lock()
	p := a.pendingServerInformation
	a.pendingServerInformation = nil
	if p == nil || p.id != probeID || !time.Now().Before(p.expires) || !a.serverInformationProbeCurrentLocked(p) {
		a.editMu.Unlock()
		return informationStageFailure("", "SERVER_INFORMATION_APPROVAL_STALE")
	}
	a.editMu.Unlock()
	var transport executionnode.OpenSSHTransport
	var node executionnode.Node
	if p.execution {
		if a.ApproveExecutionNodeHostKey(probeID).Status != "APPROVED" {
			return informationStageFailure(p.hostID, "SERVER_INFORMATION_EXEC_APPROVAL_FAILED")
		}
		a.editMu.Lock()
		binding, err := a.resolveTrustedExecutionConnectionLocked()
		if err != nil {
			a.editMu.Unlock()
			return informationStageFailure(p.hostID, "SERVER_INFORMATION_EXEC_BINDING_FAILED")
		}
		var ok bool
		transport, ok = binding.reader.transport.(executionnode.OpenSSHTransport)
		node = binding.node
		a.editMu.Unlock()
		if !ok {
			return informationFailure(p.hostID)
		}
	} else {
		known, file, directory, directoryInfo, digest, err := createSessionKnownHosts(p.address, p.port, p.keyType, p.publicKey)
		if err != nil {
			return informationStageFailure(p.hostID, "SERVER_INFORMATION_PIN_FAILED")
		}
		defer removeSessionKnownHosts(known, file, directory, directoryInfo)
		if verifyIsolatedHostKeyConfiguration(known, p.address) != nil {
			return informationStageFailure(p.hostID, "SERVER_INFORMATION_SSH_CONFIGURATION_FAILED")
		}
		transport = a.executionTransport(p.identity, runtimesecret.Binding{Root: p.root, ID: p.projectID}, known, file, digest)
		node = executionnode.Node{ID: p.hostID, Address: p.address, Port: p.port, User: p.identity.Username, CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: known, Fingerprint: p.fingerprint}}
	}
	ctx, cancel := a.operationContext(20 * time.Second)
	defer cancel()
	info, err := transport.ReadServerInformation(ctx, node)
	if err != nil {
		return informationStageFailure(p.hostID, err.Error())
	}
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if !a.serverInformationProbeCurrentLocked(p) {
		return informationStageFailure(p.hostID, "SERVER_INFORMATION_BINDING_CHANGED")
	}
	if a.approvedTargetHostKeys == nil {
		a.approvedTargetHostKeys = make(map[string]approvedTargetHostKey)
	}
	a.approvedTargetHostKeys[p.hostID] = approvedTargetHostKey{root: p.root, projectID: p.projectID, revision: p.revision, hostID: p.hostID, address: p.address, port: p.port, keyType: p.keyType, publicKey: p.publicKey, fingerprint: p.fingerprint}
	return ServerInformationResult{Status: "CHECKED", HostID: p.hostID, Information: &info}
}

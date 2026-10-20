package desktop

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"time"

	"platform-installer/internal/executionnode"
)

// These approvals exist only in this application session. A saved project
// revision, server endpoint, or project-open lifecycle change makes them stale.
type pendingTargetHostKey struct {
	id, root, projectID, revision, hostID, address string
	port                                           uint16
	keyType, publicKey, fingerprint                string
	expires                                        time.Time
}

type approvedTargetHostKey struct {
	root, projectID, revision, hostID, address string
	port                                       uint16
	keyType, publicKey, fingerprint            string
}

func (a *App) savedTargetServerLocked(hostID string) (string, uint16, string, error) {
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Managed == nil || a.activeSession != "" {
		return "", 0, "", errors.New("TARGET_HOST_TRUST_PROJECT_UNAVAILABLE")
	}
	server, ok := a.current.Managed.Servers[hostID]
	if !ok || server.HostID != hostID || !validExecutionAddress(server.Address) {
		return "", 0, "", errors.New("TARGET_HOST_TRUST_SERVER_INVALID")
	}
	port := 22
	if server.SSHPort != nil {
		port = *server.SSHPort
	}
	if port < 1 || port > 65535 {
		return "", 0, "", errors.New("TARGET_HOST_TRUST_SERVER_INVALID")
	}
	revision, err := a.projectRevision(a.current.Root)
	if err != nil || revision == "" || revision != a.current.Managed.ProjectRevision {
		return "", 0, "", errors.New("TARGET_HOST_TRUST_PROJECT_STALE")
	}
	return server.Address, uint16(port), revision, nil
}

func (a *App) ProbeTargetHostKey(hostID string) HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.pendingTargetHostKey = nil
	delete(a.approvedTargetHostKeys, hostID)
	address, port, revision, err := a.savedTargetServerLocked(hostID)
	if err != nil {
		return hostKeyProbeFailure(projectErrorCode(err))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || a.execution.context.Status != "READY" {
		return hostKeyProbeFailure("EXECUTION_NODE_READY_REQUIRED")
	}
	prober, ok := binding.reader.transport.(interface {
		ProbeTargetHostKey(context.Context, executionnode.Node, string, uint16) ([]byte, error)
	})
	if !ok {
		return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
	}
	ctx, cancel := a.operationContext(9 * time.Second)
	defer cancel()
	output, err := prober.ProbeTargetHostKey(ctx, binding.node, address, port)
	if err != nil {
		return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
	}
	keyType, publicKey, fingerprint, err := parseScannedHostKey(output, address, port)
	if err != nil {
		return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
	}
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return hostKeyProbeFailure("TARGET_HOST_KEY_PROBE_FAILED")
	}
	probeID := hex.EncodeToString(nonce)
	a.pendingTargetHostKey = &pendingTargetHostKey{
		id: probeID, root: a.current.Root, projectID: a.current.Project.ID,
		revision: revision, hostID: hostID, address: address, port: port,
		keyType: keyType, publicKey: publicKey, fingerprint: fingerprint,
		expires: time.Now().Add(2 * time.Minute),
	}
	return HostKeyProbeResult{Status: "APPROVAL_REQUIRED", ProbeID: probeID,
		SafeLabel: fmt.Sprintf("%s · %s:%d", hostID, address, port),
		KeyType:   keyType, Fingerprint: fingerprint}
}

func (a *App) DeclineTargetHostKey() HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.pendingTargetHostKey = nil
	return HostKeyProbeResult{Status: "DECLINED"}
}

func (a *App) ApproveTargetHostKey(probeID string) HostKeyProbeResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	pending := a.pendingTargetHostKey
	a.pendingTargetHostKey = nil
	if pending == nil || pending.id != probeID || !time.Now().Before(pending.expires) || a.current.Root != pending.root || a.current.Project == nil || a.current.Project.ID != pending.projectID {
		return hostKeyProbeFailure("TARGET_HOST_KEY_APPROVAL_STALE")
	}
	address, port, revision, err := a.savedTargetServerLocked(pending.hostID)
	if err != nil || address != pending.address || port != pending.port || revision != pending.revision {
		return hostKeyProbeFailure("TARGET_HOST_KEY_APPROVAL_STALE")
	}
	a.approvedTargetHostKeys[pending.hostID] = approvedTargetHostKey{
		root: pending.root, projectID: pending.projectID, revision: pending.revision,
		hostID: pending.hostID, address: address, port: port,
		keyType: pending.keyType, publicKey: pending.publicKey, fingerprint: pending.fingerprint,
	}
	return HostKeyProbeResult{Status: "APPROVED", SafeLabel: fmt.Sprintf("%s · %s:%d", pending.hostID, address, port),
		KeyType: pending.keyType, Fingerprint: pending.fingerprint}
}

func (a *App) configureTargetHostTrust() {
	if a.binding == nil || a.binding.plans == nil {
		return
	}
	stager, ok := a.binding.reader.transport.(executionnode.TargetHostTrustStager)
	if !ok {
		return
	}
	a.binding.plans.ConfigureTargetHostTrust(a.approvedTargetKeysForPlan, stager)
}

func (a *App) approvedTargetKeysForPlan(plan executionnode.DeploymentPlan) ([]executionnode.TargetHostKeyApproval, error) {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	targets := map[string]bool{}
	for _, phase := range plan.Phases {
		for _, action := range phase.Actions {
			for _, hostID := range action.Targets {
				targets[hostID] = true
			}
		}
	}
	ids := make([]string, 0, len(targets))
	for hostID := range targets {
		ids = append(ids, hostID)
	}
	sort.Strings(ids)
	return a.approvedTargetKeysForHostsLocked(plan.ProjectIdentity, plan.ProjectRevision, ids)
}

func (a *App) approvedTargetKeysForHostsLocked(projectID, revision string, ids []string) ([]executionnode.TargetHostKeyApproval, error) {
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Managed == nil || a.activeSession != "" || a.current.Project.ID != projectID {
		return nil, errors.New("TARGET_HOST_TRUST_REQUIRED")
	}
	currentRevision, err := a.projectRevision(a.current.Root)
	if err != nil || currentRevision != revision || a.current.Managed.ProjectRevision != revision {
		return nil, errors.New("TARGET_HOST_TRUST_STALE")
	}
	if len(ids) == 0 || len(ids) > 256 {
		return nil, errors.New("TARGET_HOST_TRUST_INVALID")
	}
	result := make([]executionnode.TargetHostKeyApproval, 0, len(ids))
	for _, hostID := range ids {
		pin, ok := a.approvedTargetHostKeys[hostID]
		if !ok || pin.root != a.current.Root || pin.projectID != projectID || pin.revision != revision {
			return nil, errors.New("TARGET_HOST_TRUST_REQUIRED")
		}
		address, port, _, err := a.savedTargetServerLocked(hostID)
		if err != nil || address != pin.address || port != pin.port {
			return nil, errors.New("TARGET_HOST_TRUST_STALE")
		}
		result = append(result, executionnode.TargetHostKeyApproval{HostID: hostID, Address: address, Port: int(port), KeyType: pin.keyType, PublicKey: pin.publicKey})
	}
	return result, nil
}

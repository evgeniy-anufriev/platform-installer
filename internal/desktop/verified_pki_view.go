package desktop

import (
	"errors"
	"net"
	"regexp"
	"sort"
	"strings"

	"platform-installer/internal/coreadapter"
)

const (
	maxVerifiedPKIIdentities = 64
	maxVerifiedPKIConsumers  = 4096
	maxVerifiedPKISANs       = 64
	maxVerifiedPKIValue      = 253
)

var verifiedPKISafeName = regexp.MustCompile(`^[A-Za-z0-9*._-]+$`)
var verifiedPKIIdentityID = regexp.MustCompile(`^[a-z][a-z0-9._-]*$`)

// VerifiedPKIView is an in-memory, read-only presentation projection of
// revision-bound Core PKI evidence. It is never desired state or Save input.
type VerifiedPKIView struct {
	Status            string                        `json:"status"`
	Identities        []VerifiedCertificateIdentity `json:"identities,omitempty"`
	Findings          []VerificationFinding         `json:"findings,omitempty"`
	FindingsTruncated bool                          `json:"findingsTruncated,omitempty"`
	Error             *ProjectOpenError             `json:"error,omitempty"`
}

type VerifiedCertificateIdentity struct {
	ID           string                `json:"id"`
	Scope        string                `json:"scope"`
	TLSProfileID string                `json:"tlsProfileId"`
	DNSNames     []string              `json:"dnsNames"`
	IPAddresses  []string              `json:"ipAddresses"`
	Consumers    []VerifiedPKIConsumer `json:"consumers"`
}

type VerifiedPKIConsumer struct {
	DeploymentID string `json:"deploymentId"`
	MemberID     string `json:"memberId"`
	HostID       string `json:"hostId"`
}

// GetVerifiedPKIView exposes only current, attested Core PKI identity/SAN
// evidence. It deliberately cannot initiate verification or contact a node.
func (a *App) GetVerifiedPKIView() VerifiedPKIView {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	return a.verifiedPKIViewLocked()
}

func (a *App) verifiedPKIViewLocked() VerifiedPKIView {
	verification := a.current.Verification
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return verifiedPKIUnavailable("PROJECT_NOT_OPEN")
	}
	if a.activeSession != "" {
		return VerifiedPKIView{Status: "STALE"}
	}
	if verification.Status == "INVALID" {
		return VerifiedPKIView{Status: "INVALID", Findings: append([]VerificationFinding(nil), verification.Findings...), FindingsTruncated: verification.FindingsTruncated}
	}
	if verification.Status == "STALE" {
		return VerifiedPKIView{Status: "STALE"}
	}
	if verification.Status != "VERIFIED" {
		if verification.Status == "UNVERIFIED" || verification.Status == "" {
			return VerifiedPKIView{Status: "NOT_VERIFIED"}
		}
		return VerifiedPKIView{Status: "UNAVAILABLE", Error: verification.Error}
	}
	if a.current.Managed == nil || a.current.Snapshot == nil ||
		verification.ProjectIdentity != a.current.Project.ID ||
		verification.ProjectRevision == "" ||
		verification.ProjectRevision != a.current.Managed.ProjectRevision ||
		verification.ProjectRevision != a.current.Snapshot.ProjectRevision ||
		verification.ExecutionNodeID == "" || verification.Runtime == nil {
		return VerifiedPKIView{Status: "STALE"}
	}
	if a.binding == nil || a.binding.node.ID == "" ||
		a.execution.context.SelectionKind != "EXPLICIT_EXTERNAL" ||
		a.execution.external == nil || a.execution.external.hostID != a.binding.node.ID ||
		verification.ExecutionNodeID != a.binding.node.ID ||
		!runtimeEvidenceMatchesExpected(*verification.Runtime, a.binding.reader.runtimeRelease) {
		return VerifiedPKIView{Status: "STALE"}
	}
	if a.current.Snapshot.Status != "PASS" || a.current.Snapshot.Partial {
		return verifiedPKIUnavailable("VERIFIED_PKI_SNAPSHOT_INVALID")
	}
	view, err := buildVerifiedPKIView(a.current.Snapshot)
	if err != nil {
		return verifiedPKIUnavailable("VERIFIED_PKI_VIEW_UNAVAILABLE")
	}
	return view
}

func verifiedPKIUnavailable(code string) VerifiedPKIView {
	return VerifiedPKIView{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: code, Message: "Не удалось безопасно подготовить read-only представление PKI."}}
}

func buildVerifiedPKIView(snapshot *coreadapter.Snapshot) (VerifiedPKIView, error) {
	if snapshot == nil || len(snapshot.PKI) == 0 {
		return VerifiedPKIView{}, errVerifiedPKIView
	}
	status, ok := snapshot.PKI["status"].(string)
	identities, okIdentities := snapshot.PKI["certificateIdentities"].([]any)
	if !ok || status != "PASS" || !okIdentities || len(identities) > maxVerifiedPKIIdentities {
		return VerifiedPKIView{}, errVerifiedPKIView
	}
	view := VerifiedPKIView{Status: "CURRENT", Identities: make([]VerifiedCertificateIdentity, 0, len(identities))}
	for _, raw := range identities {
		identity, err := verifiedPKIIdentity(raw)
		if err != nil {
			return VerifiedPKIView{}, errVerifiedPKIView
		}
		view.Identities = append(view.Identities, identity)
	}
	sort.Slice(view.Identities, func(i, j int) bool { return view.Identities[i].ID < view.Identities[j].ID })
	return view, nil
}

func verifiedPKIIdentity(raw any) (VerifiedCertificateIdentity, error) {
	value, ok := object(raw)
	if !ok {
		return VerifiedCertificateIdentity{}, errVerifiedPKIView
	}
	id, validID := requiredString(value, "id", maxEndpointPreviewIdentifierLength)
	tlsProfileID, validProfile := requiredString(value, "tlsProfileId", maxEndpointPreviewIdentifierLength)
	scope, validScope := value["scope"].(string)
	dnsNames, dnsOK := verifiedPKIDNSNames(value["dnsNames"])
	ipAddresses, ipOK := verifiedPKIIPAddresses(value["ipAddresses"])
	consumers, consumersOK := verifiedPKIConsumers(value["consumers"])
	if !validID || !verifiedPKIIdentityID.MatchString(id) || !validProfile || !validPreviewIdentifier(tlsProfileID) || !validScope ||
		(scope != "HOST" && scope != "MEMBER" && scope != "DEPLOYMENT") || !dnsOK || !ipOK || !consumersOK {
		return VerifiedCertificateIdentity{}, errVerifiedPKIView
	}
	return VerifiedCertificateIdentity{ID: id, Scope: scope, TLSProfileID: tlsProfileID, DNSNames: dnsNames, IPAddresses: ipAddresses, Consumers: consumers}, nil
}

func verifiedPKIDNSNames(raw any) ([]string, bool) {
	values, ok := array(raw)
	if !ok || len(values) > maxVerifiedPKISANs {
		return nil, false
	}
	result := make([]string, 0, len(values))
	for _, raw := range values {
		value, ok := raw.(string)
		if !ok || len(value) == 0 || len(value) > maxVerifiedPKIValue || !verifiedPKISafeName.MatchString(value) {
			return nil, false
		}
		result = append(result, value)
	}
	return result, true
}

func verifiedPKIIPAddresses(raw any) ([]string, bool) {
	values, ok := array(raw)
	if !ok || len(values) > maxVerifiedPKISANs {
		return nil, false
	}
	result := make([]string, 0, len(values))
	for _, raw := range values {
		value, ok := raw.(string)
		if !ok || len(value) == 0 || len(value) > maxVerifiedPKIValue || net.ParseIP(value) == nil {
			return nil, false
		}
		result = append(result, value)
	}
	return result, true
}

func verifiedPKIConsumers(raw any) ([]VerifiedPKIConsumer, bool) {
	values, ok := array(raw)
	if !ok || len(values) > maxVerifiedPKIConsumers {
		return nil, false
	}
	result := make([]VerifiedPKIConsumer, 0, len(values))
	for _, raw := range values {
		value, ok := object(raw)
		deploymentID, deploymentOK := requiredString(value, "deploymentId", maxEndpointPreviewIdentifierLength)
		memberID, memberOK := requiredString(value, "memberId", maxEndpointPreviewIdentifierLength)
		hostID, hostOK := requiredString(value, "hostId", maxEndpointPreviewIdentifierLength)
		if !ok || !deploymentOK || !memberOK || !hostOK || !validPreviewIdentifier(deploymentID) || !validPreviewIdentifier(memberID) || !validPreviewIdentifier(hostID) {
			return nil, false
		}
		result = append(result, VerifiedPKIConsumer{DeploymentID: deploymentID, MemberID: memberID, HostID: hostID})
	}
	sort.Slice(result, func(i, j int) bool {
		return strings.Join([]string{result[i].DeploymentID, result[i].MemberID, result[i].HostID}, "\x00") < strings.Join([]string{result[j].DeploymentID, result[j].MemberID, result[j].HostID}, "\x00")
	})
	return result, true
}

var errVerifiedPKIView = errors.New("verified PKI view invalid")

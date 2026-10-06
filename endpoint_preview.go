package main

import (
	"net"
	"regexp"
	"sort"
	"strings"

	"platform-installer/internal/coreadapter"
)

const (
	maxEndpointPreviewSourceItems      = 4096
	maxEndpointPreviewEndpoints        = 64
	maxEndpointPreviewProviders        = 64
	maxEndpointPreviewAddresses        = 64
	maxEndpointPreviewIdentifierLength = 128
	maxEndpointPreviewFQDNLength       = 253
	maxEndpointPreviewInterfaceLength  = 128
)

var (
	endpointPreviewIdentifier = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
	endpointPreviewInterface  = regexp.MustCompile(`^[A-Za-z0-9_.:-]+$`)
)

// EndpointPreview is a bounded, presentation-only view of accepted Core
// evidence. It is not desired state and cannot be supplied to Save.
type EndpointPreview struct {
	Status            string                    `json:"status"`
	Endpoints         []EndpointPreviewEndpoint `json:"endpoints,omitempty"`
	Providers         []EndpointPreviewProvider `json:"providers,omitempty"`
	Findings          []VerificationFinding     `json:"findings,omitempty"`
	FindingsTruncated bool                      `json:"findingsTruncated,omitempty"`
	Truncated         bool                      `json:"truncated,omitempty"`
	Error             *ProjectOpenError         `json:"error,omitempty"`
}

type EndpointPreviewEndpoint struct {
	DeploymentID string `json:"deploymentId"`
	FQDN         string `json:"fqdn"`
}

type EndpointPreviewProvider struct {
	EndpointGroupID      string                          `json:"endpointGroupId"`
	ProviderDeploymentID string                          `json:"providerDeploymentId"`
	EndpointGroupRef     string                          `json:"endpointGroupRef"`
	VirtualRouterID      int                             `json:"virtualRouterId"`
	VirtualAddresses     []EndpointPreviewVirtualAddress `json:"virtualAddresses"`
}

type EndpointPreviewVirtualAddress struct {
	Address   string `json:"address"`
	Interface string `json:"interface"`
}

// GetEndpointPreview exposes only the small safe endpoint/provider projection
// required by UI-01F5. Core snapshot maps never cross this Wails boundary.
func (a *App) GetEndpointPreview() EndpointPreview {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.reconcileEditSessionLocked()
	return a.endpointPreviewLocked()
}

func (a *App) endpointPreviewLocked() EndpointPreview {
	verification := a.current.Verification
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return endpointPreviewUnavailable("PROJECT_NOT_OPEN")
	}
	if a.activeSession != "" {
		return EndpointPreview{Status: "STALE"}
	}
	if verification.Status == "INVALID" {
		return EndpointPreview{Status: "INVALID", Findings: append([]VerificationFinding(nil), verification.Findings...), FindingsTruncated: verification.FindingsTruncated}
	}
	if verification.Status == "STALE" {
		return EndpointPreview{Status: "STALE"}
	}
	if verification.Status != "VERIFIED" {
		if verification.Status == "UNVERIFIED" || verification.Status == "" {
			return EndpointPreview{Status: "NOT_VERIFIED"}
		}
		return EndpointPreview{Status: "UNAVAILABLE", Error: verification.Error}
	}
	if a.current.Managed == nil || a.current.Snapshot == nil ||
		verification.ProjectIdentity != a.current.Project.ID ||
		verification.ProjectRevision == "" ||
		verification.ProjectRevision != a.current.Managed.ProjectRevision ||
		verification.ProjectRevision != a.current.Snapshot.ProjectRevision ||
		verification.ExecutionNodeID == "" || verification.Runtime == nil {
		return EndpointPreview{Status: "STALE"}
	}
	if a.binding == nil || a.binding.node.ID == "" ||
		a.execution.context.SelectionKind != "EXPLICIT_EXTERNAL" ||
		a.execution.external == nil || a.execution.external.hostID != a.binding.node.ID ||
		verification.ExecutionNodeID != a.binding.node.ID {
		return EndpointPreview{Status: "STALE"}
	}
	if a.current.Snapshot.Status != "PASS" || a.current.Snapshot.Partial {
		return endpointPreviewUnavailable("ENDPOINT_PREVIEW_SNAPSHOT_INVALID")
	}
	preview, err := buildEndpointPreview(a.current.Snapshot)
	if err != nil {
		return endpointPreviewUnavailable("ENDPOINT_PREVIEW_UNAVAILABLE")
	}
	return preview
}

func endpointPreviewUnavailable(code string) EndpointPreview {
	return EndpointPreview{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: code, Message: "Не удалось безопасно подготовить read-only представление точек входа."}}
}

func buildEndpointPreview(snapshot *coreadapter.Snapshot) (EndpointPreview, error) {
	if snapshot == nil {
		return EndpointPreview{}, errEndpointPreview
	}
	endpointRoot, ok := object(snapshot.Endpoints["deployments"])
	if !ok || len(endpointRoot) > maxEndpointPreviewSourceItems || len(snapshot.ServiceDeployments) > maxEndpointPreviewSourceItems {
		return EndpointPreview{}, errEndpointPreview
	}
	integrationRoot, ok := object(snapshot.Integrations["addressProvidersByEndpointGroup"])
	if !ok || len(integrationRoot) > maxEndpointPreviewSourceItems {
		return EndpointPreview{}, errEndpointPreview
	}
	preview := EndpointPreview{Status: "CURRENT"}
	endpointIDs := sortedKeys(endpointRoot)
	if len(endpointIDs) > maxEndpointPreviewEndpoints {
		preview.Truncated = true
		endpointIDs = endpointIDs[:maxEndpointPreviewEndpoints]
	}
	for _, deploymentID := range endpointIDs {
		if !validPreviewIdentifier(deploymentID) {
			return EndpointPreview{}, errEndpointPreview
		}
		record, ok := object(endpointRoot[deploymentID])
		fqdn, valid := requiredString(record, "fqdn", maxEndpointPreviewFQDNLength)
		if !ok || !valid || !validPreviewFQDN(fqdn) {
			return EndpointPreview{}, errEndpointPreview
		}
		preview.Endpoints = append(preview.Endpoints, EndpointPreviewEndpoint{DeploymentID: deploymentID, FQDN: fqdn})
	}
	for _, groupID := range sortedKeys(integrationRoot) {
		if !validPreviewIdentifier(groupID) {
			return EndpointPreview{}, errEndpointPreview
		}
		items, ok := array(integrationRoot[groupID])
		if !ok || len(items) > maxEndpointPreviewSourceItems {
			return EndpointPreview{}, errEndpointPreview
		}
		for _, item := range items {
			provider, ok := object(item)
			deploymentID, valid := requiredString(provider, "deploymentId", maxEndpointPreviewIdentifierLength)
			if !ok || !valid || !validPreviewIdentifier(deploymentID) {
				return EndpointPreview{}, errEndpointPreview
			}
			deployment, present := snapshot.ServiceDeployments[deploymentID]
			endpointGroupRef, valid := requiredString(deployment, "endpointGroupRef", maxEndpointPreviewIdentifierLength)
			virtualRouterID, validRouter := previewRouterID(deployment["virtualRouterId"])
			addresses, validAddresses := previewAddresses(provider["virtualAddresses"])
			deploymentAddresses, deploymentAddressesValid := previewAddresses(deployment["virtualAddresses"])
			if !present || !valid || !validPreviewIdentifier(endpointGroupRef) || endpointGroupRef != groupID || !validRouter || !validAddresses || !deploymentAddressesValid || !sameAddresses(addresses, deploymentAddresses) {
				return EndpointPreview{}, errEndpointPreview
			}
			if len(preview.Providers) >= maxEndpointPreviewProviders {
				preview.Truncated = true
				continue
			}
			if len(addresses) > maxEndpointPreviewAddresses {
				preview.Truncated = true
				addresses = addresses[:maxEndpointPreviewAddresses]
			}
			preview.Providers = append(preview.Providers, EndpointPreviewProvider{EndpointGroupID: groupID, ProviderDeploymentID: deploymentID, EndpointGroupRef: endpointGroupRef, VirtualRouterID: virtualRouterID, VirtualAddresses: addresses})
		}
	}
	sort.Slice(preview.Providers, func(i, j int) bool {
		if preview.Providers[i].EndpointGroupID == preview.Providers[j].EndpointGroupID {
			return preview.Providers[i].ProviderDeploymentID < preview.Providers[j].ProviderDeploymentID
		}
		return preview.Providers[i].EndpointGroupID < preview.Providers[j].EndpointGroupID
	})
	return preview, nil
}

var errEndpointPreview = &endpointPreviewError{}

type endpointPreviewError struct{}

func (*endpointPreviewError) Error() string { return "endpoint preview invalid" }

func object(value any) (map[string]any, bool) {
	result, ok := value.(map[string]any)
	return result, ok
}
func array(value any) ([]any, bool) { result, ok := value.([]any); return result, ok }
func sortedKeys(values map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}
func requiredString(values map[string]any, key string, limit int) (string, bool) {
	value, ok := values[key].(string)
	return value, ok && value != "" && len(value) <= limit
}
func validPreviewIdentifier(value string) bool {
	return len(value) <= maxEndpointPreviewIdentifierLength && endpointPreviewIdentifier.MatchString(value)
}
func validPreviewFQDN(value string) bool {
	return len(value) <= maxEndpointPreviewFQDNLength && strings.Contains(value, ".") && !strings.HasPrefix(value, ".") && !strings.HasSuffix(value, ".")
}
func previewRouterID(value any) (int, bool) {
	switch item := value.(type) {
	case float64:
		if item == float64(int(item)) && item >= 1 && item <= 255 {
			return int(item), true
		}
	case int:
		if item >= 1 && item <= 255 {
			return item, true
		}
	case int64:
		if item >= 1 && item <= 255 {
			return int(item), true
		}
	}
	return 0, false
}
func previewAddresses(value any) ([]EndpointPreviewVirtualAddress, bool) {
	items, ok := array(value)
	if !ok || len(items) > maxEndpointPreviewSourceItems {
		return nil, false
	}
	result := make([]EndpointPreviewVirtualAddress, 0, len(items))
	for _, item := range items {
		object, ok := object(item)
		address, addressOK := requiredString(object, "address", 45)
		iface, interfaceOK := requiredString(object, "interface", maxEndpointPreviewInterfaceLength)
		ip := net.ParseIP(address)
		if !ok || !addressOK || !interfaceOK || ip == nil || ip.To4() == nil || !endpointPreviewInterface.MatchString(iface) {
			return nil, false
		}
		result = append(result, EndpointPreviewVirtualAddress{Address: address, Interface: iface})
	}
	return result, true
}
func sameAddresses(left, right []EndpointPreviewVirtualAddress) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

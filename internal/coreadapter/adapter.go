package coreadapter

import (
	"context"
	"encoding/json"
)

// Adapter is the only boundary from Installer application logic to Core.
type Adapter interface {
	BuildSnapshot(ctx context.Context, projectRoot string, installerOwnedPaths []string) (*Snapshot, error)
}

type Document struct {
	LogicalPath      string `json:"logicalPath"`
	Digest           string `json:"digest"`
	Ownership        string `json:"ownership"`
	RevisionIncluded bool   `json:"revisionIncluded"`
}

// Snapshot mirrors only fields consumed by Installer application semantics.
type Snapshot struct {
	Status                 string                                 `json:"status"`
	Partial                bool                                   `json:"partial"`
	Project                map[string]any                         `json:"project"`
	ProjectRevision        string                                 `json:"projectRevision"`
	SnapshotFingerprint    string                                 `json:"snapshotFingerprint"`
	Documents              []Document                             `json:"documents"`
	Hosts                  map[string]map[string]any              `json:"hosts"`
	References             map[string]map[string][]map[string]any `json:"references"`
	ServiceCatalog         map[string]map[string]any              `json:"serviceCatalog"`
	ServiceDeployments     map[string]map[string]any              `json:"serviceDeployments"`
	EffectiveConfiguration map[string]any                         `json:"effectiveConfiguration"`
	EndpointGroups         map[string]any                         `json:"endpointGroups"`
	Topology               map[string]any                         `json:"topology"`
	Endpoints              map[string]any                         `json:"endpoints"`
	Integrations           map[string]any                         `json:"integrations"`
	PKI                    map[string]any                         `json:"pki"`
	Validation             map[string]any                         `json:"validation"`
	Readiness              map[string]any                         `json:"readiness"`
	Findings               []map[string]any                       `json:"findings"`
	Raw                    json.RawMessage                        `json:"-"`
}

func DecodeSnapshot(data []byte) (*Snapshot, error) {
	var snapshot Snapshot
	if err := json.Unmarshal(data, &snapshot); err != nil {
		return nil, err
	}
	snapshot.Raw = append(snapshot.Raw[:0], data...)
	return &snapshot, nil
}

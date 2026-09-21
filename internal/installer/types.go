package installer

import (
	"encoding/json"
	"time"
)

const (
	EditCommandAPIVersion      = "platform.installer/edit-command/v1alpha1"
	EditCommandAPIVersionV2    = "platform.installer/edit-command/v1alpha2"
	EditCommandAPIVersionV3    = "platform.installer/edit-command/v1alpha3"
	EditCommandAPIVersionV4    = "platform.installer/edit-command/v1alpha4"
	EditCommandAPIVersionV5    = "platform.installer/edit-command/v1alpha5"
	EditCommandAPIVersionV6    = "platform.installer/edit-command/v1alpha6"
	EditCommandAPIVersionV7    = "platform.installer/edit-command/v1alpha7"
	EditCommandAPIVersionV8    = "platform.installer/edit-command/v1alpha8"
	EditPlanAPIVersion         = "platform.installer/edit-plan/v1alpha1"
	EditPlanAPIVersionV2       = "platform.installer/edit-plan/v1alpha2"
	EditResultAPIVersion       = "platform.installer/edit-commit-result/v1alpha1"
	EditResultAPIVersionV2     = "platform.installer/edit-commit-result/v1alpha2"
	EditSessionAPIVersion      = "platform.installer/edit-session/v1alpha1"
	StructuralPlanAPIVersion   = "platform.installer/structural-edit-plan/v1alpha1"
	StructuralResultAPIVersion = "platform.installer/structural-save-result/v1alpha1"
)

type EditCommand struct {
	APIVersion          string            `json:"apiVersion,omitempty"`
	Kind                string            `json:"kind,omitempty"`
	BaseProjectRevision string            `json:"baseProjectRevision,omitempty"`
	Operation           string            `json:"operation"`
	DeploymentID        string            `json:"deploymentId,omitempty"`
	Scope               string            `json:"scope,omitempty"`
	MemberID            string            `json:"memberId,omitempty"`
	Setting             string            `json:"setting,omitempty"`
	Value               any               `json:"value,omitempty"`
	EndpointGroupID     string            `json:"endpointGroupId,omitempty"`
	HAProxyDeploymentID string            `json:"haproxyDeploymentId,omitempty"`
	HostID              string            `json:"hostId,omitempty"`
	ServerType          string            `json:"type,omitempty"`
	DesiredHostname     string            `json:"desiredHostname,omitempty"`
	Address             string            `json:"address,omitempty"`
	SSHPort             int               `json:"sshPort,omitempty"`
	ClearSSHPort        bool              `json:"clearSSHPort,omitempty"`
	ServiceType         string            `json:"serviceType,omitempty"`
	Mode                string            `json:"mode,omitempty"`
	EntityID            string            `json:"entityId,omitempty"`
	Entity              map[string]any    `json:"entity,omitempty"`
	Members             []PlacementMember `json:"members,omitempty"`
	Hosts               []PlacementHost   `json:"hosts,omitempty"`
	Property            string            `json:"property,omitempty"`
	Deployment          map[string]any    `json:"deployment,omitempty"`
	EndpointGroup       map[string]any    `json:"endpointGroup,omitempty"`
	VirtualRouterID     int               `json:"virtualRouterId,omitempty"`
	VirtualAddresses    []VirtualAddress  `json:"virtualAddresses,omitempty"`
	Placement           map[string]any    `json:"placement,omitempty"`
	Backend             map[string]any    `json:"backend,omitempty"`
	Commands            []EditCommand     `json:"commands,omitempty"`
	unknownFields       []string
	presentFields       map[string]bool
}

func (command *EditCommand) UnmarshalJSON(content []byte) error {
	type commandAlias EditCommand
	var decoded commandAlias
	if err := json.Unmarshal(content, &decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(content, &fields); err != nil {
		return err
	}
	*command = EditCommand(decoded)
	command.presentFields = make(map[string]bool, len(fields))
	known := map[string]bool{
		"apiVersion": true, "kind": true, "baseProjectRevision": true, "operation": true,
		"deploymentId": true, "scope": true, "memberId": true, "setting": true, "value": true, "endpointGroupId": true,
		"haproxyDeploymentId": true, "hostId": true, "type": true, "desiredHostname": true, "address": true, "sshPort": true,
		"clearSSHPort": true, "serviceType": true, "mode": true, "entityId": true,
		"entity": true, "members": true, "hosts": true, "property": true, "deployment": true,
		"endpointGroup": true, "virtualRouterId": true, "virtualAddresses": true,
		"placement": true, "backend": true, "commands": true,
	}
	for field := range fields {
		command.presentFields[field] = true
		if !known[field] {
			command.unknownFields = append(command.unknownFields, field)
		}
	}
	return nil
}

// VirtualAddress is the one closed provider-address value shared by the
// v1alpha6 command boundary and the directly owned managed-project view.
type VirtualAddress struct {
	Address       string `json:"address"`
	Interface     string `json:"interface"`
	unknownFields []string
}

func (value *VirtualAddress) UnmarshalJSON(content []byte) error {
	type alias VirtualAddress
	var decoded alias
	if err := json.Unmarshal(content, &decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(content, &fields); err != nil {
		return err
	}
	*value = VirtualAddress(decoded)
	for field := range fields {
		if field != "address" && field != "interface" {
			value.unknownFields = append(value.unknownFields, field)
		}
	}
	return nil
}

type PlacementMember struct {
	MemberID      string         `json:"memberId"`
	HostID        string         `json:"hostId"`
	Roles         []string       `json:"roles,omitempty"`
	Configuration map[string]any `json:"configuration,omitempty"`
	unknownFields []string
}

func (value *PlacementMember) UnmarshalJSON(content []byte) error {
	type alias PlacementMember
	var decoded alias
	if err := json.Unmarshal(content, &decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(content, &fields); err != nil {
		return err
	}
	*value = PlacementMember(decoded)
	for field := range fields {
		if field != "memberId" && field != "hostId" && field != "roles" && field != "configuration" {
			value.unknownFields = append(value.unknownFields, field)
		}
	}
	return nil
}

type PlacementHost struct {
	HostID        string   `json:"hostId"`
	Roles         []string `json:"roles,omitempty"`
	unknownFields []string
}

func (value *PlacementHost) UnmarshalJSON(content []byte) error {
	type alias PlacementHost
	var decoded alias
	if err := json.Unmarshal(content, &decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(content, &fields); err != nil {
		return err
	}
	*value = PlacementHost(decoded)
	for field := range fields {
		if field != "hostId" && field != "roles" {
			value.unknownFields = append(value.unknownFields, field)
		}
	}
	return nil
}

type Finding struct {
	APIVersion  string `json:"apiVersion"`
	Kind        string `json:"kind"`
	Code        string `json:"code"`
	Status      string `json:"status"`
	Category    string `json:"category"`
	Field       string `json:"field"`
	SafeMessage string `json:"safeMessage"`
}

type Validation struct {
	Status   string    `json:"status"`
	Findings []Finding `json:"findings"`
}

type DocumentChange struct {
	LogicalPath  string         `json:"logicalPath"`
	BeforeDigest string         `json:"beforeDigest,omitempty"`
	AfterDigest  string         `json:"afterDigest,omitempty"`
	Before       *DocumentState `json:"before,omitempty"`
	After        *DocumentState `json:"after,omitempty"`
}

type DocumentState struct {
	State  string `json:"state"`
	Digest string `json:"digest,omitempty"`
}

type SemanticChange struct {
	Operation   string `json:"operation"`
	EntityID    string `json:"entityId,omitempty"`
	Property    string `json:"property,omitempty"`
	SafeSummary string `json:"safeSummary"`
}

type EditPlan struct {
	APIVersion                  string           `json:"apiVersion"`
	Kind                        string           `json:"kind"`
	Status                      string           `json:"status"`
	PlanID                      string           `json:"planId,omitempty"`
	BaseProjectRevision         string           `json:"baseProjectRevision"`
	CommandSummary              SemanticChange   `json:"commandSummary"`
	SemanticChanges             []SemanticChange `json:"semanticChanges"`
	AffectedEntities            []string         `json:"affectedEntities"`
	AffectedDocuments           []DocumentChange `json:"affectedDocuments"`
	Impacts                     []string         `json:"impacts"`
	Validation                  Validation       `json:"validation"`
	ExpectedEffectiveState      []map[string]any `json:"expectedEffectiveState,omitempty"`
	ExpectedSnapshotFingerprint string           `json:"expectedSnapshotFingerprint,omitempty"`
	ReviewDiff                  string           `json:"reviewDiff"`
	CommitAllowed               bool             `json:"commitAllowed"`
	ApplyRequired               bool             `json:"applyRequired"`
	ExpiresAt                   time.Time        `json:"expiresAt,omitempty"`
	Timing                      PlanTiming       `json:"timing"`
}

// StructuralEditPlan is the local-only preview used by new Installer edit
// sessions. It deliberately contains no Core validation or effective-state
// claims.
type StructuralEditPlan struct {
	APIVersion          string           `json:"apiVersion"`
	Kind                string           `json:"kind"`
	Status              string           `json:"status"`
	Finding             *Finding         `json:"finding,omitempty"`
	PlanID              string           `json:"planId,omitempty"`
	BaseProjectRevision string           `json:"baseProjectRevision"`
	SemanticChanges     []SemanticChange `json:"semanticChanges"`
	AffectedEntities    []string         `json:"affectedEntities"`
	AffectedDocuments   []DocumentChange `json:"affectedDocuments"`
	ReviewDiff          string           `json:"reviewDiff"`
	SaveAllowed         bool             `json:"saveAllowed"`
	ExpiresAt           time.Time        `json:"expiresAt,omitempty"`
}

type StructuralSaveResult struct {
	APIVersion         string              `json:"apiVersion"`
	Kind               string              `json:"kind"`
	Status             string              `json:"status"`
	Changed            bool                `json:"changed"`
	Finding            *Finding            `json:"finding,omitempty"`
	OldProjectRevision string              `json:"oldProjectRevision,omitempty"`
	NewProjectRevision string              `json:"newProjectRevision,omitempty"`
	AffectedDocuments  []DocumentChange    `json:"affectedDocuments,omitempty"`
	Timing             CommitTiming        `json:"timing"`
	Managed            *ManagedProjectView `json:"managed,omitempty"`
}

// ManagedProjectView exposes only Installer-owned canonical fields. It is not
// an Ansible-resolved ProjectSnapshot and exposes only directly owned provider
// fields, never Core-derived endpoint, DNS or PKI semantics.
type ManagedProjectView struct {
	ProjectRevision  string                          `json:"projectRevision"`
	Servers          map[string]ManagedServer        `json:"servers"`
	Deployments      map[string]ManagedDeployment    `json:"deployments"`
	EndpointGroups   map[string]ManagedEndpointGroup `json:"endpointGroups"`
	MemberPlacements []ManagedMemberPlacement        `json:"memberPlacements"`
	HostPlacements   []ManagedHostPlacement          `json:"hostPlacements"`
	PKI              ManagedPKI                      `json:"pki"`
}

// ManagedPKI contains direct Installer-owned desired input only; it never
// represents Core-resolved certificate identity, SAN or runtime material.
type ManagedPKI struct {
	Authorities map[string]map[string]any `json:"authorities"`
	Profiles    map[string]map[string]any `json:"profiles"`
	TLSProfiles map[string]map[string]any `json:"tlsProfiles"`
	Scopes      map[string]map[string]any `json:"scopes"`
}

type ManagedServer struct {
	HostID          string `json:"hostId"`
	Type            string `json:"type,omitempty"`
	DesiredHostname string `json:"desiredHostname,omitempty"`
	Address         string `json:"address,omitempty"`
	SSHPort         *int   `json:"sshPort,omitempty"`
}

type ManagedDeployment struct {
	DeploymentID      string                         `json:"deploymentId"`
	ServiceType       string                         `json:"serviceType"`
	Mode              string                         `json:"mode"`
	EndpointGroup     string                         `json:"endpointGroup,omitempty"`
	EndpointGroupRef  string                         `json:"endpointGroupRef,omitempty"`
	VirtualRouterID   *int                           `json:"virtualRouterId,omitempty"`
	VirtualAddresses  []VirtualAddress               `json:"virtualAddresses,omitempty"`
	ProviderEditState string                         `json:"providerEditState"`
	Configuration     []ManagedConfigurationOverride `json:"configuration"`
}

type ManagedEndpointGroup struct {
	EndpointGroupID string `json:"endpointGroupId"`
	Domain          string `json:"domain"`
	Wildcard        bool   `json:"wildcard"`
}

type ManagedMemberPlacement struct {
	DeploymentID  string                         `json:"deploymentId"`
	MemberID      string                         `json:"memberId"`
	HostID        string                         `json:"hostId"`
	Roles         []string                       `json:"roles"`
	Configuration []ManagedConfigurationOverride `json:"configuration"`
}

// ManagedConfigurationOverride exposes only a stable setting identity and
// override presence until an exact READY catalog descriptor safely admits a
// copied primitive value. Unsupported raw YAML/JSON never crosses this view.
type ManagedConfigurationOverride struct {
	Setting         string `json:"setting"`
	OverridePresent bool   `json:"overridePresent"`
	State           string `json:"state"`
	Value           any    `json:"value,omitempty"`
}

type ManagedHostPlacement struct {
	DeploymentID string   `json:"deploymentId"`
	HostID       string   `json:"hostId"`
	Roles        []string `json:"roles"`
}

type PlanTiming struct {
	Application     time.Duration `json:"application"`
	InitialSnapshot time.Duration `json:"initialSnapshot"`
	StagedSnapshot  time.Duration `json:"stagedSnapshot"`
}

type CommitTiming struct {
	Transaction time.Duration `json:"transaction"`
	Snapshot    time.Duration `json:"snapshot"`
}

type EditCommitResult struct {
	APIVersion         string              `json:"apiVersion"`
	Kind               string              `json:"kind"`
	Status             string              `json:"status"`
	Changed            bool                `json:"changed"`
	Finding            *Finding            `json:"finding,omitempty"`
	OldProjectRevision string              `json:"oldProjectRevision,omitempty"`
	NewProjectRevision string              `json:"newProjectRevision,omitempty"`
	AffectedDocuments  []DocumentChange    `json:"affectedDocuments,omitempty"`
	Snapshot           any                 `json:"snapshot,omitempty"`
	Managed            *ManagedProjectView `json:"managed,omitempty"`
	ApplyRequired      bool                `json:"applyRequired"`
	Discarded          bool                `json:"discarded,omitempty"`
	Timing             CommitTiming        `json:"timing"`
}

type EditSession struct {
	APIVersion            string    `json:"apiVersion"`
	Kind                  string    `json:"kind"`
	SessionID             string    `json:"sessionId"`
	ProjectContextID      string    `json:"projectContextId"`
	ProjectRoot           string    `json:"-"`
	ProjectClassification string    `json:"-"`
	BaseProjectRevision   string    `json:"baseProjectRevision"`
	Status                string    `json:"status"`
	CommandCount          int       `json:"commandCount"`
	EncodedBytes          int       `json:"encodedBytes"`
	ExpiresAt             time.Time `json:"expiresAt"`
	ReviewedPlanID        string    `json:"reviewedPlanId,omitempty"`
}

type writerError struct {
	code, message, field string
}

func (e *writerError) Error() string { return e.code }

func (e *writerError) finding() Finding {
	return Finding{APIVersion: "platform.installer/finding/v1alpha1", Kind: "Finding",
		Code: e.code, Status: "BLOCKED", Category: "project-writer", Field: e.field,
		SafeMessage: e.message}
}

func blocked(code, message, field string) *writerError {
	return &writerError{code: code, message: message, field: field}
}

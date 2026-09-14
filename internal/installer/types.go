package installer

import (
	"encoding/json"
	"time"
)

const (
	EditCommandAPIVersion   = "platform.installer/edit-command/v1alpha1"
	EditCommandAPIVersionV2 = "platform.installer/edit-command/v1alpha2"
	EditCommandAPIVersionV3 = "platform.installer/edit-command/v1alpha3"
	EditPlanAPIVersion      = "platform.installer/edit-plan/v1alpha1"
	EditPlanAPIVersionV2    = "platform.installer/edit-plan/v1alpha2"
	EditResultAPIVersion    = "platform.installer/edit-commit-result/v1alpha1"
	EditResultAPIVersionV2  = "platform.installer/edit-commit-result/v1alpha2"
	EditSessionAPIVersion   = "platform.installer/edit-session/v1alpha1"
)

type EditCommand struct {
	APIVersion          string            `json:"apiVersion,omitempty"`
	Kind                string            `json:"kind,omitempty"`
	BaseProjectRevision string            `json:"baseProjectRevision,omitempty"`
	Operation           string            `json:"operation"`
	DeploymentID        string            `json:"deploymentId,omitempty"`
	Setting             string            `json:"setting,omitempty"`
	Value               any               `json:"value,omitempty"`
	EndpointGroupID     string            `json:"endpointGroupId,omitempty"`
	HAProxyDeploymentID string            `json:"haproxyDeploymentId,omitempty"`
	HostID              string            `json:"hostId,omitempty"`
	ServerType          string            `json:"type,omitempty"`
	Address             string            `json:"address,omitempty"`
	SSHPort             int               `json:"sshPort,omitempty"`
	ClearSSHPort        bool              `json:"clearSSHPort,omitempty"`
	ServiceType         string            `json:"serviceType,omitempty"`
	Mode                string            `json:"mode,omitempty"`
	EntityID            string            `json:"entityId,omitempty"`
	Entity              map[string]any    `json:"entity,omitempty"`
	Members             []PlacementMember `json:"members,omitempty"`
	Property            string            `json:"property,omitempty"`
	Deployment          map[string]any    `json:"deployment,omitempty"`
	EndpointGroup       map[string]any    `json:"endpointGroup,omitempty"`
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
		"deploymentId": true, "setting": true, "value": true, "endpointGroupId": true,
		"haproxyDeploymentId": true, "hostId": true, "type": true, "address": true, "sshPort": true,
		"clearSSHPort": true, "serviceType": true, "mode": true, "entityId": true,
		"entity": true, "members": true, "property": true, "deployment": true,
		"endpointGroup": true, "placement": true, "backend": true, "commands": true,
	}
	for field := range fields {
		command.presentFields[field] = true
		if !known[field] {
			command.unknownFields = append(command.unknownFields, field)
		}
	}
	return nil
}

type PlacementMember struct {
	MemberID      string         `json:"memberId"`
	HostID        string         `json:"hostId"`
	Roles         []string       `json:"roles"`
	Configuration map[string]any `json:"configuration,omitempty"`
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
	APIVersion         string           `json:"apiVersion"`
	Kind               string           `json:"kind"`
	Status             string           `json:"status"`
	Changed            bool             `json:"changed"`
	Finding            *Finding         `json:"finding,omitempty"`
	OldProjectRevision string           `json:"oldProjectRevision,omitempty"`
	NewProjectRevision string           `json:"newProjectRevision,omitempty"`
	AffectedDocuments  []DocumentChange `json:"affectedDocuments,omitempty"`
	Snapshot           any              `json:"snapshot,omitempty"`
	ApplyRequired      bool             `json:"applyRequired"`
	Discarded          bool             `json:"discarded,omitempty"`
	Timing             CommitTiming     `json:"timing"`
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

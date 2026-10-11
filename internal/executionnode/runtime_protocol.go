package executionnode

// Typed access to the fixed UI-BE-04C runtime protocol.  This is transport
// plumbing only: it stores no plan, owns no session and cannot carry a remote
// command, playbook path or argv supplied by an Installer client.

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math"
	"os"
	"path"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/sshpassword"
)

func (t OpenSSHTransport) StageRuntimeProjection(ctx context.Context, node Node, runID, projectIdentity, planFingerprint, requirementsFingerprint string, projections map[string]map[string]artifactsource.Result, pkiSecretFiles map[string]string) error {
	if !validRuntimeToken(runID) || projectIdentity == "" || planFingerprint == "" || requirementsFingerprint == "" || !validRemoteSecretFiles(pkiSecretFiles) {
		return errors.New("RUNTIME_PROJECTION_INPUT_INVALID")
	}
	payload := map[string]any{
		"apiVersion":                                   "platform.installer/runtime-projection/v1alpha1",
		"platform_execution_run_id":                    runID,
		"platform_execution_project_identity":          projectIdentity,
		"platform_execution_plan_fingerprint":          planFingerprint,
		"platform_execution_requirements_fingerprint":  requirementsFingerprint,
		"platform_project_id":                          projectIdentity,
		"platform_service_catalog_path":                "/var/lib/platform-installer/runtime/current/catalog/service-catalog.yml",
		"platform_resolved_artifact_sources_by_target": projections,
		"platform_resolved_artifact_sources":           "{{ platform_resolved_artifact_sources_by_target[inventory_hostname] | default({}) }}",
		"platform_pki_secret_files":                    pkiSecretFiles,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	local, err := os.CreateTemp("", "platform-runtime-projection-*.json")
	if err != nil {
		return err
	}
	localPath := local.Name()
	defer os.Remove(localPath)
	if _, err := local.Write(data); err != nil {
		_ = local.Close()
		return err
	}
	if err := local.Close(); err != nil {
		return err
	}
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return err
	}
	remote := "/var/tmp/platform-installer/execution-projection/" + runID + ".json"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/execution-projection/installer-*.json) ;; *) exit 64;; esac\nmkdir -p -- /var/tmp/platform-installer/execution-projection\nrm -f -- \"$1\"\n")); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	args := append(t.scpBase(node, identity), "-O", "--", localPath, t.destination(node, remote))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	script := "set -eu\nremote=$1\nrun=$2\ncase \"$remote:$run\" in /var/tmp/platform-installer/execution-projection/installer-*.json:installer-*) ;; *) exit 64;; esac\nsudo -n install -d -m 0700 /var/lib/platform-installer/execution/runs/$run\nsudo -n install -m 0600 \"$remote\" /var/lib/platform-installer/execution/runs/$run/runtime-projection.json\nrm -f -- \"$remote\"\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote, runID}, []byte(script)); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	return nil
}

func validRemoteSecretFiles(values map[string]string) bool {
	for reference, secretPath := range values {
		if !strings.HasPrefix(reference, "runtime:") || len(reference) == len("runtime:") || !strings.HasPrefix(secretPath, "/") || path.Clean(secretPath) != secretPath || strings.ContainsAny(reference+secretPath, "\r\n\x00") {
			return false
		}
	}
	return true
}

func validRuntimeToken(value string) bool {
	const prefix = "installer-"
	if len(value) <= len(prefix) || len(value) > 128 || !strings.HasPrefix(value, prefix) {
		return false
	}
	for _, r := range value[len(prefix):] {
		// Legacy workstation-created IDs are decimal, while v1alpha2 Start
		// returns the Execution Node's lowercase hexadecimal identifier.
		if !(r >= '0' && r <= '9') && !(r >= 'a' && r <= 'f') {
			return false
		}
	}
	return true
}

type ExecutionStartRequest struct {
	RunID           string         `json:"runId"`
	ProjectIdentity string         `json:"projectIdentity"`
	PlanFingerprint string         `json:"planFingerprint"`
	RuntimeRelease  map[string]any `json:"runtimeRelease"`
}

// RuntimeEvidence is the immutable runtime identity asserted by the active
// Execution Node process, not the release requested by the workstation.
type RuntimeEvidence struct {
	BundleDigest  string `json:"bundleDigest"`
	CoreVersion   string `json:"coreVersion"`
	CatalogDigest string `json:"catalogDigest"`
	Protocol      string `json:"protocol"`
}

type ProjectVerificationSnapshot struct {
	Snapshot *coreadapter.Snapshot
	Runtime  RuntimeEvidence
}

// RuntimeSecretDescriptorRequest carries only archive/provenance proof.  Core
// derives descriptors from the staged desired state; Go never parses settings.
type RuntimeSecretDescriptorRequest struct {
	RequestID, ProjectIdentity, ProjectRevision, ArtifactLockDigest, CatalogLockDigest string
}

type RuntimeSecretDescriptor struct {
	RequirementRef, Purpose, ServiceDeployment, DisplayLabel string
	RequiredWhen                                             string
	Operations                                               []string
	Hosts                                                    []string
}

type RuntimeSecretDescriptorResult struct {
	ProjectIdentity, ProjectRevision, DescriptorSetFingerprint string
	Descriptors                                                []RuntimeSecretDescriptor
	Runtime                                                    RuntimeEvidence
}

type ExecutionRun struct {
	RunID           string `json:"runId"`
	ProjectIdentity string `json:"projectIdentity,omitempty"`
	State           string `json:"state"`
	Sequence        int    `json:"sequence"`
}

type ExecutionEvent struct {
	APIVersion        string               `json:"apiVersion"`
	Kind              string               `json:"kind"`
	RunID             string               `json:"runId"`
	Sequence          int                  `json:"sequence"`
	Timestamp         string               `json:"timestamp"`
	PlanFingerprint   string               `json:"planFingerprint,omitempty"`
	EventType         string               `json:"eventType"`
	Status            string               `json:"status"`
	PhaseID           string               `json:"phaseId,omitempty"`
	ActionID          string               `json:"actionId,omitempty"`
	Host              string               `json:"host,omitempty"`
	ServiceDeployment string               `json:"serviceDeployment,omitempty"`
	Task              *ExecutionEventTask  `json:"task,omitempty"`
	ElapsedMillis     *int                 `json:"elapsedMilliseconds,omitempty"`
	SafeMessage       string               `json:"safeMessage"`
	Error             *ExecutionEventError `json:"error,omitempty"`
	Redaction         ExecutionRedaction   `json:"redaction"`
}

type ExecutionEventTask struct {
	Role string `json:"role,omitempty"`
	Name string `json:"name,omitempty"`
	UUID string `json:"uuid,omitempty"`
}

type ExecutionEventError struct {
	Code          string `json:"code"`
	Summary       string `json:"summary"`
	DiagnosticRef string `json:"diagnosticRef,omitempty"`
}

type ExecutionRedaction struct {
	Applied bool     `json:"applied"`
	Fields  []string `json:"fields,omitempty"`
}

type ExecutionEventPage struct {
	Events           []ExecutionEvent `json:"events"`
	NextSequence     int              `json:"nextSequence"`
	HasMore          bool             `json:"hasMore"`
	EarliestSequence int              `json:"earliestSequence,omitempty"`
	HistoryTruncated bool             `json:"historyTruncated,omitempty"`
}

type CandidateProjectSnapshotRequest struct {
	RequestID                  string
	ProjectIdentity            string
	CandidateProjectRevision   string
	ArtifactLockDigest         string
	CatalogLockDigest          string
	InstallerOwnedLogicalPaths []string
}

var candidateOwnedPathPattern = regexp.MustCompile(`^(ansible\.cfg|inventory/hosts\.yml|inventory/group_vars/all/platform-installer\.yml|inventory/host_vars/[a-z0-9][a-z0-9-]{0,62}/platform-installer\.yml)$`)
var candidateIdentityPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,127}$`)
var previewSettingIDPattern = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9._-]{0,127}$`)

func validLowerHex(value string, size int) bool {
	if len(value) != size {
		return false
	}
	for _, item := range value {
		if (item < '0' || item > '9') && (item < 'a' || item > 'f') {
			return false
		}
	}
	return true
}
func validSHA256(value string) bool {
	return strings.HasPrefix(value, "sha256:") && validLowerHex(strings.TrimPrefix(value, "sha256:"), 64)
}

const ExecutionEventPageLimit = 256

// Match the bounded Execution Node journal. The remote lifecycle reserves its
// final 256 slots for critical events, but permits up to 16384 total records.
const maxObservedExecutionEvents = 16384

const maxDecodedExecutionEventBytes = 64 * 1024
const maxExecutionProtocolResponseBytes = 16 * 1024 * 1024
const maxExecutionEventPageResponseBytes = 2 * 1024 * 1024
const maxProjectSnapshotResponseBytes = 2 * 1024 * 1024
const maxExecutionReleaseProbeBytes = 4 * 1024
const maxExecutionStateProbeBytes = 64 * 1024

var executionEventTypes = map[string]bool{"RUN_STARTED": true, "PHASE_STARTED": true, "ACTION_STARTED": true, "TASK_STARTED": true, "TASK_COMPLETED": true, "ACTION_COMPLETED": true, "PHASE_COMPLETED": true, "RUN_COMPLETED": true, "DIAGNOSTIC": true}
var executionEventStatuses = map[string]bool{"PENDING": true, "RUNNING": true, "SUCCESS": true, "CHANGED": true, "SKIPPED": true, "FAILED": true, "CANCELLED": true, "INTERRUPTED": true}

var errExecutionEventsResponseInvalid = errors.New("EXECUTION_EVENTS_RESPONSE_INVALID")
var errExecutionEventResponseInvalid = errors.New("EXECUTION_EVENT_RESPONSE_INVALID")

func (t OpenSSHTransport) BuildDeploymentPlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, deploymentOrder []string) (DeploymentPlan, error) {
	if projectRoot == "" || len(runtimeRelease) == 0 || deploymentOrder == nil {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_INPUT_INVALID")
	}
	capabilities, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetCapabilities"})
	if err != nil || !orderedDeploymentPlanRequestSupported(capabilities) {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_ORDER_RUNTIME_UNSUPPORTED")
	}
	runID, err := newRunID()
	if err != nil {
		return DeploymentPlan{}, err
	}
	if err := t.stagePlanProject(ctx, node, projectRoot, runID, "plan"); err != nil {
		return DeploymentPlan{}, err
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha2", "operation": "BuildDeploymentPlan", "runId": runID, "project": "/var/lib/platform-installer/execution/runs/" + runID + "/project", "runtimeRelease": runtimeRelease, "deploymentOrder": deploymentOrder})
	if err != nil {
		return DeploymentPlan{}, err
	}
	value, ok := response["deploymentPlan"].(map[string]any)
	if !ok {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	plan, err := decodeDeploymentPlan(value)
	if err != nil {
		return DeploymentPlan{}, err
	}
	if err := bindExecutionManifest(&plan, response, runID); err != nil {
		return DeploymentPlan{}, err
	}
	return plan, nil
}

func orderedDeploymentPlanRequestSupported(response map[string]any) bool {
	if response["apiVersion"] != "platform.installer/execution-capabilities/v1alpha6" || response["kind"] != "ExecutionCapabilities" {
		return false
	}
	allowed := []string{"apiVersion", "kind", "bootstrapProtocol", "coreVersion", "catalogDigest", "schemaDigest", "runtime", "supportedOperations", "executionStart", "targetCredentialLease", "runtimeSecretDescriptors", "serviceConfigurationPreview", "deploymentPlanRequestVersions", "projectSnapshotRequestVersions"}
	return closedKeys(response, allowed...) && contains(response["supportedOperations"], "BuildDeploymentPlan") && exactArrayOfStrings(response["deploymentPlanRequestVersions"], "platform.installer/execution-runtime/v1alpha2")
}

// A blocked plan has no execution manifest by design: it cannot enter Start.
// Only an executable plan is bound to a staged manifest and may be approved.
func bindExecutionManifest(plan *DeploymentPlan, response map[string]any, stagingID string) error {
	if plan == nil || plan.Status == "BLOCKED" {
		return nil
	}
	manifestDigest, ok := response["executionManifestDigest"].(string)
	if !ok || !validSHA256(manifestDigest) {
		return errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	plan.stagingID = stagingID
	plan.executionManifestDigest = manifestDigest
	return nil
}

// BuildProjectSnapshot is a read-only, controller-only Core query. Its project
// staging is owned by this one request and the Execution Node removes it after
// replying; it never creates an execution manifest or lifecycle run.
func (t OpenSSHTransport) BuildProjectSnapshot(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (*coreadapter.Snapshot, error) {
	result, err := t.BuildProjectVerificationSnapshot(ctx, node, projectRoot, runtimeRelease)
	if err != nil {
		return nil, err
	}
	return result.Snapshot, nil
}

// ServiceConfigurationPreview is a bounded, target-free presentation result.
// It is never Project Verify evidence or execution authorization.
type ServiceConfigurationPreview struct {
	APIVersion      string                               `json:"apiVersion"`
	Kind            string                               `json:"kind"`
	ProjectRevision string                               `json:"projectRevision"`
	Services        map[string]ServiceConfigurationScope `json:"services"`
	// Populated only from attested runtime evidence after decoding the closed
	// Core response; this is Wails presentation metadata, not a Core field.
	RuntimeDigest string          `json:"runtimeDigest,omitempty"`
	Runtime       RuntimeEvidence `json:"-"`
}

type ServiceConfigurationScope struct {
	Configuration map[string]ServiceConfigurationValue            `json:"configuration"`
	Members       map[string]map[string]ServiceConfigurationValue `json:"members"`
}

type ServiceConfigurationValue struct {
	State  string `json:"state"`
	Source string `json:"source"`
	Value  any    `json:"value,omitempty"`
}

func (t OpenSSHTransport) BuildServiceConfigurationPreview(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (ServiceConfigurationPreview, error) {
	if projectRoot == "" || len(runtimeRelease) == 0 {
		return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_INPUT_INVALID")
	}
	capabilities, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetCapabilities"})
	if err != nil || (capabilities["apiVersion"] != "platform.installer/execution-capabilities/v1alpha5" && capabilities["apiVersion"] != "platform.installer/execution-capabilities/v1alpha6") || !validServiceConfigurationPreviewCapability(capabilities["serviceConfigurationPreview"], capabilities["supportedOperations"]) {
		return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_UNSUPPORTED")
	}
	runID, err := newRunID()
	if err != nil {
		return ServiceConfigurationPreview{}, err
	}
	if err := t.stagePlanProject(ctx, node, projectRoot, runID, "snapshot"); err != nil {
		return ServiceConfigurationPreview{}, err
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildServiceConfigurationPreview", "runId": runID, "runtimeRelease": runtimeRelease})
	if err != nil {
		return ServiceConfigurationPreview{}, err
	}
	data, err := json.Marshal(response["serviceConfigurationPreview"])
	if err != nil || len(data) > 1024*1024 {
		return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
	}
	var result ServiceConfigurationPreview
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&result) != nil || decoder.Decode(new(any)) != io.EOF || result.RuntimeDigest != "" || result.APIVersion != "platform.installer/service-configuration-preview/v1alpha1" || result.Kind != "ServiceConfigurationPreview" || !validSHA256(result.ProjectRevision) || result.Services == nil || len(result.Services) > 512 {
		return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
	}
	for deploymentID, service := range result.Services {
		if len(deploymentID) > 128 || !runtimeSecretDeploymentPattern.MatchString(deploymentID) || service.Configuration == nil || service.Members == nil || len(service.Configuration) > 256 || len(service.Members) > 512 || !validPreviewValues(service.Configuration) {
			return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
		}
		for memberID, values := range service.Members {
			if len(memberID) > 128 || !runtimeSecretDeploymentPattern.MatchString(memberID) || values == nil || len(values) > 256 || !validPreviewValues(values) {
				return ServiceConfigurationPreview{}, errors.New("SERVICE_CONFIGURATION_PREVIEW_RESPONSE_INVALID")
			}
		}
	}
	runtime, ok := decodeRuntimeEvidence(response["runtimeEvidence"])
	if !ok || runtime.BundleDigest != runtimeRelease["bundleDigest"] {
		return ServiceConfigurationPreview{}, errors.New("EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED")
	}
	result.Runtime = runtime
	result.RuntimeDigest = runtime.BundleDigest
	return result, nil
}

func validPreviewValues(values map[string]ServiceConfigurationValue) bool {
	for settingID, item := range values {
		if !previewSettingIDPattern.MatchString(settingID) {
			return false
		}
		switch item.State {
		case "RESOLVED", "DEFERRED", "UNRESOLVED", "CYCLIC":
		default:
			return false
		}
		switch item.Source {
		case "ROLE_DEFAULT", "DEPLOYMENT_OVERRIDE", "MEMBER_OVERRIDE", "STATIC_REFERENCE", "RUNTIME_DEFERRED":
		default:
			return false
		}
		if item.Value != nil {
			if item.State != "RESOLVED" {
				return false
			}
			switch value := item.Value.(type) {
			case string:
				if len(value) > 4096 || !utf8.ValidString(value) {
					return false
				}
			case float64:
				if math.IsNaN(value) || math.IsInf(value, 0) {
					return false
				}
			case bool:
			default:
				return false
			}
		}
	}
	return true
}

// BuildProjectVerificationSnapshot is additive to the UI-01B snapshot query:
// it returns the same read-only Core snapshot plus identity attested by the
// active immutable runtime that executed it.
func (t OpenSSHTransport) BuildProjectVerificationSnapshot(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (ProjectVerificationSnapshot, error) {
	if projectRoot == "" || len(runtimeRelease) == 0 {
		return ProjectVerificationSnapshot{}, errors.New("PROJECT_SNAPSHOT_INPUT_INVALID")
	}
	runID, err := newRunID()
	if err != nil {
		return ProjectVerificationSnapshot{}, err
	}
	if err := t.stagePlanProject(ctx, node, projectRoot, runID, "snapshot"); err != nil {
		return ProjectVerificationSnapshot{}, err
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{
		"apiVersion": "platform.installer/execution-runtime/v1alpha1",
		"operation":  "BuildProjectSnapshot", "runId": runID,
		"runtimeRelease": runtimeRelease,
	})
	if err != nil {
		return ProjectVerificationSnapshot{}, err
	}
	value, ok := response["projectSnapshot"]
	if !ok {
		return ProjectVerificationSnapshot{}, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	data, err := json.Marshal(value)
	if err != nil || len(data) > maxProjectSnapshotResponseBytes {
		return ProjectVerificationSnapshot{}, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	snapshot, err := coreadapter.DecodeSnapshot(data)
	if err != nil || snapshot.ProjectRevision == "" {
		return ProjectVerificationSnapshot{}, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	runtime, ok := decodeRuntimeEvidence(response["runtimeEvidence"])
	if !ok {
		return ProjectVerificationSnapshot{}, errors.New("EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED")
	}
	return ProjectVerificationSnapshot{Snapshot: snapshot, Runtime: runtime}, nil
}

func decodeRuntimeEvidence(raw any) (RuntimeEvidence, bool) {
	value, ok := raw.(map[string]any)
	if !ok || len(value) != 4 {
		return RuntimeEvidence{}, false
	}
	evidence := RuntimeEvidence{}
	var fields = []struct {
		key    string
		target *string
	}{
		{"bundleDigest", &evidence.BundleDigest}, {"coreVersion", &evidence.CoreVersion},
		{"catalogDigest", &evidence.CatalogDigest}, {"protocol", &evidence.Protocol},
	}
	for _, field := range fields {
		value, ok := value[field.key].(string)
		if !ok || value == "" || len(value) > 256 {
			return RuntimeEvidence{}, false
		}
		*field.target = value
	}
	if !validSHA256(evidence.BundleDigest) || !validSHA256(evidence.CatalogDigest) {
		return RuntimeEvidence{}, false
	}
	return evidence, true
}

// BuildCandidateProjectSnapshot proves a complete transient candidate through
// a separately negotiated fixed request. Older read-only snapshot runtimes are
// never treated as candidate-capable.
func (t OpenSSHTransport) BuildCandidateProjectSnapshot(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, request CandidateProjectSnapshotRequest) (*coreadapter.Snapshot, error) {
	if request.RequestID == "" {
		value := make([]byte, 16)
		if _, err := rand.Read(value); err != nil {
			return nil, err
		}
		request.RequestID = hex.EncodeToString(value)
	}
	ownedSeen := make(map[string]bool)
	ownedValid := len(request.InstallerOwnedLogicalPaths) <= 1026
	for _, logical := range request.InstallerOwnedLogicalPaths {
		if !candidateOwnedPathPattern.MatchString(logical) || ownedSeen[logical] {
			ownedValid = false
		}
		ownedSeen[logical] = true
	}
	if projectRoot == "" || len(runtimeRelease) == 0 || !validLowerHex(request.RequestID, 32) || !candidateIdentityPattern.MatchString(request.ProjectIdentity) || !validSHA256(request.CandidateProjectRevision) || !validSHA256(request.ArtifactLockDigest) || !validSHA256(request.CatalogLockDigest) || !ownedValid {
		return nil, errors.New("PROJECT_SNAPSHOT_INPUT_INVALID")
	}
	capabilities, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetCapabilities"})
	if err != nil {
		return nil, err
	}
	if !candidateSnapshotCapabilitySupported(capabilities) {
		return nil, errors.New("PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED")
	}
	runID, err := newRunID()
	if err != nil {
		return nil, err
	}
	archiveDigest, err := t.stageCandidateProject(ctx, node, projectRoot, runID, request.RequestID)
	if err != nil {
		return nil, err
	}
	defer t.cleanupSnapshotStaging(node, runID, request.RequestID, archiveDigest)
	payload := map[string]any{
		"apiVersion": "platform.installer/project-snapshot-request/v1alpha1", "kind": "BuildProjectSnapshotRequest",
		"requestId": request.RequestID, "projectIdentity": request.ProjectIdentity,
		"candidateProjectRevision": request.CandidateProjectRevision, "projectArchiveDigest": archiveDigest,
		"artifactLockDigest": request.ArtifactLockDigest, "catalogLockDigest": request.CatalogLockDigest,
		"installerOwnedLogicalPaths": request.InstallerOwnedLogicalPaths,
		"projectContract":            "v2alpha1", "snapshotContract": "v1alpha1", "editContract": "v1alpha2",
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildProjectSnapshot", "runId": runID, "runtimeRelease": runtimeRelease, "snapshotRequest": payload})
	if err != nil {
		return nil, err
	}
	value, ok := response["projectSnapshot"]
	if !ok {
		return nil, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	data, err := json.Marshal(value)
	if err != nil || len(data) > maxProjectSnapshotResponseBytes {
		return nil, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	snapshot, err := coreadapter.DecodeSnapshot(data)
	if err != nil || snapshot.ProjectRevision != request.CandidateProjectRevision {
		return nil, errors.New("PROJECT_SNAPSHOT_RESPONSE_INVALID")
	}
	return snapshot, nil
}

// BuildRuntimeSecretDescriptors stages a verified candidate archive through
// the existing request-owned path, then asks only Core for safe prompts.
func (t OpenSSHTransport) BuildRuntimeSecretDescriptors(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, request RuntimeSecretDescriptorRequest) (RuntimeSecretDescriptorResult, error) {
	if projectRoot == "" || len(runtimeRelease) == 0 || !validLowerHex(request.RequestID, 32) || !candidateIdentityPattern.MatchString(request.ProjectIdentity) || !validSHA256(request.ProjectRevision) || !validSHA256(request.ArtifactLockDigest) || !validSHA256(request.CatalogLockDigest) {
		return RuntimeSecretDescriptorResult{}, errors.New("RUNTIME_SECRET_DESCRIPTORS_INPUT_INVALID")
	}
	capability, err := t.CredentialStartCapability(ctx, node)
	if err != nil || (capability.APIVersion != "platform.installer/execution-capabilities/v1alpha4" && capability.APIVersion != "platform.installer/execution-capabilities/v1alpha5" && capability.APIVersion != "platform.installer/execution-capabilities/v1alpha6") || !capability.TypedRuntimeInputs || !capability.supportsPayloadVersion(credentialPayloadVersionV4) {
		return RuntimeSecretDescriptorResult{}, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNSUPPORTED")
	}
	runID, err := newRunID()
	if err != nil {
		return RuntimeSecretDescriptorResult{}, err
	}
	archiveDigest, err := t.stageCandidateProject(ctx, node, projectRoot, runID, request.RequestID)
	if err != nil {
		return RuntimeSecretDescriptorResult{}, err
	}
	defer t.cleanupSnapshotStaging(node, runID, request.RequestID, archiveDigest)
	payload := map[string]any{"apiVersion": "platform.installer/project-snapshot-request/v1alpha1", "kind": "BuildProjectSnapshotRequest", "requestId": request.RequestID, "projectIdentity": request.ProjectIdentity, "candidateProjectRevision": request.ProjectRevision, "projectArchiveDigest": archiveDigest, "artifactLockDigest": request.ArtifactLockDigest, "catalogLockDigest": request.CatalogLockDigest, "installerOwnedLogicalPaths": []string{}, "projectContract": "v2alpha1", "snapshotContract": "v1alpha1", "editContract": "v1alpha2"}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildRuntimeSecretDescriptors", "runId": runID, "runtimeRelease": runtimeRelease, "snapshotRequest": payload})
	if err != nil {
		return RuntimeSecretDescriptorResult{}, err
	}
	value, ok := response["runtimeSecretDescriptors"].(map[string]any)
	if !ok {
		return RuntimeSecretDescriptorResult{}, errors.New("RUNTIME_SECRET_DESCRIPTORS_RESPONSE_INVALID")
	}
	data, err := json.Marshal(value)
	if err != nil || len(data) > 65536 {
		return RuntimeSecretDescriptorResult{}, errors.New("RUNTIME_SECRET_DESCRIPTORS_RESPONSE_INVALID")
	}
	var result RuntimeSecretDescriptorResult
	if err := json.Unmarshal(data, &result); err != nil || result.ProjectIdentity != request.ProjectIdentity || result.ProjectRevision != request.ProjectRevision || !validSHA256(result.DescriptorSetFingerprint) || len(result.Descriptors) > 16 {
		return RuntimeSecretDescriptorResult{}, errors.New("RUNTIME_SECRET_DESCRIPTORS_RESPONSE_INVALID")
	}
	result.Runtime, ok = decodeRuntimeEvidence(response["runtimeEvidence"])
	if !ok {
		return RuntimeSecretDescriptorResult{}, errors.New("EXECUTION_RUNTIME_IDENTITY_UNCONFIRMED")
	}
	return result, nil
}

func (t OpenSSHTransport) CheckCandidateProjectSnapshotCapability(ctx context.Context, node Node, expectedRuntime map[string]any) error {
	expectedDigest, _ := expectedRuntime["bundleDigest"].(string)
	if !validSHA256(expectedDigest) {
		return errors.New("PROJECT_SNAPSHOT_INPUT_INVALID")
	}
	active, err := t.sshBounded(ctx, node, "sudo", []string{"-n", "cat", "/var/lib/platform-installer/runtime/state/active"}, nil, maxExecutionStateProbeBytes)
	if err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	if parseFacts(string(active))["BUNDLE_DIGEST"] != expectedDigest {
		return errors.New("EXECUTION_RUNTIME_RELEASE_CHANGED")
	}
	capabilities, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetCapabilities"})
	if err != nil {
		return err
	}
	if candidateSnapshotCapabilitySupported(capabilities) {
		return nil
	}
	return errors.New("PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED")
}

func candidateSnapshotCapabilitySupported(capabilities map[string]any) bool {
	contains := func(value any, expected string) bool {
		items, ok := value.([]any)
		if !ok {
			return false
		}
		for _, item := range items {
			if item == expected {
				return true
			}
		}
		return false
	}
	return contains(capabilities["supportedOperations"], "BuildProjectSnapshot") &&
		contains(capabilities["projectSnapshotRequestVersions"], "platform.installer/project-snapshot-request/v1alpha1")
}

func (t OpenSSHTransport) cleanupSnapshotStaging(node Node, runID, requestID, archiveDigest string) {
	if !validRuntimeToken(runID) || !validLowerHex(requestID, 32) || !validSHA256(archiveDigest) {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	script := "set -eu\ncase \"$1:$2:$3\" in installer-*:[0-9a-f][0-9a-f]*:sha256:*) ;; *) exit 64;; esac\nruntime=$(sudo -n readlink -f /var/lib/platform-installer/runtime/current)\ncase \"$runtime\" in /var/lib/platform-installer/runtime/releases/*) ;; *) exit 64;; esac\nsudo -n env PYTHONPATH=\"$runtime/ansible-core/tools\" python3 \"$runtime/ansible-core/tools/execution_protocol.py\" --runtime-release \"$runtime\" --controller \"$runtime/ansible-core/tools/execution_controller.py\" --cleanup-snapshot-run-id \"$1\" --cleanup-request-id \"$2\" --cleanup-archive-digest \"$3\" >/dev/null\ntemporary=/var/tmp/platform-installer/execution-plan/$1\ncase \"$temporary\" in /var/tmp/platform-installer/execution-plan/installer-*) ;; *) exit 64;; esac\nrm -rf -- \"$temporary\"\n"
	_, _ = t.ssh(ctx, node, "sh", []string{"-s", "--", runID, requestID, archiveDigest}, []byte(script))
}

func (t OpenSSHTransport) cleanupSnapshotUpload(parent context.Context, node Node, runID, purpose, remote string) {
	if remote == "" || remote != projectUploadPath(runID, purpose) {
		return
	}
	ctx, cancel := context.WithTimeout(context.WithoutCancel(parent), 30*time.Second)
	defer cancel()
	script := "set -eu\ntemporary=$1\nrm -rf -- \"$temporary\"\n"
	_, _ = t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte(script))
}

func projectUploadPath(runID, purpose string) string {
	if !validRuntimeToken(runID) {
		return ""
	}
	switch purpose {
	case "candidate":
		return "/var/tmp/platform-installer/execution-plan/" + runID
	case "plan", "snapshot":
		return "/var/tmp/platform-installer-project-" + runID
	default:
		return ""
	}
}

const privateProjectStageScript = `set -eu
case "$1" in /var/tmp/platform-installer-project-installer-*) ;; *) exit 64;; esac
[ -d /var/tmp ] && [ ! -L /var/tmp ] || exit 64
[ "$(stat -c %u /var/tmp)" = 0 ] && [ "$(stat -c %a /var/tmp)" = 1777 ] || exit 64
umask 077
mkdir -- "$1"
`

func (t OpenSSHTransport) stagePlanProject(ctx context.Context, node Node, projectRoot, runID, purpose string) error {
	archive, err := createProjectArchive(projectRoot)
	if err != nil {
		return err
	}
	defer os.Remove(archive)
	_, err = t.stageProjectArchive(ctx, node, archive, runID, purpose, "")
	return err
}

func (t OpenSSHTransport) stageCandidateProject(ctx context.Context, node Node, projectRoot, runID, requestID string) (string, error) {
	archive, err := createCandidateProjectArchive(projectRoot)
	if err != nil {
		return "", err
	}
	defer os.Remove(archive)
	return t.stageProjectArchive(ctx, node, archive, runID, "candidate", requestID)
}

func (t OpenSSHTransport) stageProjectArchive(ctx context.Context, node Node, archive, runID, purpose, requestID string) (string, error) {
	archiveFile, err := os.Open(archive)
	if err != nil {
		return "", err
	}
	digest := sha256.New()
	_, copyErr := io.Copy(digest, archiveFile)
	closeErr := archiveFile.Close()
	if copyErr != nil {
		return "", copyErr
	}
	if closeErr != nil {
		return "", closeErr
	}
	archiveDigest := "sha256:" + hex.EncodeToString(digest.Sum(nil))
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return "", err
	}
	remote := projectUploadPath(runID, purpose)
	if remote == "" {
		return "", &ExecutionError{Code: "PROJECT_TRANSFER_FAILED"}
	}
	claim := privateProjectStageScript
	if purpose == "candidate" {
		claim = "set -eu\ncase \"$1\" in /var/tmp/platform-installer/execution-plan/installer-*) ;; *) exit 64;; esac\n[ -d /var/tmp ] && [ ! -L /var/tmp ] || exit 64\n[ \"$(stat -c %u /var/tmp)\" = 0 ] && [ \"$(stat -c %a /var/tmp)\" = 1777 ] || exit 64\nbase=/var/tmp/platform-installer\nparent=$base/execution-plan\n[ -d \"$base\" ] && [ ! -L \"$base\" ] || exit 64\n[ \"$(stat -c %u \"$base\")\" = 0 ] && [ \"$(stat -c %a \"$base\")\" = 711 ] || exit 64\n[ -d \"$parent\" ] && [ ! -L \"$parent\" ] || exit 64\n[ \"$(stat -c %u \"$parent\")\" = \"$(id -u)\" ] && [ \"$(stat -c %a \"$parent\")\" = 700 ] || exit 64\numask 077\nmkdir -- \"$1\"\n"
	}
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte(claim)); err != nil {
		return "", &ExecutionError{Code: "PROJECT_TRANSFER_FAILED"}
	}
	owned := true
	defer func() {
		if owned {
			t.cleanupSnapshotUpload(ctx, node, runID, purpose, remote)
		}
	}()
	args := append(t.scpBase(node, identity), "-O", "--", archive, t.destination(node, remote+"/project.tar"))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return "", &ExecutionError{Code: "PROJECT_TRANSFER_FAILED"}
	}
	script := "set -eu\nrun=$1; archive=$2; run_id=$3; expected=$4; purpose=$5; request_id=${6-}\ncase \"$purpose:$run\" in candidate:/var/tmp/platform-installer/execution-plan/installer-*|plan:/var/tmp/platform-installer-project-installer-*|snapshot:/var/tmp/platform-installer-project-installer-*) ;; *) exit 64;; esac\ncase \"$archive\" in \"$run/project.tar\") ;; *) exit 64;; esac\ncase \"$purpose\" in plan|snapshot|candidate) ;; *) exit 64;; esac\nactual=sha256:$(sha256sum \"$archive\" | awk '{print $1}')\n[ \"$actual\" = \"$expected\" ]\nif [ \"$purpose\" = candidate ]; then\n  runtime=$(sudo -n readlink -f /var/lib/platform-installer/runtime/current)\n  case \"$runtime\" in /var/lib/platform-installer/runtime/releases/*) ;; *) exit 64;; esac\n  sudo -n env PYTHONPATH=\"$runtime/ansible-core/tools\" python3 \"$runtime/ansible-core/tools/execution_protocol.py\" --runtime-release \"$runtime\" --controller \"$runtime/ansible-core/tools/execution_controller.py\" --stage-candidate-archive \"$archive\" --stage-run-id \"$run_id\" --stage-request-id \"$request_id\" --expected-archive-digest \"$expected\" >/dev/null\nelse\n  sudo -n install -d -m 0700 /var/lib/platform-installer/execution/runs/$run_id/project\n  sudo -n sh -c 'umask 077; printf \"%s\\n\" \"$1\" > \"$2\"' -- \"$actual\" /var/lib/platform-installer/execution/runs/$run_id/project-archive.digest\n  sudo -n tar -xf \"$archive\" -C /var/lib/platform-installer/execution/runs/$run_id/project\n  if [ \"$purpose\" = snapshot ]; then\n    sudo -n sh -c 'umask 077; printf \"{\\\"kind\\\":\\\"readonly\\\",\\\"runId\\\":\\\"%s\\\"}\\n\" \"$1\" > \"$2\"' -- \"$run_id\" /var/lib/platform-installer/execution/runs/$run_id/.snapshot-owner.json\n  fi\nfi\nsudo -n rm -f -- \"$archive\"\nrm -rf -- \"$run\"\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote, remote + "/project.tar", runID, archiveDigest, purpose, requestID}, []byte(script)); err != nil {
		return "", &ExecutionError{Code: "PROJECT_TRANSFER_FAILED"}
	}
	owned = false
	return archiveDigest, nil
}

func (t OpenSSHTransport) StartExecution(ctx context.Context, node Node, request ExecutionStartRequest) (ExecutionRun, error) {
	if request.RunID == "" || request.ProjectIdentity == "" || request.PlanFingerprint == "" || len(request.RuntimeRelease) == 0 {
		return ExecutionRun{}, errors.New("EXECUTION_START_INPUT_INVALID")
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "StartExecution", "runId": request.RunID, "projectIdentity": request.ProjectIdentity, "planFingerprint": request.PlanFingerprint, "runtimeRelease": request.RuntimeRelease})
	if err != nil {
		return ExecutionRun{}, err
	}
	run, err := decodeRun(response)
	if err == nil {
		run.RunID = request.RunID
		run.ProjectIdentity = request.ProjectIdentity
	}
	return run, err
}

func (t OpenSSHTransport) GetExecution(ctx context.Context, node Node, runID string) (ExecutionRun, error) {
	ctx = sshpassword.WithScope(ctx, sshpassword.Scope{RunID: runID})
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetExecution", "runId": runID})
	if err != nil {
		return ExecutionRun{}, err
	}
	run, err := decodeRun(response)
	if err == nil {
		run.RunID = runID
	}
	return run, err
}

func (t OpenSSHTransport) GetEvents(ctx context.Context, node Node, runID string, afterSequence, limit int) (ExecutionEventPage, error) {
	ctx = sshpassword.WithScope(ctx, sshpassword.Scope{RunID: runID})
	if afterSequence < 0 || limit < 1 || limit > 512 {
		return ExecutionEventPage{}, errors.New("EXECUTION_EVENTS_INPUT_INVALID")
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetEvents", "runId": runID, "afterSequence": afterSequence, "limit": limit})
	if err != nil {
		return ExecutionEventPage{}, err
	}
	return decodeEventPage(response, runID, afterSequence, limit)
}

func (t OpenSSHTransport) CancelExecution(ctx context.Context, node Node, runID string) (ExecutionRun, error) {
	ctx = sshpassword.WithScope(ctx, sshpassword.Scope{RunID: runID})
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "CancelExecution", "runId": runID})
	if err != nil {
		return ExecutionRun{}, err
	}
	return decodeRun(response)
}

func decodeRun(response map[string]any) (ExecutionRun, error) {
	value, ok := response["run"].(map[string]any)
	if !ok {
		return ExecutionRun{}, errors.New("EXECUTION_RUN_RESPONSE_INVALID")
	}
	run := ExecutionRun{}
	if v, ok := value["runId"].(string); ok {
		run.RunID = v
	}
	if v, ok := value["projectIdentity"].(string); ok {
		run.ProjectIdentity = v
	}
	if metadata, ok := response["metadata"].(map[string]any); ok {
		if v, ok := metadata["projectIdentity"].(string); ok {
			run.ProjectIdentity = v
		}
		if run.RunID == "" {
			if v, ok := metadata["runId"].(string); ok {
				run.RunID = v
			}
		}
	}
	if v, ok := value["state"].(string); ok {
		run.State = v
	}
	if v, ok := value["sequence"].(float64); ok {
		run.Sequence = int(v)
	}
	if run.State == "" {
		return ExecutionRun{}, errors.New("EXECUTION_RUN_RESPONSE_INVALID")
	}
	return run, nil
}
func decodeEventPage(response map[string]any, runID string, afterSequence, limit int) (ExecutionEventPage, error) {
	values, ok := response["events"].([]any)
	if !ok || len(values) > 2048 {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	result := make([]ExecutionEvent, 0, len(values))
	earliestRaw, earliestExists := response["earliestSequence"]
	truncatedRaw, truncatedExists := response["historyTruncated"]
	earliest, earliestOK := earliestRaw.(float64)
	truncated, truncatedOK := truncatedRaw.(bool)
	if earliestExists != truncatedExists || earliestExists && (!earliestOK || !truncatedOK || earliest < 0 || earliest != float64(int(earliest))) {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	earliestPresent := earliestExists
	truncatedPresent := truncatedExists
	expectedSequence := afterSequence + 1
	if truncatedPresent && truncated {
		if earliest <= float64(expectedSequence) {
			return ExecutionEventPage{}, errExecutionEventsResponseInvalid
		}
		expectedSequence = int(earliest)
	}
	for _, raw := range values {
		value, ok := raw.(map[string]any)
		if !ok {
			return ExecutionEventPage{}, errExecutionEventResponseInvalid
		}
		for _, key := range []string{"planFingerprint", "phaseId", "actionId", "host", "serviceDeployment"} {
			if rawValue, present := value[key]; present {
				text, valid := rawValue.(string)
				if !valid || text == "" {
					return ExecutionEventPage{}, errExecutionEventResponseInvalid
				}
			}
		}
		if rawError, present := value["error"].(map[string]any); present {
			if rawDiagnostic, exists := rawError["diagnosticRef"]; exists {
				text, valid := rawDiagnostic.(string)
				if !valid || text == "" {
					return ExecutionEventPage{}, errExecutionEventResponseInvalid
				}
			}
		}
		encoded, err := json.Marshal(value)
		if err != nil || len(encoded) > maxDecodedExecutionEventBytes {
			return ExecutionEventPage{}, errExecutionEventResponseInvalid
		}
		event := ExecutionEvent{}
		if err := json.Unmarshal(encoded, &event); err != nil || validateExecutionEvent(event, runID) != nil || event.Sequence != expectedSequence {
			return ExecutionEventPage{}, errExecutionEventResponseInvalid
		}
		result = append(result, event)
		expectedSequence++
	}
	page := ExecutionEventPage{Events: result, NextSequence: afterSequence}
	if earliestPresent {
		page.EarliestSequence = int(earliest)
		page.HistoryTruncated = truncated
	}
	nextRaw, hasNext := response["nextSequence"]
	moreRaw, hasHasMore := response["hasMore"]
	if !hasNext && !hasHasMore {
		if len(result) > 0 {
			page.NextSequence = result[len(result)-1].Sequence
		}
		return page, nil
	}
	next, nextOK := nextRaw.(float64)
	more, moreOK := moreRaw.(bool)
	if !nextOK || next < 0 || next != float64(int(next)) || !moreOK || len(result) > limit {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	page.NextSequence, page.HasMore = int(next), more
	if len(result) > 0 && page.NextSequence != result[len(result)-1].Sequence {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	if len(result) == 0 && (page.NextSequence != afterSequence || page.HasMore) {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	if page.HistoryTruncated && len(result) == 0 {
		return ExecutionEventPage{}, errExecutionEventsResponseInvalid
	}
	return page, nil
}

func validateExecutionEvent(event ExecutionEvent, runID string) error {
	if event.APIVersion != "platform.installer/event/v1alpha1" || event.Kind != "ExecutionEvent" || event.RunID != runID || event.Sequence < 1 || !executionEventTypes[event.EventType] || !executionEventStatuses[event.Status] || event.SafeMessage == "" || !event.Redaction.Applied {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if _, err := time.Parse(time.RFC3339, event.Timestamp); err != nil {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if event.PlanFingerprint != "" && !validSHA256Fingerprint(event.PlanFingerprint) {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	for _, value := range []string{event.SafeMessage, event.PhaseID, event.ActionID, event.Host, event.ServiceDeployment} {
		if len(value) > 8192 || strings.ContainsAny(value, "\x00\r\n\x1b") {
			return errors.New("EXECUTION_EVENT_INVALID")
		}
	}
	if event.ElapsedMillis != nil && *event.ElapsedMillis < 0 {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if event.Task != nil && (len(event.Task.UUID) > 128 || len(event.Task.Role) > 256 || len(event.Task.Name) > 512 || strings.ContainsAny(event.Task.UUID+event.Task.Role+event.Task.Name, "\x00\r\n\x1b")) {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if (event.EventType == "TASK_STARTED" || event.EventType == "TASK_COMPLETED") && (event.Task == nil || event.Task.UUID == "") {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if event.Error != nil && (!validEventCode(event.Error.Code) || event.Error.Summary == "" || len(event.Error.Summary) > 2048 || len(event.Error.DiagnosticRef) > 2048 || strings.ContainsAny(event.Error.Summary+event.Error.DiagnosticRef, "\x00\r\n\x1b")) {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	if len(event.Redaction.Fields) > 64 {
		return errors.New("EXECUTION_EVENT_INVALID")
	}
	seenRedactions := map[string]bool{}
	for _, field := range event.Redaction.Fields {
		if field == "" || len(field) > 256 || strings.ContainsAny(field, "\x00\r\n\x1b") || seenRedactions[field] {
			return errors.New("EXECUTION_EVENT_INVALID")
		}
		seenRedactions[field] = true
		if field == "task.name" && event.Task != nil && event.Task.Name != "" {
			return errors.New("EXECUTION_EVENT_INVALID")
		}
	}
	return nil
}

func validSHA256Fingerprint(value string) bool {
	if len(value) != len("sha256:")+64 || !strings.HasPrefix(value, "sha256:") {
		return false
	}
	for _, character := range value[len("sha256:"):] {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}

func validEventCode(value string) bool {
	if value == "" || len(value) > 128 || value[0] < 'A' || value[0] > 'Z' {
		return false
	}
	for _, character := range value[1:] {
		if character != '_' && (character < 'A' || character > 'Z') && (character < '0' || character > '9') {
			return false
		}
	}
	return true
}
func decodeDeploymentPlan(value map[string]any) (DeploymentPlan, error) {
	plan := DeploymentPlan{}
	if v, ok := value["id"].(string); ok {
		plan.ID = v
	}
	if v, ok := value["status"].(string); ok {
		plan.Status = v
	}
	if v, ok := value["projectIdentity"].(string); ok {
		plan.ProjectIdentity = v
	}
	if v, ok := value["projectRevision"].(string); ok {
		plan.ProjectRevision = v
	}
	if f, ok := value["fingerprints"].(map[string]any); ok {
		if v, ok := f["plan"].(string); ok {
			plan.PlanFingerprint = v
		}
	}
	acknowledgements, err := decodePlanAcknowledgements(value["acknowledgements"])
	if err != nil {
		return DeploymentPlan{}, err
	}
	plan.AcknowledgementDetails = acknowledgements
	for _, acknowledgement := range acknowledgements {
		plan.Acknowledgements = append(plan.Acknowledgements, acknowledgement.Code)
	}
	phases, err := decodeDeploymentPlanPhases(value["phases"])
	if err != nil {
		return DeploymentPlan{}, err
	}
	plan.Phases = phases
	plan.Findings = decodeFindings(value["findings"])
	if requirements, ok := value["artifactRequirements"].([]any); ok {
		for _, raw := range requirements {
			item, ok := raw.(map[string]any)
			if !ok {
				return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
			}
			requirement := artifactsource.Requirement{}
			if v, ok := item["requirementId"].(string); ok {
				requirement.ID = v
			}
			if v, ok := item["name"].(string); ok {
				requirement.Name = v
			}
			if v, ok := item["version"].(string); ok {
				requirement.Version = v
			}
			if v, ok := item["os"].(string); ok {
				requirement.OS = v
			}
			if v, ok := item["architecture"].(string); ok {
				requirement.Architecture = v
			}
			if requirement.ID == "" || requirement.Name == "" || requirement.OS == "" || requirement.Architecture == "" {
				return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_REQUIREMENT_INVALID")
			}
			plan.ArtifactRequirements = append(plan.ArtifactRequirements, requirement)
		}
	}
	credentials, err := decodeRequiredCredentials(value["requiredCredentials"])
	if err != nil {
		return DeploymentPlan{}, err
	}
	plan.RequiredCredentials = credentials
	if r, ok := value["runtimeRelease"].(map[string]any); ok {
		plan.RuntimeRelease = r
	}
	if plan.ID == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" || len(plan.RuntimeRelease) == 0 || (plan.Status != "EXECUTABLE" && plan.Status != "BLOCKED") || (plan.Status == "EXECUTABLE" && plan.ProjectIdentity == "") {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	return plan, nil
}

func decodeRequiredCredentials(raw any) ([]RequiredCredential, error) {
	values, ok := raw.([]any)
	if !ok || len(values) > 32 {
		return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	result := make([]RequiredCredential, 0, len(values))
	seen := map[string]bool{}
	for _, rawValue := range values {
		value, ok := rawValue.(map[string]any)
		if !ok || !closedKeys(value, "requirementRef", "purpose", "hosts") {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		ref, refOK := value["requirementRef"].(string)
		purpose, purposeOK := value["purpose"].(string)
		hostValues, hostsOK := value["hosts"].([]any)
		if !refOK || !purposeOK || !hostsOK || ref == "" || len(ref) > 128 || purpose == "" || len(purpose) > 128 || seen[ref] || len(hostValues) > maxDeploymentPlanTargets {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		credential := RequiredCredential{RequirementRef: ref, Purpose: purpose, Hosts: make([]string, 0, len(hostValues))}
		prior := ""
		for _, rawHost := range hostValues {
			host, ok := rawHost.(string)
			if !ok || !candidateIdentityPattern.MatchString(host) || host <= prior {
				return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
			}
			credential.Hosts = append(credential.Hosts, host)
			prior = host
		}
		seen[ref] = true
		result = append(result, credential)
	}
	return result, nil
}

const (
	maxDeploymentPlanPhases           = 32
	maxDeploymentPlanActions          = 512
	maxDeploymentPlanTargets          = 256
	maxDeploymentPlanDependencies     = 256
	maxDeploymentPlanAcknowledgements = 64
	maxDeploymentPlanText             = 512
)

func decodePlanAcknowledgements(raw any) ([]PlanAcknowledgement, error) {
	values, ok := raw.([]any)
	if !ok || len(values) > maxDeploymentPlanAcknowledgements {
		return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	result := make([]PlanAcknowledgement, 0, len(values))
	seen := map[string]bool{}
	for _, rawValue := range values {
		value, ok := rawValue.(map[string]any)
		if !ok || len(value) != 2 {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		code, codeOK := value["code"].(string)
		summary, summaryOK := value["summary"].(string)
		if !codeOK || !summaryOK || !validEventCode(code) || len(summary) == 0 || len(summary) > maxDeploymentPlanText || seen[code] {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		seen[code] = true
		result = append(result, PlanAcknowledgement{Code: code, Summary: summary})
	}
	return result, nil
}

func decodeDeploymentPlanPhases(raw any) ([]DeploymentPlanPhase, error) {
	values, ok := raw.([]any)
	if !ok || len(values) > maxDeploymentPlanPhases {
		return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	result := make([]DeploymentPlanPhase, 0, len(values))
	seenPhases, seenActions := map[string]bool{}, map[string]bool{}
	actionCount := 0
	for index, rawValue := range values {
		value, ok := rawValue.(map[string]any)
		if !ok || len(value) != 3 {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		id, idOK := value["id"].(string)
		order, orderOK := exactNonNegativeInteger(value["order"])
		rawActions, actionsOK := value["actions"].([]any)
		if !idOK || !orderOK || order != index || len(id) == 0 || len(id) > maxDeploymentPlanText || seenPhases[id] {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		if !actionsOK || actionCount+len(rawActions) > maxDeploymentPlanActions {
			return nil, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
		seenPhases[id] = true
		phase := DeploymentPlanPhase{ID: id, Order: order, Actions: make([]DeploymentPlanAction, 0, len(rawActions))}
		for _, rawAction := range rawActions {
			action, err := decodeDeploymentPlanAction(rawAction, seenActions)
			if err != nil {
				return nil, err
			}
			phase.Actions = append(phase.Actions, action)
			actionCount++
		}
		result = append(result, phase)
	}
	return result, nil
}

func decodeDeploymentPlanAction(raw any, seen map[string]bool) (DeploymentPlanAction, error) {
	value, ok := raw.(map[string]any)
	if !ok {
		return DeploymentPlanAction{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	allowed := len(value) == 7 || len(value) == 8
	if !allowed {
		return DeploymentPlanAction{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	action := DeploymentPlanAction{}
	var idOK, typeOK, summaryOK, mutatingOK bool
	action.ID, idOK = value["id"].(string)
	action.Type, typeOK = value["type"].(string)
	action.Summary, summaryOK = value["summary"].(string)
	action.Mutating, mutatingOK = value["mutating"].(bool)
	if deployment, present := value["serviceDeployment"]; present {
		var deploymentOK bool
		action.ServiceDeployment, deploymentOK = deployment.(string)
		if !deploymentOK || action.ServiceDeployment == "" || len(action.ServiceDeployment) > maxDeploymentPlanText {
			return DeploymentPlanAction{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
		}
	}
	if reboot, ok := value["reboot"].(string); ok && (reboot == "NONE" || reboot == "RECOMMENDED" || reboot == "REQUIRED") {
		action.Reboot = reboot
	} else {
		return DeploymentPlanAction{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	targets, targetOK := decodePlanStringList(value["targets"], maxDeploymentPlanTargets)
	dependsOn, dependsOK := decodePlanStringList(value["dependsOn"], maxDeploymentPlanDependencies)
	if !idOK || !typeOK || !summaryOK || !mutatingOK || !validEventCode(action.Type) || len(action.ID) == 0 || len(action.ID) > maxDeploymentPlanText || len(action.Summary) == 0 || len(action.Summary) > maxDeploymentPlanText || !targetOK || !dependsOK || seen[action.ID] {
		return DeploymentPlanAction{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	seen[action.ID] = true
	action.Targets, action.DependsOn = targets, dependsOn
	return action, nil
}

func decodePlanStringList(raw any, limit int) ([]string, bool) {
	values, ok := raw.([]any)
	if !ok || len(values) > limit {
		return nil, false
	}
	result := make([]string, 0, len(values))
	seen := map[string]bool{}
	for _, rawValue := range values {
		value, ok := rawValue.(string)
		if !ok || value == "" || len(value) > maxDeploymentPlanText || seen[value] {
			return nil, false
		}
		seen[value] = true
		result = append(result, value)
	}
	return result, true
}

func exactNonNegativeInteger(raw any) (int, bool) {
	value, ok := raw.(float64)
	if !ok || value < 0 || value != float64(int(value)) || int(value) < 0 {
		return 0, false
	}
	return int(value), true
}

func decodeFindings(raw any) []Finding {
	values, ok := raw.([]any)
	if !ok {
		return nil
	}
	result := make([]Finding, 0, len(values))
	for _, rawFinding := range values {
		value, ok := rawFinding.(map[string]any)
		if !ok {
			continue
		}
		code, codeOK := value["code"].(string)
		message, messageOK := value["safeMessage"].(string)
		if codeOK && messageOK && code != "" && message != "" {
			result = append(result, Finding{Code: code, SafeMessage: message})
		}
	}
	return result
}

func (t OpenSSHTransport) runtimeProtocol(ctx context.Context, node Node, request map[string]any) (map[string]any, error) {
	return t.runtimeProtocolWithPrivateFlag(ctx, node, request, "")
}

// StageTargetHostTrust is private execution input, not a public Start wire
// field or portable project mutation. The node verifies the Core-resolved
// endpoints and binds the resulting file to the exact staged manifest.
func (t OpenSSHTransport) StageTargetHostTrust(ctx context.Context, node Node, plan DeploymentPlan, approvals []TargetHostKeyApproval) error {
	if plan.stagingID == "" || !validSHA256(plan.executionManifestDigest) || len(approvals) == 0 || len(approvals) > 256 {
		return errors.New("TARGET_HOST_TRUST_INVALID")
	}
	response, err := t.runtimeProtocolWithPrivateFlag(ctx, node, map[string]any{
		"stagingId": plan.stagingID, "projectIdentity": plan.ProjectIdentity,
		"projectRevision": plan.ProjectRevision, "planFingerprint": plan.PlanFingerprint,
		"runtimeRelease": plan.RuntimeRelease, "manifestDigest": plan.executionManifestDigest,
		"approvals": approvals,
	}, "--stage-target-host-trust")
	if err != nil {
		return err
	}
	if response["status"] != "STAGED" {
		return errors.New("TARGET_HOST_TRUST_INVALID")
	}
	return nil
}

func (t OpenSSHTransport) runtimeProtocolWithPrivateFlag(ctx context.Context, node Node, request map[string]any, flag string) (map[string]any, error) {
	payload, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}
	// Resolve the active immutable release on the node, then invoke the fixed
	// protocol directly. No shell command is assembled from dynamic values.
	root := "/var/lib/platform-installer/runtime"
	releaseOutput, err := t.sshBounded(ctx, node, "sudo", []string{"-n", "readlink", "-f", root + "/current"}, nil, maxExecutionReleaseProbeBytes)
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	release := strings.TrimSpace(string(releaseOutput))
	if !strings.HasPrefix(release, root+"/releases/") || strings.ContainsAny(release, " \t\r\n") {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	active, err := t.sshBounded(ctx, node, "sudo", []string{"-n", "cat", root + "/state/active"}, nil, maxExecutionStateProbeBytes)
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	digest := parseFacts(string(active))["BUNDLE_DIGEST"]
	if !strings.HasPrefix(digest, "sha256:") || len(digest) != len("sha256:")+64 {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	args := []string{"-n", "env", "PYTHONPATH=" + release + "/ansible-core/tools", "python3", release + "/ansible-core/tools/execution_protocol.py", "--runtime-release", release, "--bundle-digest", digest, "--controller", release + "/ansible-core/tools/execution_controller.py"}
	if flag != "" {
		if flag != "--stage-target-host-trust" || len(payload) > 65536 {
			return nil, errors.New("TARGET_HOST_TRUST_INVALID")
		}
		args = append(args, flag)
	}
	responseLimit := maxExecutionProtocolResponseBytes
	if request["operation"] == "GetEvents" {
		responseLimit = maxExecutionEventPageResponseBytes
	} else if request["operation"] == "BuildProjectSnapshot" {
		responseLimit = maxProjectSnapshotResponseBytes
	}
	output, err := t.sshBounded(ctx, node, "sudo", args, payload, responseLimit)
	var response map[string]any
	decodeErr := errors.New("EXECUTION_PROTOCOL_RESPONSE_INVALID")
	if len(output) <= maxExecutionProtocolResponseBytes {
		decodeErr = json.Unmarshal(output, &response)
	}
	if decodeErr != nil {
		if err != nil {
			return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
		}
		return nil, errors.New("EXECUTION_PROTOCOL_RESPONSE_INVALID")
	}
	if code, ok := response["error"].(string); ok && code != "" {
		var findings []Finding
		if diagnostic, ok := response["diagnostic"].(map[string]any); ok {
			findings = decodeFindings(diagnostic["findings"])
		}
		return response, &ExecutionError{Code: code, Findings: findings}
	}
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	return response, nil
}

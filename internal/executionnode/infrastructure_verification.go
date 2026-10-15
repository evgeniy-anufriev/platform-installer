package executionnode

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"platform-installer/internal/coreadapter"
	"time"
)

type ExecutionMode string

const (
	FullProject              ExecutionMode = "FULL_PROJECT"
	ApplicationLibrariesOnly ExecutionMode = "APPLICATION_LIBRARIES_ONLY"
	InfrastructureVerifyOnly ExecutionMode = "INFRASTRUCTURE_VERIFY_ONLY"
)

func (m ExecutionMode) valid() bool {
	return m == FullProject || m == ApplicationLibrariesOnly || m == InfrastructureVerifyOnly
}

// InfrastructureVerification is an observation from Core, never Start authority.
type InfrastructureVerification struct {
	Status                    string                                 `json:"status"`
	Code                      *string                                `json:"code"`
	InfrastructureFingerprint *string                                `json:"infrastructureFingerprint"`
	EvidenceRevision          *string                                `json:"evidenceRevision"`
	Deployments               []InfrastructureDeploymentVerification `json:"deployments"`
}

type InfrastructureDeploymentVerification struct {
	DeploymentID   string `json:"deploymentId"`
	SourceRunID    string `json:"sourceRunId"`
	CoverageDigest string `json:"coverageDigest"`
	VerifiedAt     string `json:"verifiedAt"`
}

func (v InfrastructureVerification) Validate() bool {
	if v.Status != "PASS" && v.Status != "BLOCKED" && v.Status != "UNKNOWN" {
		return false
	}
	if v.Deployments == nil || len(v.Deployments) > 256 {
		return false
	}
	if v.Code != nil && *v.Code != "INFRA_VERIFY_MISSING" && *v.Code != "INFRA_VERIFY_STALE" && *v.Code != "INFRA_EVIDENCE_UNAVAILABLE" {
		return false
	}
	for _, digest := range []*string{v.InfrastructureFingerprint, v.EvidenceRevision} {
		if digest != nil && !validSHA256(*digest) {
			return false
		}
	}
	seen := map[string]bool{}
	for _, d := range v.Deployments {
		if len(d.DeploymentID) > 128 || !runtimeSecretDeploymentPattern.MatchString(d.DeploymentID) || seen[d.DeploymentID] || !validRuntimeToken(d.SourceRunID) || !validSHA256(d.CoverageDigest) || len(d.VerifiedAt) > 40 {
			return false
		}
		if _, err := time.Parse(time.RFC3339, d.VerifiedAt); err != nil {
			return false
		}
		seen[d.DeploymentID] = true
	}
	return true
}

func decodeInfrastructureVerification(raw any) (*InfrastructureVerification, error) {
	fields, ok := raw.(map[string]any)
	if !ok || len(fields) != 5 || !closedKeys(fields, "status", "code", "infrastructureFingerprint", "evidenceRevision", "deployments") {
		return nil, errors.New("INFRASTRUCTURE_VERIFICATION_RESPONSE_INVALID")
	}
	data, err := json.Marshal(raw)
	if err != nil || len(data) > 128*1024 {
		return nil, errors.New("INFRASTRUCTURE_VERIFICATION_RESPONSE_INVALID")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var result InfrastructureVerification
	if decoder.Decode(&result) != nil || decoder.Decode(new(any)) != io.EOF || !result.Validate() {
		return nil, errors.New("INFRASTRUCTURE_VERIFICATION_RESPONSE_INVALID")
	}
	return &result, nil
}

func b0PlanCapabilitySupported(c map[string]any) bool {
	if !closedKeys(c, "apiVersion", "kind", "bootstrapProtocol", "coreVersion", "catalogDigest", "schemaDigest", "runtime", "supportedOperations", "executionStart", "targetCredentialLease", "runtimeSecretDescriptors", "serviceConfigurationPreview", "deploymentPlanRequestVersions", "projectSnapshotRequestVersions", "applicationExecution", "infrastructureVerification") {
		return false
	}
	v, ok := c["infrastructureVerification"].(map[string]any)
	return c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha8" && c["kind"] == "ExecutionCapabilities" && contains(c["supportedOperations"], "BuildDeploymentPlan") && contains(c["deploymentPlanRequestVersions"], "platform.installer/execution-runtime/v1alpha4") && ok && closedKeys(v, "protocol", "executionModes", "requiredPlanRequestVersion", "manifestContract", "planContract") && v["protocol"] == "InfrastructureVerification/v1alpha1" && v["requiredPlanRequestVersion"] == "platform.installer/execution-runtime/v1alpha4" && v["manifestContract"] == "platform.installer/execution-manifest/v1alpha3" && v["planContract"] == "platform.installer/plan/v1alpha5" && validExecutionModes(v["executionModes"])
}

// ReadApplicationLibraries uses the existing target-free snapshot path. It
// does not resolve YAML locally or manufacture an empty success on old Core.
func (t OpenSSHTransport) ReadApplicationLibraries(ctx context.Context, node Node, root string, release map[string]any) (*coreadapter.ApplicationLibraries, error) {
	snapshot, err := t.BuildProjectSnapshot(ctx, node, root, release)
	if err != nil {
		return nil, err
	}
	if snapshot.ApplicationLibraries == nil {
		return nil, errors.New("APPLICATION_SNAPSHOT_RUNTIME_UNSUPPORTED")
	}
	return snapshot.ApplicationLibraries, nil
}

// BuildDeploymentPlanForMode reuses ordinary staging and the fixed Core operation.
// Unsupported runtimes fail before staging; there is no full-project fallback.
func (t OpenSSHTransport) BuildDeploymentPlanForMode(ctx context.Context, node Node, projectRoot string, release map[string]any, order []string, mode ExecutionMode, vaultSources map[string]string) (DeploymentPlan, error) {
	if projectRoot == "" || len(release) == 0 || !validModePlanInput(order, mode, vaultSources) {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_INPUT_INVALID")
	}
	c, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha4", "operation": "GetCapabilities"})
	if err != nil {
		return DeploymentPlan{}, err
	}
	if !b0PlanCapabilitySupported(c) {
		return DeploymentPlan{}, errors.New("EXECUTION_MODE_RUNTIME_UNSUPPORTED")
	}
	if vaultSources == nil {
		vaultSources = map[string]string{}
	}
	return t.buildDeploymentPlanRequest(ctx, node, projectRoot, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha4", "runtimeRelease": release, "deploymentOrder": order, "executionMode": string(mode), "applicationVaultSources": vaultSources})
}

func validExecutionModes(raw any) bool {
	values, ok := raw.([]any)
	return ok && len(values) == 3 && values[0] == string(FullProject) && values[1] == string(ApplicationLibrariesOnly) && values[2] == string(InfrastructureVerifyOnly)
}

func validModePlanInput(order []string, mode ExecutionMode, sources map[string]string) bool {
	if order == nil || len(order) > 256 || !mode.valid() || len(sources) > 16 {
		return false
	}
	for id, source := range sources {
		if len(id) > 128 || !runtimeSecretDeploymentPattern.MatchString(id) || (source != "RUNTIME_INPUT" && source != "CURRENT_RUN_BOOTSTRAP") {
			return false
		}
	}
	return true
}

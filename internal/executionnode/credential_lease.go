package executionnode

// UI-02C private Execution-Node credential transport. None of these values is
// exposed through the Wails facade; callers use it only while constructing one
// StartExecution/v1alpha2 request.

import (
	"context"
	"encoding/json"
	"errors"
	"regexp"
	"strings"
)

var runtimeSecretRequirementPattern = regexp.MustCompile(`^[a-z][a-z0-9-]{0,63}$`)

const (
	credentialLeaseProtocol    = "PutRuntimeSecretLease/v1alpha1"
	credentialPayloadVersion   = "TargetCredentialLeasePayload/v1alpha1"
	credentialPayloadVersionV2 = "TargetCredentialLeasePayload/v1alpha2"
	credentialPayloadVersionV3 = "TargetCredentialLeasePayload/v1alpha3"
	startProtocolV2            = "StartExecution/v1alpha2"
	maxRuntimeSecretValues     = 16
	maxRuntimeSecretValueBytes = 4096
	maxRuntimeSecretTotalBytes = 65536
)

type CredentialLeaseRequest struct {
	RequestID, StartAttemptID, ProjectIdentity, ProjectRevision, PlanFingerprint, ExecutionManifestDigest string
	RuntimeRelease                                                                                        map[string]any
}

type TargetCredentialLeasePayload struct {
	Username, Password, PrivateKey, SudoPassword, PKIStorePassword string
	RuntimeSecretValues                                            map[string]string
}

type CredentialLeaseResponse struct {
	RequestID, StartAttemptID, Status, LeaseID, StagedExpiresAt string
}

type CredentialStartCapability struct {
	APIVersion      string
	MaxPayloadBytes int
	PayloadVersions []string
}

type ExecutionStartV2Request struct {
	StartAttemptID, ProjectIdentity, ProjectRevision, PlanFingerprint, ExecutionManifestDigest, LeaseID string
	RuntimeRelease                                                                                      map[string]any
}

type ExecutionStartV2Response struct{ Status, StartAttemptID, RunID string }

func (t OpenSSHTransport) CredentialStartCapability(ctx context.Context, node Node) (CredentialStartCapability, error) {
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetCapabilities"})
	if err != nil {
		return CredentialStartCapability{}, err
	}
	version, _ := response["apiVersion"].(string)
	allowed := []string{"apiVersion", "kind", "bootstrapProtocol", "coreVersion", "catalogDigest", "schemaDigest", "runtime", "supportedOperations", "executionStart", "targetCredentialLease", "projectSnapshotRequestVersions"}
	if version == "platform.installer/execution-capabilities/v1alpha3" {
		allowed = append(allowed, "runtimeSecretDescriptors")
	}
	if (version != "platform.installer/execution-capabilities/v1alpha2" && version != "platform.installer/execution-capabilities/v1alpha3") || response["kind"] != "ExecutionCapabilities" || !closedKeys(response, allowed...) {
		return CredentialStartCapability{}, errors.New("TARGET_CREDENTIAL_LEASE_UNSUPPORTED")
	}
	start, startOK := response["executionStart"].(map[string]any)
	lease, leaseOK := response["targetCredentialLease"].(map[string]any)
	if !startOK || !leaseOK || !closedKeys(start, "protocol") || start["protocol"] != startProtocolV2 || !closedKeys(lease, "protocol", "payloadVersions", "maxPayloadBytes", "requiredStartProtocol") || lease["protocol"] != credentialLeaseProtocol || lease["requiredStartProtocol"] != startProtocolV2 {
		return CredentialStartCapability{}, errors.New("TARGET_CREDENTIAL_LEASE_UNSUPPORTED")
	}
	versions, ok := decodeCredentialPayloadVersions(lease["payloadVersions"])
	if !ok {
		return CredentialStartCapability{}, errors.New("TARGET_CREDENTIAL_LEASE_UNSUPPORTED")
	}
	maximum, ok := exactPositiveInt(lease["maxPayloadBytes"])
	if !ok || maximum > 1088*1024 || !contains(response["supportedOperations"], "PutRuntimeSecretLease") {
		return CredentialStartCapability{}, errors.New("TARGET_CREDENTIAL_LEASE_UNSUPPORTED")
	}
	if version == "platform.installer/execution-capabilities/v1alpha3" && !validRuntimeSecretDescriptorCapability(response["runtimeSecretDescriptors"], response["supportedOperations"]) {
		return CredentialStartCapability{}, errors.New("TARGET_CREDENTIAL_LEASE_UNSUPPORTED")
	}
	return CredentialStartCapability{APIVersion: version, MaxPayloadBytes: maximum, PayloadVersions: versions}, nil
}

func validRuntimeSecretDescriptorCapability(raw any, operations any) bool {
	value, ok := raw.(map[string]any)
	if !ok || !closedKeys(value, "protocol", "maxDescriptors", "maxHostsPerDescriptor", "maxResponseBytes") || value["protocol"] != "BuildRuntimeSecretDescriptors/v1alpha1" || !contains(operations, "BuildRuntimeSecretDescriptors") {
		return false
	}
	maxDescriptors, ok1 := exactPositiveInt(value["maxDescriptors"])
	maxHosts, ok2 := exactPositiveInt(value["maxHostsPerDescriptor"])
	maxResponse, ok3 := exactPositiveInt(value["maxResponseBytes"])
	return ok1 && ok2 && ok3 && maxDescriptors == 16 && maxHosts == 256 && maxResponse == 65536
}

func decodeCredentialPayloadVersions(raw any) ([]string, bool) {
	values, ok := raw.([]any)
	if !ok || len(values) < 1 || len(values) > 3 {
		return nil, false
	}
	result := make([]string, len(values))
	for index, value := range values {
		text, ok := value.(string)
		if !ok || (text != credentialPayloadVersion && text != credentialPayloadVersionV2 && text != credentialPayloadVersionV3) || (index > 0 && text <= result[index-1]) {
			return nil, false
		}
		result[index] = text
	}
	if result[0] != credentialPayloadVersion || (len(result) > 1 && result[1] != credentialPayloadVersionV2) || (len(result) > 2 && result[2] != credentialPayloadVersionV3) {
		return nil, false
	}
	return result, true
}

func (c CredentialStartCapability) supportsPayloadVersion(version string) bool {
	for _, candidate := range c.PayloadVersions {
		if candidate == version {
			return true
		}
	}
	return false
}

func (t OpenSSHTransport) PutRuntimeSecretLease(ctx context.Context, node Node, request CredentialLeaseRequest, payload TargetCredentialLeasePayload, maxPayloadBytes int) (CredentialLeaseResponse, error) {
	if !validCredentialLeaseRequest(request) || maxPayloadBytes < 1 || maxPayloadBytes > 1088*1024 || (payload.Password == "") == (payload.PrivateKey == "") || payload.Username == "" || !validPKIStorePassword(payload.PKIStorePassword) || !validRuntimeSecretValues(payload.RuntimeSecretValues) {
		return CredentialLeaseResponse{}, errors.New("TARGET_CREDENTIAL_LEASE_INPUT_INVALID")
	}
	version := credentialPayloadVersion
	body := map[string]any{"apiVersion": version, "kind": "TargetCredentialLeasePayload", "username": payload.Username, "password": nil, "privateKey": nil, "sudoPassword": nil}
	if payload.RuntimeSecretValues != nil {
		version = credentialPayloadVersionV3
		body["apiVersion"] = version
		body["pkiStorePassword"] = payload.PKIStorePassword
		body["runtimeSecretValues"] = payload.RuntimeSecretValues
	} else if payload.PKIStorePassword != "" {
		version = credentialPayloadVersionV2
		body["apiVersion"] = version
		body["pkiStorePassword"] = payload.PKIStorePassword
	}
	if payload.Password != "" {
		body["password"] = payload.Password
	} else {
		body["privateKey"] = payload.PrivateKey
	}
	if payload.SudoPassword != "" {
		body["sudoPassword"] = payload.SudoPassword
	}
	encoded, err := json.Marshal(body)
	if err != nil || len(encoded) > maxPayloadBytes {
		return CredentialLeaseResponse{}, errors.New("TARGET_CREDENTIAL_LEASE_INPUT_INVALID")
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/runtime-secret-lease/v1alpha1", "kind": "PutRuntimeSecretLeaseRequest", "requestId": request.RequestID, "startAttemptId": request.StartAttemptID, "projectIdentity": request.ProjectIdentity, "projectRevision": request.ProjectRevision, "planFingerprint": request.PlanFingerprint, "executionManifestDigest": request.ExecutionManifestDigest, "runtimeRelease": request.RuntimeRelease, "payload": body})
	if err != nil {
		return CredentialLeaseResponse{}, err
	}
	result := CredentialLeaseResponse{}
	for _, field := range []struct {
		raw any
		dst *string
	}{{response["requestId"], &result.RequestID}, {response["startAttemptId"], &result.StartAttemptID}, {response["status"], &result.Status}, {response["leaseId"], &result.LeaseID}, {response["stagedExpiresAt"], &result.StagedExpiresAt}} {
		value, ok := field.raw.(string)
		if !ok || value == "" || len(value) > 256 {
			return CredentialLeaseResponse{}, errors.New("TARGET_CREDENTIAL_LEASE_RESPONSE_INVALID")
		}
		*field.dst = value
	}
	if result.RequestID != request.RequestID || result.StartAttemptID != request.StartAttemptID || (result.Status != "STORED" && result.Status != "ALREADY_STORED") || !validLowerHex(result.LeaseID, 32) {
		return CredentialLeaseResponse{}, errors.New("TARGET_CREDENTIAL_LEASE_RESPONSE_INVALID")
	}
	return result, nil
}

func validPKIStorePassword(value string) bool {
	if value == "" {
		return true
	}
	return len([]byte(value)) <= 4096 && strings.ToValidUTF8(value, "") == value
}

func validRuntimeSecretValues(values map[string]string) bool {
	if values == nil {
		return true
	}
	if len(values) == 0 || len(values) > maxRuntimeSecretValues {
		return false
	}
	total := 0
	for reference, value := range values {
		if !runtimeSecretRequirementPattern.MatchString(reference) || strings.ToValidUTF8(value, "") != value {
			return false
		}
		size := len([]byte(value))
		if size < 1 || size > maxRuntimeSecretValueBytes {
			return false
		}
		total += size
		if total > maxRuntimeSecretTotalBytes {
			return false
		}
	}
	return true
}

func (t OpenSSHTransport) StartExecutionV2(ctx context.Context, node Node, request ExecutionStartV2Request) (ExecutionStartV2Response, error) {
	if !validExecutionStartV2Request(request) {
		return ExecutionStartV2Response{}, errors.New("EXECUTION_START_INPUT_INVALID")
	}
	body := map[string]any{"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": request.StartAttemptID, "projectIdentity": request.ProjectIdentity, "projectRevision": request.ProjectRevision, "planFingerprint": request.PlanFingerprint, "executionManifestDigest": request.ExecutionManifestDigest, "runtimeRelease": request.RuntimeRelease}
	if request.LeaseID != "" {
		body["leaseId"] = request.LeaseID
	}
	response, err := t.runtimeProtocol(ctx, node, body)
	if err != nil {
		return ExecutionStartV2Response{}, err
	}
	if !closedKeys(response, "apiVersion", "kind", "status", "startAttemptId", "runId") || response["apiVersion"] != "platform.installer/execution-start/v1alpha2" || response["kind"] != "StartExecutionResponse" {
		return ExecutionStartV2Response{}, errors.New("EXECUTION_START_RESPONSE_INVALID")
	}
	result := ExecutionStartV2Response{}
	result.Status, _ = response["status"].(string)
	result.StartAttemptID, _ = response["startAttemptId"].(string)
	result.RunID, _ = response["runId"].(string)
	if (result.Status != "STARTED" && result.Status != "ALREADY_STARTED") || result.StartAttemptID != request.StartAttemptID || !validRuntimeToken(result.RunID) {
		return ExecutionStartV2Response{}, errors.New("EXECUTION_START_RESPONSE_INVALID")
	}
	return result, nil
}

func validCredentialLeaseRequest(r CredentialLeaseRequest) bool {
	return validLowerHex(r.RequestID, 32) && validLowerHex(r.StartAttemptID, 32) && candidateIdentityPattern.MatchString(r.ProjectIdentity) && validSHA256(r.ProjectRevision) && validSHA256(r.PlanFingerprint) && validSHA256(r.ExecutionManifestDigest) && validRuntimeRelease(r.RuntimeRelease)
}
func validExecutionStartV2Request(r ExecutionStartV2Request) bool {
	return validLowerHex(r.StartAttemptID, 32) && candidateIdentityPattern.MatchString(r.ProjectIdentity) && validSHA256(r.ProjectRevision) && validSHA256(r.PlanFingerprint) && validSHA256(r.ExecutionManifestDigest) && (r.LeaseID == "" || validLowerHex(r.LeaseID, 32)) && validRuntimeRelease(r.RuntimeRelease)
}
func validRuntimeRelease(raw map[string]any) bool {
	if len(raw) != 4 {
		return false
	}
	core, coreOK := raw["coreVersion"].(string)
	protocol, protoOK := raw["planningProtocol"].(string)
	return coreOK && core != "" && len(core) <= 256 && protoOK && protocol != "" && len(protocol) <= 256 && validSHA256(stringValue(raw["bundleDigest"])) && validSHA256(stringValue(raw["catalogDigest"]))
}
func stringValue(v any) string { s, _ := v.(string); return s }
func closedKeys(value map[string]any, keys ...string) bool {
	if len(value) != len(keys) {
		return false
	}
	for _, key := range keys {
		if _, ok := value[key]; !ok {
			return false
		}
	}
	return true
}
func exactPositiveInt(value any) (int, bool) {
	number, ok := value.(float64)
	if !ok || number < 1 || number != float64(int(number)) || number > float64(^uint(0)>>1) {
		return 0, false
	}
	return int(number), true
}
func contains(value any, target string) bool {
	values, ok := value.([]any)
	if !ok {
		return false
	}
	for _, item := range values {
		text, ok := item.(string)
		if ok && strings.TrimSpace(text) == target {
			return true
		}
	}
	return false
}

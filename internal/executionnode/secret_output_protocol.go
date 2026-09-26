package executionnode

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"strings"
)

const secretOutputProtocol = "SecretOutputDelivery/v1alpha1"

const (
	maxSecretOutputRequestBytes  = 8 * 1024
	maxSecretOutputResponseBytes = 64 * 1024
	maxSecretOutputStderrBytes   = 4 * 1024
)

var errSecretOutputProtocol = errors.New("SECRET_OUTPUT_PROTOCOL_UNAVAILABLE")
var ErrSecretOutputRecoveryRequired = errors.New("OUTPUT_RECOVERY_REQUIRED")
var secretOutputOpaqueID = regexp.MustCompile(`^[0-9a-f]{32}$`)
var secretOutputDeploymentID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
var secretOutputSourceRunID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)

type SecretOutputPackage struct {
	Protocol      string   `json:"protocol"`
	PackageID     string   `json:"packageId"`
	ProjectID     string   `json:"projectId"`
	DeploymentID  string   `json:"deploymentId"`
	SourceRunID   string   `json:"sourceRunId"`
	RuntimeDigest string   `json:"runtimeDigest"`
	Generation    int      `json:"generation"`
	State         string   `json:"state"`
	Entries       []string `json:"entries"`
}

type SecretOutputCapabilities struct {
	Protocol        string   `json:"protocol"`
	Operation       string   `json:"operation"`
	MaxPayloadBytes int      `json:"maxPayloadBytes"`
	Operations      []string `json:"operations"`
}

type SecretOutputList struct {
	Protocol   string                `json:"protocol"`
	Operation  string                `json:"operation"`
	ProjectID  string                `json:"projectId"`
	Packages   []SecretOutputPackage `json:"packages"`
	NextCursor *string               `json:"nextCursor"`
}

type SecretOutputAck struct {
	Protocol   string `json:"protocol"`
	Operation  string `json:"operation"`
	ProjectID  string `json:"projectId"`
	PackageID  string `json:"packageId"`
	Generation int    `json:"generation"`
	ReceiptID  string `json:"receiptId"`
	State      string `json:"state"`
}

// SecretOutputRequest is a closed-operation transport input. It accepts only
// the protocol's fixed request fields; no remote path or command is exposed.
type SecretOutputRequest struct {
	Operation         string
	ProjectID         string
	Limit             int
	Cursor            *string
	PackageID         string
	Generation        int
	ReceiptID         string
	CiphertextDigests map[string]string
}

func (t OpenSSHTransport) GetSecretOutputCapabilities(ctx context.Context, node Node, expectedRuntimeDigest, projectID string) (SecretOutputCapabilities, error) {
	request := SecretOutputRequest{Operation: "GetCapabilities", ProjectID: projectID}
	data, err := t.callSecretOutputProtocol(ctx, node, expectedRuntimeDigest, request, false)
	if err != nil {
		return SecretOutputCapabilities{}, err
	}
	var result SecretOutputCapabilities
	if err := decodeClosedJSON(data, &result); err != nil || result.Protocol != secretOutputProtocol || result.Operation != request.Operation || result.MaxPayloadBytes != maxSecretOutputResponseBytes || len(result.Operations) != 3 || result.Operations[0] != "ListPending" || result.Operations[1] != "Fetch" || result.Operations[2] != "Acknowledge" {
		return SecretOutputCapabilities{}, errSecretOutputProtocol
	}
	return result, nil
}

func (t OpenSSHTransport) ListPendingSecretOutputs(ctx context.Context, node Node, expectedRuntimeDigest, projectID string, limit int, cursor *string) (SecretOutputList, error) {
	request := SecretOutputRequest{Operation: "ListPending", ProjectID: projectID, Limit: limit, Cursor: cursor}
	data, err := t.callSecretOutputProtocol(ctx, node, expectedRuntimeDigest, request, false)
	if err != nil {
		return SecretOutputList{}, err
	}
	var result SecretOutputList
	if err := decodeClosedJSON(data, &result); err != nil || result.Protocol != secretOutputProtocol || result.Operation != request.Operation || result.ProjectID != projectID || result.Packages == nil || len(result.Packages) > limit {
		return SecretOutputList{}, errSecretOutputProtocol
	}
	if result.NextCursor != nil && !secretOutputOpaqueID.MatchString(*result.NextCursor) {
		return SecretOutputList{}, errSecretOutputProtocol
	}
	seen := make(map[string]bool, len(result.Packages))
	for _, item := range result.Packages {
		if item.Protocol != secretOutputProtocol || !secretOutputOpaqueID.MatchString(item.PackageID) || seen[item.PackageID] || item.ProjectID != projectID || !secretOutputDeploymentID.MatchString(item.DeploymentID) || len(item.DeploymentID) > 128 || !secretOutputSourceRunID.MatchString(item.SourceRunID) || !validSHA256(item.RuntimeDigest) || item.Generation < 1 || item.Generation > 2147483647 || (item.State != "READY" && item.State != "ACKED_CLEANUP_PENDING") || len(item.Entries) != 2 || item.Entries[0] != "admin-token" || item.Entries[1] != "unseal-shares" {
			return SecretOutputList{}, errSecretOutputProtocol
		}
		seen[item.PackageID] = true
	}
	return result, nil
}

func (t OpenSSHTransport) FetchSecretOutput(ctx context.Context, node Node, expectedRuntimeDigest, projectID, packageID string, generation int) ([]byte, error) {
	if !secretOutputOpaqueID.MatchString(packageID) || generation < 1 {
		return nil, errSecretOutputProtocol
	}
	return t.callSecretOutputProtocol(ctx, node, expectedRuntimeDigest, SecretOutputRequest{Operation: "Fetch", ProjectID: projectID, PackageID: packageID, Generation: generation}, true)
}

func (t OpenSSHTransport) AcknowledgeSecretOutput(ctx context.Context, node Node, expectedRuntimeDigest string, request SecretOutputRequest) (SecretOutputAck, error) {
	if request.Operation != "Acknowledge" || !secretOutputOpaqueID.MatchString(request.PackageID) || !secretOutputOpaqueID.MatchString(request.ReceiptID) || request.Generation < 1 || len(request.CiphertextDigests) != 2 || !validSHA256(request.CiphertextDigests["admin-token"]) || !validSHA256(request.CiphertextDigests["unseal-shares"]) {
		return SecretOutputAck{}, errSecretOutputProtocol
	}
	data, err := t.callSecretOutputProtocol(ctx, node, expectedRuntimeDigest, request, false)
	if err != nil {
		return SecretOutputAck{}, err
	}
	var result SecretOutputAck
	if err := decodeClosedJSON(data, &result); err != nil || result.Protocol != secretOutputProtocol || result.Operation != "Acknowledge" || result.ProjectID != request.ProjectID || result.PackageID != request.PackageID || result.Generation != request.Generation || result.ReceiptID != request.ReceiptID || (result.State != "DELIVERED" && result.State != "ACKED_CLEANUP_PENDING") {
		return SecretOutputAck{}, errSecretOutputProtocol
	}
	return result, nil
}

func (t OpenSSHTransport) callSecretOutputProtocol(ctx context.Context, node Node, expectedRuntimeDigest string, request SecretOutputRequest, binaryResponse bool) ([]byte, error) {
	if !validSHA256(expectedRuntimeDigest) || !candidateIdentityPattern.MatchString(request.ProjectID) {
		return nil, errSecretOutputProtocol
	}
	body := map[string]any{"protocol": secretOutputProtocol, "operation": request.Operation, "projectId": request.ProjectID}
	switch request.Operation {
	case "GetCapabilities":
	case "ListPending":
		if request.Limit < 1 || request.Limit > 32 {
			return nil, errSecretOutputProtocol
		}
		body["limit"] = request.Limit
		if request.Cursor != nil {
			if !secretOutputOpaqueID.MatchString(*request.Cursor) {
				return nil, errSecretOutputProtocol
			}
			body["cursor"] = *request.Cursor
		}
	case "Fetch":
		if !secretOutputOpaqueID.MatchString(request.PackageID) || request.Generation < 1 {
			return nil, errSecretOutputProtocol
		}
		body["packageId"], body["expectedGeneration"] = request.PackageID, request.Generation
	case "Acknowledge":
		if !secretOutputOpaqueID.MatchString(request.PackageID) || !secretOutputOpaqueID.MatchString(request.ReceiptID) || request.Generation < 1 || len(request.CiphertextDigests) != 2 || !validSHA256(request.CiphertextDigests["admin-token"]) || !validSHA256(request.CiphertextDigests["unseal-shares"]) {
			return nil, errSecretOutputProtocol
		}
		body["packageId"], body["expectedGeneration"] = request.PackageID, request.Generation
		body["receiptId"], body["ciphertextDigests"] = request.ReceiptID, request.CiphertextDigests
	default:
		return nil, errSecretOutputProtocol
	}
	input, err := json.Marshal(body)
	if err != nil || len(input) > maxSecretOutputRequestBytes {
		return nil, errSecretOutputProtocol
	}
	root := "/var/lib/platform-installer/runtime"
	releaseOutput, err := t.sshBounded(ctx, node, "sudo", []string{"-n", "readlink", "-f", root + "/current"}, nil, maxExecutionReleaseProbeBytes)
	if err != nil {
		return nil, errSecretOutputProtocol
	}
	release := strings.TrimSpace(string(releaseOutput))
	if !strings.HasPrefix(release, root+"/releases/") || strings.ContainsAny(release, " \t\r\n") {
		return nil, errSecretOutputProtocol
	}
	active, err := t.sshBounded(ctx, node, "sudo", []string{"-n", "cat", root + "/state/active"}, nil, maxExecutionStateProbeBytes)
	if err != nil || parseFacts(string(active))["BUNDLE_DIGEST"] != expectedRuntimeDigest {
		return nil, errSecretOutputProtocol
	}
	limit := maxSecretOutputResponseBytes
	if binaryResponse {
		limit = maxSecretOutputResponseBytes
	}
	args := []string{"-n", "env", "PYTHONPATH=" + release + "/ansible-core/tools", "python3", release + "/ansible-core/tools/execution_secret_output_protocol.py"}
	output, err := t.sshSeparatedBounded(ctx, node, "sudo", args, input, limit, maxSecretOutputStderrBytes)
	var failure struct {
		Protocol  string `json:"protocol"`
		Operation string `json:"operation"`
		ErrorCode string `json:"errorCode"`
	}
	if decodeClosedJSON(output, &failure) == nil && failure.Protocol == secretOutputProtocol && failure.Operation == request.Operation && failure.ErrorCode == "OUTPUT_RECOVERY_REQUIRED" {
		return nil, ErrSecretOutputRecoveryRequired
	}
	if err != nil {
		return nil, errSecretOutputProtocol
	}
	return output, nil
}

func decodeClosedJSON(data []byte, target any) error {
	if len(data) == 0 || !uniqueJSONKeys(data) {
		return errSecretOutputProtocol
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return errSecretOutputProtocol
	}
	return nil
}

func uniqueJSONKeys(data []byte) bool {
	decoder := json.NewDecoder(bytes.NewReader(data))
	if !scanUniqueJSONValue(decoder) {
		return false
	}
	var extra any
	return errors.Is(decoder.Decode(&extra), io.EOF)
}

func scanUniqueJSONValue(decoder *json.Decoder) bool {
	token, err := decoder.Token()
	if err != nil {
		return false
	}
	delim, ok := token.(json.Delim)
	if !ok {
		return true
	}
	switch delim {
	case '{':
		seen := map[string]struct{}{}
		for decoder.More() {
			keyToken, err := decoder.Token()
			if err != nil {
				return false
			}
			key, ok := keyToken.(string)
			if !ok {
				return false
			}
			if _, exists := seen[key]; exists {
				return false
			}
			seen[key] = struct{}{}
			if !scanUniqueJSONValue(decoder) {
				return false
			}
		}
		end, err := decoder.Token()
		return err == nil && end == json.Delim('}')
	case '[':
		for decoder.More() {
			if !scanUniqueJSONValue(decoder) {
				return false
			}
		}
		end, err := decoder.Token()
		return err == nil && end == json.Delim(']')
	default:
		return false
	}
}

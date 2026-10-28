package executionnode

import (
	"context"
	"encoding/json"
	"errors"
	"sort"
)

const imagePlanRequestVersion = "platform.installer/execution-runtime/v1alpha6"

type ImagePreparationScope struct {
	ProjectIdentity          string                           `json:"projectIdentity"`
	ProjectRevision          string                           `json:"projectRevision"`
	DescriptorSetFingerprint string                           `json:"descriptorSetFingerprint"`
	TargetConnections        map[string]ImageTargetConnection `json:"targetConnections"`
	Requirements             []struct {
		RequirementRef       string   `json:"requirementRef"`
		Purpose              string   `json:"purpose"`
		Hosts                []string `json:"hosts"`
		ApplicationLibraries []string `json:"applicationLibraries"`
	} `json:"requirements"`
}

type ImageTargetConnection struct {
	Address string `json:"address"`
	Port    int    `json:"port"`
}

func (t OpenSSHTransport) imagePlanningCapabilities(ctx context.Context, node Node, fallback string) (map[string]any, error) {
	if len(serviceSelection(ctx)) > 0 {
		return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": serviceSelectionRequestVersion, "operation": "GetCapabilities"})
	}
	capability, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": selectionPlanRequestVersion, "operation": "GetCapabilities"})
	if err == nil && imagePlanCapabilitySupported(capability) {
		return capability, nil
	}
	capability, err = t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": imagePlanRequestVersion, "operation": "GetCapabilities"})
	if err == nil && imagePlanCapabilitySupported(capability) {
		return capability, nil
	}
	return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": fallback, "operation": "GetCapabilities"})
}

type ImagePreparationCredentials struct {
	Payload   TargetCredentialLeasePayload
	Approvals []TargetHostKeyApproval
}

type ImagePreparationCredentialProvider func(ImagePreparationScope) (ImagePreparationCredentials, error)
type imagePreparationContextKey struct{}

// WithImagePreparationCredentials scopes the existing session broker callback to
// one synchronous Create Plan; no credential values are retained by the builder.
func WithImagePreparationCredentials(ctx context.Context, provider ImagePreparationCredentialProvider) context.Context {
	return context.WithValue(ctx, imagePreparationContextKey{}, provider)
}

func imagePlanCapabilitySupported(c map[string]any) bool {
	images, ok := c["applicationImages"].(map[string]any)
	return ok && (c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha10" || selectionCapabilitySupported(c)) &&
		contains(c["supportedOperations"], "PrepareApplicationImages") && contains(c["deploymentPlanRequestVersions"], imagePlanRequestVersion) &&
		images["protocol"] == "PrepareApplicationImages/v1alpha1" && images["leaseProtocol"] == "platform.installer/application-image-preparation-lease/v1alpha1"
}

func (t OpenSSHTransport) prepareApplicationImages(ctx context.Context, node Node, request map[string]any) error {
	base := map[string]any{"apiVersion": request["apiVersion"], "operation": "PrepareApplicationImages", "runId": request["runId"], "runtimeRelease": request["runtimeRelease"]}
	describe := map[string]any{}
	for key, value := range base {
		describe[key] = value
	}
	describe["phase"] = "DESCRIBE"
	for _, key := range []string{"executionMode", "deploymentOrder", "skipInfrastructureVerify"} {
		describe[key] = request[key]
	}
	if request["apiVersion"] == selectionPlanRequestVersion || request["apiVersion"] == serviceSelectionRequestVersion {
		describe["skipApplicationLibraries"] = request["skipApplicationLibraries"]
		describe["applicationLibraryOrder"] = request["applicationLibraryOrder"]
	}
	if request["apiVersion"] == serviceSelectionRequestVersion {
		describe["skipServiceDeployments"] = request["skipServiceDeployments"]
	}
	response, err := t.runtimeProtocol(ctx, node, describe)
	if err != nil {
		return err
	}
	inputsDigest, ok := response["inputsDigest"].(string)
	if !ok || !validSHA256(inputsDigest) || response["status"] != "INPUTS_READY" {
		return errors.New("APPLICATION_IMAGE_PREPARATION_RESPONSE_INVALID")
	}
	encoded, err := json.Marshal(response["inputs"])
	var scope ImagePreparationScope
	if err != nil || json.Unmarshal(encoded, &scope) != nil || !validSHA256(scope.ProjectRevision) {
		return errors.New("APPLICATION_IMAGE_PREPARATION_RESPONSE_INVALID")
	}
	base["phase"], base["inputsDigest"] = "PREPARE", inputsDigest
	if len(scope.TargetConnections) > 0 {
		provider, ok := ctx.Value(imagePreparationContextKey{}).(ImagePreparationCredentialProvider)
		if !ok || provider == nil {
			return errors.New("TARGET_CREDENTIAL_REQUIRED")
		}
		credentials, err := provider(scope)
		if err != nil {
			return err
		}
		payload := credentials.Payload
		if payload.Username == "" || (payload.Password == "") == (payload.PrivateKey == "") || !validRuntimeSecretValues(payload.RuntimeSecretValues) {
			return errors.New("TARGET_CREDENTIAL_LEASE_INPUT_INVALID")
		}
		body := map[string]any{"apiVersion": credentialPayloadVersionV4, "kind": "TargetCredentialLeasePayload", "username": payload.Username,
			"password": nil, "privateKey": nil, "sudoPassword": nil, "pkiStorePassword": nil, "runtimeSecretValues": payload.RuntimeSecretValues, "runtimeSecretInputs": []any{}}
		if payload.RuntimeSecretValues == nil {
			body["runtimeSecretValues"] = map[string]string{}
		}
		if payload.Password != "" {
			body["password"] = payload.Password
		} else {
			body["privateKey"] = payload.PrivateKey
		}
		if payload.SudoPassword != "" {
			body["sudoPassword"] = payload.SudoPassword
		}
		base["preparationLease"] = map[string]any{"apiVersion": "platform.installer/application-image-preparation-lease/v1alpha1", "binding": response["leaseBinding"], "payload": body, "approvals": credentials.Approvals}
	}
	prepared, err := t.runtimeProtocol(ctx, node, base)
	if err != nil {
		return err
	}
	preparationDigest, ok := prepared["preparationDigest"].(string)
	if !ok || !validSHA256(preparationDigest) || prepared["status"] != "READY" {
		return errors.New("APPLICATION_IMAGE_PREPARATION_RESPONSE_INVALID")
	}
	request["applicationImagePreparation"] = preparationDigest
	return nil
}

func (s ImagePreparationScope) TargetIDs() []string {
	ids := make([]string, 0, len(s.TargetConnections))
	for id := range s.TargetConnections {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

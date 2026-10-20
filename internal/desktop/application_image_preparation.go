package desktop

import (
	"errors"
	"slices"
	"strings"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

// Called within synchronous Create Plan, while editMu protects the session.
func (a *App) imagePreparationCredentialsLocked(scope executionnode.ImagePreparationScope) (executionnode.ImagePreparationCredentials, error) {
	result := executionnode.ImagePreparationCredentials{}
	approvals, err := a.approvedTargetKeysForHostsLocked(scope.ProjectIdentity, scope.ProjectRevision, scope.TargetIDs())
	if err != nil {
		return result, err
	}
	result.Approvals = approvals
	if len(scope.Requirements) > 0 {
		evidence := a.runtimeSecretEvidence
		if evidence == nil || evidence.projectID != scope.ProjectIdentity || evidence.projectRevision != scope.ProjectRevision || a.binding == nil || evidence.nodeID != a.binding.node.ID || !runtimeEvidenceMatchesExpected(evidence.runtime, a.binding.reader.runtimeRelease) {
			return result, errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
		}
		for _, requirement := range scope.Requirements {
			found := false
			for _, item := range evidence.applicationInputs {
				if item.RequirementRef == requirement.RequirementRef && item.Purpose == requirement.Purpose && strings.HasPrefix(item.Purpose, "APPLICATION_REGISTRY_") && slices.Equal(item.Hosts, requirement.Hosts) && slices.Equal(item.ApplicationLibraries, requirement.ApplicationLibraries) {
					found = true
					break
				}
			}
			if !found {
				return result, errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
			}
		}
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return result, err
	}
	if len(scope.Requirements) > 0 {
		// The form saves pending values. Authorize promotion against the current
		// Core descriptor evidence before constructing the metadata-only payload.
		requirements := make([]string, 0)
		for _, item := range a.runtimeSecretEvidence.descriptors {
			if item.Purpose == "SERVICE_PASSWORD" {
				requirements = append(requirements, item.RequirementRef)
			}
		}
		for _, item := range a.runtimeSecretEvidence.applicationInputs {
			requirements = append(requirements, item.RequirementRef)
		}
		if err := a.secrets.PromotePendingRuntimeSecretValues(binding, requirements); err != nil {
			return result, err
		}
	}
	err = a.secrets.WithTargetCredential(binding, func(credential runtimesecret.TargetCredential) error {
		payload := executionnode.TargetCredentialLeasePayload{Username: credential.Username, SudoPassword: string(credential.SudoSecret), RuntimeSecretValues: map[string]string{}}
		if credential.SSHMode == runtimesecret.SSHPassword {
			payload.Password = string(credential.SSHSecret)
		} else {
			payload.PrivateKey = string(credential.SSHSecret)
		}
		for _, requirement := range scope.Requirements {
			value, ok := credential.RuntimeSecretValues[requirement.RequirementRef]
			if !ok || len(value) == 0 {
				return errors.New("APPLICATION_REGISTRY_RUNTIME_SECRET_REQUIRED")
			}
			payload.RuntimeSecretValues[requirement.RequirementRef] = string(value)
		}
		result.Payload = payload
		return nil
	})
	return result, err
}

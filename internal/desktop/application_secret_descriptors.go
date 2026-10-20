package desktop

import (
	"platform-installer/internal/executionnode"
	"regexp"
	"slices"
)

var applicationSecretRequirement = regexp.MustCompile(`^application-secret-[a-f0-9]{32}$`)
var applicationSecretID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
var applicationSecretHost = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)

func validApplicationSecretDescriptor(item executionnode.ApplicationSecretDescriptor) bool {
	if !applicationSecretRequirement.MatchString(item.RequirementRef) || !applicationSecretID.MatchString(item.SourceRef) || item.DisplayLabel == "" || len([]byte(item.DisplayLabel)) > 256 ||
		!slices.Equal(item.Operations, []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}) {
		return false
	}
	if item.Purpose == "APPLICATION_SECRET" || item.Purpose == "APPLICATION_REGISTRY_USERNAME" || item.Purpose == "APPLICATION_REGISTRY_PASSWORD" {
		if item.ProviderDeployment != nil {
			return false
		}
	} else if item.Purpose == "APPLICATION_VAULT_ADMIN_TOKEN" {
		if item.ProviderDeployment == nil || !applicationSecretID.MatchString(*item.ProviderDeployment) || item.SourceRef != "vault-admin-token-"+*item.ProviderDeployment {
			return false
		}
	} else {
		return false
	}
	for _, group := range []struct {
		values  []string
		pattern *regexp.Regexp
	}{{item.Hosts, applicationSecretHost}, {item.ApplicationLibraries, applicationSecretID}} {
		if len(group.values) == 0 || len(group.values) > 256 {
			return false
		}
		prior := ""
		for _, value := range group.values {
			if !group.pattern.MatchString(value) || value <= prior {
				return false
			}
			prior = value
		}
	}
	return true
}

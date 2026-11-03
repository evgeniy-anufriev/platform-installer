package desktop

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"regexp"
	"slices"
	"sort"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

var applicationSecretRequirement = regexp.MustCompile(`^application-secret-[a-f0-9]{32}$`)
var applicationSecretID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
var applicationSecretHost = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)

func applicationSecretSourceRequirements(inputs []executionnode.ApplicationSecretDescriptor) map[string]string {
	result := map[string]string{}
	for _, item := range inputs {
		if item.Purpose == "APPLICATION_SECRET" || item.Purpose == "APPLICATION_REGISTRY_USERNAME" || item.Purpose == "APPLICATION_REGISTRY_PASSWORD" {
			result[item.SourceRef] = item.RequirementRef
		}
	}
	return result
}

func validApplicationSecretDescriptor(item executionnode.ApplicationSecretDescriptor) bool {
	if !applicationSecretRequirement.MatchString(item.RequirementRef) || !applicationSecretID.MatchString(item.SourceRef) || item.DisplayLabel == "" || len([]byte(item.DisplayLabel)) > 256 ||
		!validApplicationSecretOperations(item.Operations) {
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

func validApplicationSecretOperations(operations []string) bool {
	allowed := []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY", "APPLICATION_LIBRARIES_POST_INSTALL"}
	var ordered []string
	for _, op := range allowed {
		if slices.Contains(operations, op) {
			ordered = append(ordered, op)
		}
	}
	return len(operations) > 0 && slices.Equal(operations, ordered)
}

type PendingApplicationSecretContext struct {
	ApplicationLibrary string `json:"applicationLibrary"`
	ApplicationSlot    string `json:"applicationSlot,omitempty"`
}

type pendingApplicationSecret struct{ key, source, account, field string }

func secretObject(value any) map[string]any { result, _ := value.(map[string]any); return result }

// Inventory only the source descriptors shown by the saved package editor.
// Templates remain opaque here; Core alone resolves them before attachment.
func (a *App) pendingApplicationSecretsLocked(input PendingApplicationSecretContext) ([]pendingApplicationSecret, error) {
	if a.current.Status != "OPEN" || a.current.Managed == nil || a.activeSession != "" {
		return nil, errors.New("PROJECT_CHANGES_UNSAVED")
	}
	library, ok := a.current.Managed.ApplicationLibraries[input.ApplicationLibrary]
	if !ok {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
	}
	ref, _ := library["libraryRef"].(string)
	definition := a.current.Managed.ApplicationPackages["library:"+ref].Definition
	defaults := secretObject(definition["provided_connections"])
	authored := secretObject(library["provided_connections"])
	if input.ApplicationSlot != "" {
		slot := secretObject(secretObject(definition["slots"])[input.ApplicationSlot])
		appRef, _ := slot["applicationRef"].(string)
		if appRef == "" {
			return nil, errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
		}
		app := a.current.Managed.ApplicationPackages["application:"+appRef].Definition
		defaults = secretObject(secretObject(app["defaults"])["accounts"])
		authored = secretObject(secretObject(library["applications"])[input.ApplicationSlot])
		authored = secretObject(authored["accounts"])
	}
	names := map[string]bool{}
	for name := range defaults {
		names[name] = true
	}
	for name := range authored {
		names[name] = true
	}
	var result []pendingApplicationSecret
	for name := range names {
		base := secretObject(secretObject(defaults[name])["credentials"])
		override := secretObject(secretObject(authored[name])["credentials"])
		fields := map[string]bool{}
		for field := range base {
			fields[field] = true
		}
		for field := range override {
			fields[field] = true
		}
		for field := range fields {
			value, exists := override[field]
			if !exists {
				value = base[field]
			}
			source := secretObject(secretObject(value)["source"])
			ref, _ := source["ref"].(string)
			if source["kind"] != "runtime_secret_ref" || ref == "" {
				continue
			}
			identity, _ := json.Marshal([]string{input.ApplicationLibrary, input.ApplicationSlot, ref})
			digest := sha256.Sum256(identity)
			result = append(result, pendingApplicationSecret{key: "pending-application:" + hex.EncodeToString(digest[:]), source: ref, account: name, field: field})
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].key < result[j].key })
	return result, nil
}

func (a *App) GetPendingApplicationRuntimeSecretDescriptors(input PendingApplicationSecretContext) RuntimeSecretDescriptorOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	items, err := a.pendingApplicationSecretsLocked(input)
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	revision, err := a.projectRevision(a.current.Root)
	if err != nil || revision != a.current.Managed.ProjectRevision {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE", Error: &ProjectOpenError{Code: "PROJECT_REVISION_CHANGED", Message: projectErrorMessage("PROJECT_REVISION_CHANGED")}}
	}
	binding, err := a.credentialBindingLocked()
	if err != nil {
		return RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE"}
	}
	keys := []string{}
	for _, item := range items {
		keys = append(keys, item.key)
	}
	presence := a.secrets.PendingApplicationSecretPresence(binding, keys)
	result := RuntimeSecretDescriptorOperation{Status: "READY", ProjectRevision: revision, ApplicationSecretAvailability: presence}
	seen := map[string]bool{}
	for _, item := range items {
		if seen[item.key] {
			continue
		}
		seen[item.key] = true
		result.ApplicationInputs = append(result.ApplicationInputs, executionnode.ApplicationSecretDescriptor{RequirementRef: item.key, SourceRef: item.source, Purpose: "APPLICATION_SECRET", ApplicationLibraries: []string{input.ApplicationLibrary}, DisplayLabel: item.account + ": " + item.field})
	}
	return result
}

func (a *App) setPendingApplicationSecretLocked(binding runtimesecret.Binding, input RuntimeSecretValuesInput) error {
	if input.DescriptorSetFingerprint != "" || input.ServiceDeployment != "" || input.ApplicationSourceValues != nil || len(input.Values) != 1 || input.Values[input.ApplicationRequirementRef] == "" {
		return errors.New("RUNTIME_SECRET_INPUT_INVALID")
	}
	items, err := a.pendingApplicationSecretsLocked(PendingApplicationSecretContext{ApplicationLibrary: input.ApplicationLibrary, ApplicationSlot: input.ApplicationSlot})
	if err != nil {
		return err
	}
	revision, err := a.projectRevision(a.current.Root)
	if err != nil || revision != input.ProjectRevision || revision != a.current.Managed.ProjectRevision {
		return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
	}
	for _, item := range items {
		if item.key == input.ApplicationRequirementRef {
			return a.secrets.SetPendingApplicationSecretValues(binding, map[string]string{item.key: input.Values[item.key]})
		}
	}
	return errors.New("RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND")
}

// Map editor inputs through Core's existing, runtime-attested projection. Go
// never evaluates a template or calculates an application's effective source.
func (a *App) pendingApplicationSourceBindingsLocked(binding runtimesecret.Binding, revision string, inputs []executionnode.ApplicationSecretDescriptor) (map[string]string, error) {
	result := applicationSecretSourceRequirements(inputs)
	if a.current.Managed == nil {
		return result, nil
	}
	type located struct {
		library, slot string
		pendingApplicationSecret
	}
	var locations []located
	for library, value := range a.current.Managed.ApplicationLibraries {
		contexts := []string{""}
		ref, _ := value["libraryRef"].(string)
		for slot := range secretObject(a.current.Managed.ApplicationPackages["library:"+ref].Definition["slots"]) {
			contexts = append(contexts, slot)
		}
		for _, slot := range contexts {
			items, err := a.pendingApplicationSecretsLocked(PendingApplicationSecretContext{ApplicationLibrary: library, ApplicationSlot: slot})
			if err != nil {
				return nil, err
			}
			for _, item := range items {
				locations = append(locations, located{library: library, slot: slot, pendingApplicationSecret: item})
			}
		}
	}
	keys := []string{}
	for _, item := range locations {
		keys = append(keys, item.key)
	}
	presence := a.secrets.PendingApplicationSecretPresence(binding, keys)
	if !slices.ContainsFunc(locations, func(item located) bool { return presence[item.key] }) {
		return result, nil
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	proof, err := a.binding.reader.BuildVerificationSnapshot(ctx, a.current.Root)
	if err != nil || proof.Snapshot == nil || proof.Snapshot.ProjectRevision != revision || proof.Snapshot.Partial || proof.Snapshot.ApplicationLibraries == nil {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE")
	}
	after, err := a.projectRevision(a.current.Root)
	if err != nil || after != revision || a.revalidateBindingBeforePublicationLocked(a.binding) != nil {
		return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
	}
	for _, item := range locations {
		if !presence[item.key] {
			continue
		}
		library := proof.Snapshot.ApplicationLibraries.Libraries[item.library]
		var accounts []map[string]json.RawMessage
		if item.slot == "" {
			accounts = append(accounts, library.ProvidedConnections)
		} else {
			for _, instance := range library.Instances {
				if instance.SlotID == item.slot {
					accounts = append(accounts, instance.CredentialRequirements)
				}
			}
		}
		for _, account := range accounts {
			var value map[string]any
			if json.Unmarshal(account[item.account], &value) != nil {
				continue
			}
			source := secretObject(secretObject(secretObject(value["credentials"])[item.field])["source"])
			if source["kind"] != "runtime_secret_ref" {
				continue
			}
			ref, _ := source["ref"].(string)
			for _, descriptor := range inputs {
				if descriptor.Purpose == "APPLICATION_SECRET" && descriptor.SourceRef == ref && slices.Contains(descriptor.ApplicationLibraries, item.library) {
					if previous := result[item.key]; previous != "" && previous != descriptor.RequirementRef {
						return nil, errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
					}
					result[item.key] = descriptor.RequirementRef
				}
			}
		}
	}
	return result, nil
}

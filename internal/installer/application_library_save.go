package installer

import (
	"encoding/json"
	"regexp"
	"strings"
)

var libraryInputID = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
var exactLibraryRef = regexp.MustCompile(`^[a-z][a-z0-9-]*@[0-9]+\.[0-9]+\.[0-9]+$`)
var registryAuthority = regexp.MustCompile(`^[a-z0-9][a-z0-9.-]*(?::[0-9]+)?$`)
var applicationSettingKeys = []string{"image", "command", "user", "restart", "parameters", "environment", "ports", "endpoint", "accounts", "provisioner", "readiness", "config_files", "config_directories", "config_archives", "topicBindings", "connections"}

func applicationEditOperation(op string) bool {
	switch op {
	case "CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment", "DeleteApplicationLibraryDeployment", "SetApplicationLibrarySlot", "RemoveApplicationLibrarySlot", "SetApplicationLibraryPlacement", "RemoveApplicationLibraryPlacement", "SetApplicationLibraryOverride", "RemoveApplicationLibraryOverride":
		return true
	}
	return false
}

func validLibraryInputID(s string) bool { return len(s) <= 128 && libraryInputID.MatchString(s) }

func validateApplicationEdit(c EditCommand) error {
	invalid := blocked("INVALID_EDIT_COMMAND", "Application library edit is invalid", "command")
	if c.APIVersion != EditCommandAPIVersionV11 || c.Kind != "EditCommand" || !validSHA256(c.BaseProjectRevision) || !validLibraryInputID(c.DeploymentID) {
		return invalid
	}
	fields := []string{"deploymentId"}
	switch c.Operation {
	case "CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment":
		fields = append(fields, "entity")
		if c.Entity == nil || !applicationKeys(c.Entity, "libraryRef", "runtimeRef", "runtime_directory", "bindings", "resources", "shared_secrets", "vault_ref", "applications", "overrides", "registry_credentials", "provided_connections") {
			return invalid
		}
		if c.Operation == "CreateApplicationLibraryDeployment" {
			if _, ok := c.Entity["libraryRef"]; !ok {
				return invalid
			}
			if _, ok := c.Entity["runtimeRef"]; !ok {
				return invalid
			}
		}
		for key, value := range c.Entity {
			if key == "overrides" && !applicationKeys(asMap(value), "environment", "parameters") {
				return invalid
			}
			if key == "libraryRef" {
				s, ok := value.(string)
				if !ok || !exactLibraryRef.MatchString(s) || len(s) > 160 {
					return invalid
				}
			} else if key == "runtime_directory" {
				s, ok := value.(string)
				if !ok || len(s) > 4096 {
					return invalid
				}
			} else if key == "runtimeRef" {
				s, ok := value.(string)
				if !ok || !validLibraryInputID(s) {
					return invalid
				}
			} else if asMap(value) == nil {
				return invalid
			}
			if key == "provided_connections" {
				if asMap(value) == nil {
					return blocked("INVALID_VALUE", "Provided connection overrides must be a map", "command")
				}
				for name, raw := range asMap(value) {
					entry := asMap(raw)
					if !validLibraryInputID(name) || entry == nil || !applicationKeys(entry, "parameters", "credentials") {
						return blocked("INVALID_VALUE", "Only parameters and credential sources can be overridden", "command")
					}
					for _, property := range []string{"parameters", "credentials"} {
						if value, exists := entry[property]; exists && asMap(value) == nil {
							return blocked("INVALID_VALUE", "Provided parameters and credentials must be maps", "command")
						}
					}
					for field, credential := range asMap(entry["credentials"]) {
						if !validLibraryInputID(field) || !validApplicationCredential(credential, true) {
							return blocked("SECRET_REFERENCE_INVALID", "Provided credential source is invalid", "command")
						}
					}
				}
			}
			if key == "applications" {
				for _, slot := range asMap(value) {
					if !validLibrarySlot(asMap(slot)) {
						return invalid
					}
				}
			}
		}
	case "SetApplicationLibrarySlot", "RemoveApplicationLibrarySlot":
		fields = append(fields, "entityId")
		if !validLibraryInputID(c.EntityID) {
			return invalid
		}
		if c.Operation == "SetApplicationLibrarySlot" {
			fields = append(fields, "entity")
			if !validLibrarySlot(c.Entity) {
				return invalid
			}
		}
	case "SetApplicationLibraryPlacement", "RemoveApplicationLibraryPlacement":
		fields = append(fields, "hostId")
		if !identifierPattern.MatchString(c.HostID) {
			return invalid
		}
		if c.Operation == "SetApplicationLibraryPlacement" {
			fields = append(fields, "placement")
			if c.Placement == nil || !applicationKeys(c.Placement, "overrides") {
				return invalid
			}
		}
	case "SetApplicationLibraryOverride", "RemoveApplicationLibraryOverride":
		fields = append(fields, "entityId", "hostId", "property", "setting")
		if c.EntityID != "" && !validLibraryInputID(c.EntityID) || c.HostID != "" && !identifierPattern.MatchString(c.HostID) || c.EntityID != "" && c.HostID != "" {
			return invalid
		}
		// Empty slot/host addresses the common library environment/parameters only.
		if c.EntityID == "" && c.HostID == "" && (c.Property != "" || c.Setting != "environment" && c.Setting != "parameters") {
			return invalid
		}
		if c.HostID != "" && c.Property != "parameters" && c.Property != "ports" {
			return invalid
		}
		if c.Property != "" && c.Property != "parameters" && c.Property != "environment" && c.Property != "ports" && c.Property != "endpoint" && c.Property != "connections" {
			return invalid
		}
		if !configurationSettingPattern.MatchString(c.Setting) {
			return invalid
		}
		if c.Property == "" && !applicationKeys(map[string]any{c.Setting: nil}, applicationSettingKeys...) {
			return invalid
		}
		if c.Operation == "SetApplicationLibraryOverride" {
			fields = append(fields, "value")
			if c.Value == nil {
				return invalid
			}
		}
	case "DeleteApplicationLibraryDeployment":
	default:
		return invalid
	}
	if err := validateCommandFields(c, fields...); err != nil {
		return err
	}
	for _, value := range []any{c.Entity, c.Placement} {
		if err := safeApplicationInput(value, 0); err != nil {
			return err
		}
	}
	if err := boundedApplicationInput(c.Value, 0); err != nil {
		return err
	}
	if c.Property == "" && (c.Setting == "accounts" || c.Setting == "connections") && c.Operation == "SetApplicationLibraryOverride" {
		if err := safeApplicationInput(map[string]any{c.Setting: c.Value}, 0); err != nil {
			return err
		}
	}
	if c.Operation == "SetApplicationLibraryOverride" {
		if (c.Property == "connections" && !validApplicationConnectionSettings(map[string]any{c.Setting: c.Value})) ||
			(c.Property == "" && c.Setting == "connections" && !validApplicationConnectionSettings(c.Value)) {
			return invalid
		}
	}
	data, err := json.Marshal(c)
	if err != nil || len(data) > 64*1024 {
		return invalid
	}
	return nil
}

func applicationKeys(m map[string]any, keys ...string) bool {
	for k := range m {
		found := false
		for _, allowed := range keys {
			if k == allowed {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	return true
}

func validLibrarySlot(m map[string]any) bool {
	if m == nil || !applicationKeys(m, "overrides", "accounts", "credentials") {
		return false
	}
	for key, value := range m {
		obj := asMap(value)
		if obj == nil {
			return false
		}
		if key == "overrides" && (!applicationKeys(obj, applicationSettingKeys...) || !validApplicationConnectionSettings(obj["connections"])) {
			return false
		}
		if key == "credentials" {
			if !applicationKeys(obj, "vault_binding") {
				return false
			}
			if raw, exists := obj["vault_binding"]; exists {
				binding, ok := raw.(string)
				if !ok || !validLibraryInputID(binding) {
					return false
				}
			}
		}
	}
	return true
}

// Bound authored input without classifying arbitrary parameter names as secrets.
// Declared credential descriptors retain their separate runtime reference rules.
func safeApplicationInput(v any, depth int) error {
	if depth > 16 {
		return blocked("INVALID_VALUE", "Application input nesting exceeds its limit", "command")
	}
	switch value := v.(type) {
	case map[string]any:
		if len(value) > 128 {
			return blocked("INVALID_VALUE", "Application input exceeds its limit", "command")
		}
		for key, item := range value {
			if key == "registry_credentials" {
				if asMap(item) == nil {
					return blocked("SECRET_REFERENCE_INVALID", "Registry credentials must contain runtime references", "command")
				}
				for registry, entry := range asMap(item) {
					if !registryAuthority.MatchString(registry) {
						return blocked("REGISTRY_AUTHORITY_INVALID", "Registry must be a host or host:port without scheme, path or credentials", "command")
					}
					pair := asMap(entry)
					if len(pair) != 2 || !applicationKeys(pair, "username", "password") {
						return blocked("SECRET_REFERENCE_INVALID", "Registry credentials require username and password references", "command")
					}
					for _, name := range []string{"username", "password"} {
						if !validApplicationCredential(pair[name], false) || asMap(asMap(pair[name])["source"])["kind"] != "runtime_secret_ref" {
							return blocked("SECRET_REFERENCE_INVALID", "Registry credentials accept runtime references only", "command")
						}
					}
				}
			}
			if key == "shared_secrets" {
				if asMap(item) == nil {
					return blocked("SECRET_REFERENCE_INVALID", "Shared secret descriptors must be a map", "command")
				}
				for _, raw := range asMap(item) {
					if !validApplicationCredential(raw, false) {
						return blocked("SECRET_REFERENCE_INVALID", "Shared secret source is invalid", "command")
					}
				}
			}
			if key == "accounts" {
				for _, account := range asMap(item) {
					fields := asMap(account)
					if fields == nil {
						return blocked("SECRET_REFERENCE_INVALID", "Account descriptor must be a map", "command")
					}
					if raw, exists := fields["credentials"]; exists && (asMap(raw) == nil || !applicationKeys(asMap(raw), "username", "password")) {
						return blocked("SECRET_REFERENCE_INVALID", "Account credentials are invalid", "command")
					}
					for name, raw := range asMap(fields["credentials"]) {
						if !validApplicationCredential(raw, name == "username") {
							return blocked("SECRET_REFERENCE_INVALID", "Credential source is invalid", "command")
						}
					}
				}
			}
			next := safeApplicationInput
			if key == "environment" || key == "parameters" || key == "grants" || key == "endpoint" || key == "config_files" || key == "config_directories" || key == "config_archives" {
				next = boundedApplicationInput
			}
			if err := next(item, depth+1); err != nil {
				return err
			}
		}
	case []any:
		if len(value) > 256 {
			return blocked("INVALID_VALUE", "Application list exceeds its limit", "command")
		}
		for _, item := range value {
			if err := safeApplicationInput(item, depth+1); err != nil {
				return err
			}
		}
	case string:
		if strings.Contains(value, "PRIVATE KEY-----") {
			return blocked("SECRET_VALUE_NOT_ALLOWED", "Secret material is not accepted", "command")
		}
	}
	return nil
}

// Match the closed source shapes in settings.schema.json, only at declared
// credential locations. Core still owns semantic resolution of these references.
func validApplicationCredential(raw any, allowLiteral bool) bool {
	descriptor := asMap(raw)
	if len(descriptor) != 1 || !applicationKeys(descriptor, "source") {
		return false
	}
	source := asMap(descriptor["source"])
	required := []string{"kind"}
	switch source["kind"] {
	case "generated":
	case "runtime_secret_ref":
		required = append(required, "ref")
	case "vault_ref":
		required = append(required, "binding", "mount", "document", "field")
	case "pki_credential":
		required = append(required, "binding", "credential")
	case "literal":
		if !allowLiteral {
			return false
		}
		required = append(required, "value")
	default:
		return false
	}
	if len(source) != len(required) || !applicationKeys(source, required...) {
		return false
	}
	for _, key := range required {
		value, ok := source[key].(string)
		if !ok || value == "" {
			return false
		}
		if key == "ref" {
			if len(value) > 128 || !(validLibraryInputID(value) || applicationTemplateRef.MatchString(value)) {
				return false
			}
		} else if key == "binding" || key == "mount" || key == "field" || key == "credential" {
			if !validLibraryInputID(value) {
				return false
			}
		}
	}
	return true
}

var applicationTemplateRef = regexp.MustCompile(`.*\{\{.+\}\}.*`)

func boundedApplicationInput(v any, depth int) error {
	if depth > 16 {
		return blocked("INVALID_VALUE", "Application input nesting exceeds its limit", "command")
	}
	switch x := v.(type) {
	case map[string]any:
		if len(x) > 128 {
			return blocked("INVALID_VALUE", "Application input exceeds its limit", "command")
		}
		for _, item := range x {
			if err := boundedApplicationInput(item, depth+1); err != nil {
				return err
			}
		}
	case []any:
		if len(x) > 256 {
			return blocked("INVALID_VALUE", "Application list exceeds its limit", "command")
		}
		for _, item := range x {
			if err := boundedApplicationInput(item, depth+1); err != nil {
				return err
			}
		}
	case string:
		if strings.Contains(x, "PRIVATE KEY-----") {
			return blocked("SECRET_VALUE_NOT_ALLOWED", "Private key material is not accepted", "command")
		}
	}
	return nil
}

func applicationMap(parent map[string]any, key string) (map[string]any, error) {
	if value, exists := parent[key]; exists {
		if m := asMap(value); m != nil {
			return m, nil
		}
		return nil, managedReadError("Application input root is malformed", key)
	}
	m := map[string]any{}
	parent[key] = m
	return m, nil
}

func (c *structuralCandidate) reduceApplicationEdit(cmd EditCommand) error {
	state, _, _, err := c.desired()
	if err != nil {
		return err
	}
	libraries, err := applicationMap(state, "applicationLibraryDeployments")
	if err != nil {
		return err
	}
	owner := asMap(libraries[cmd.DeploymentID])
	switch cmd.Operation {
	case "CreateApplicationLibraryDeployment":
		if owner != nil {
			return blocked("EDIT_COMMAND_CONFLICT", "Library deployment already exists", "command.deploymentId")
		}
		libraries[cmd.DeploymentID] = deepCopy(cmd.Entity)
	case "UpdateApplicationLibraryDeployment":
		if owner == nil {
			return referenceNotFound("deploymentId")
		}
		for key, value := range cmd.Entity {
			owner[key] = deepCopy(value)
		}
	case "DeleteApplicationLibraryDeployment":
		if owner == nil {
			return referenceNotFound("deploymentId")
		}
		delete(libraries, cmd.DeploymentID)
	default:
		if owner == nil {
			return referenceNotFound("deploymentId")
		}
		logical := desiredDocument
		if cmd.HostID != "" {
			inventory, e := c.inventory()
			if e != nil {
				return e
			}
			if inventory.targets[cmd.HostID] == nil {
				return referenceNotFound("hostId")
			}
			if _, e := c.hostDocument(cmd.HostID, true); e != nil {
				return e
			}
			logical = managedHostDocument(cmd.HostID)
			members, e := applicationMap(c.documents[logical], "platform_application_libraries")
			if e != nil {
				return e
			}
			if cmd.Operation == "SetApplicationLibraryPlacement" {
				members[cmd.DeploymentID] = deepCopy(cmd.Placement)
				c.dirty[logical] = true
				return nil
			}
			if cmd.Operation == "RemoveApplicationLibraryPlacement" {
				delete(members, cmd.DeploymentID)
				c.dirty[logical] = true
				return nil
			}
			owner = asMap(members[cmd.DeploymentID])
			if owner == nil {
				return referenceNotFound("placement")
			}
		} else if cmd.EntityID != "" {
			if cmd.Operation == "RemoveApplicationLibraryOverride" && asMap(owner["applications"]) == nil {
				return nil
			}
			slots, e := applicationMap(owner, "applications")
			if e != nil {
				return e
			}
			if cmd.Operation == "SetApplicationLibrarySlot" {
				current := asMap(slots[cmd.EntityID])
				if current == nil {
					current = map[string]any{}
					slots[cmd.EntityID] = current
				}
				for key, v := range cmd.Entity {
					current[key] = deepCopy(v)
				}
				c.dirty[logical] = true
				return nil
			}
			if cmd.Operation == "RemoveApplicationLibrarySlot" {
				delete(slots, cmd.EntityID)
				c.dirty[logical] = true
				return nil
			}
			owner = asMap(slots[cmd.EntityID])
			if owner == nil {
				if cmd.Operation == "RemoveApplicationLibraryOverride" {
					return nil
				}
				owner = map[string]any{}
				slots[cmd.EntityID] = owner
			}
		}
		if cmd.Operation == "RemoveApplicationLibraryOverride" && asMap(owner["overrides"]) == nil {
			return nil
		}
		overrides, e := applicationMap(owner, "overrides")
		if e != nil {
			return e
		}
		if cmd.Property != "" {
			if cmd.Operation == "RemoveApplicationLibraryOverride" && asMap(overrides[cmd.Property]) == nil {
				return nil
			}
			overrides, e = applicationMap(overrides, cmd.Property)
			if e != nil {
				return e
			}
		}
		if cmd.Operation == "RemoveApplicationLibraryOverride" {
			delete(overrides, cmd.Setting)
		} else {
			overrides[cmd.Setting] = deepCopy(cmd.Value)
		}
		c.dirty[logical] = true
		return nil
	}
	c.documents[desiredDocument]["platform_desired_state_contract"] = "platform.installer/project-desired-state/v3alpha1"
	c.dirty[desiredDocument] = true
	return nil
}

func (c *structuralCandidate) validateApplicationReferences() error {
	state, deployments, _, err := c.desired()
	if err != nil {
		return err
	}
	libraries := asMap(state["applicationLibraryDeployments"])
	if len(libraries) > 128 {
		return managedReadError("Too many library deployments", desiredDocument)
	}
	var packages map[string]ManagedApplicationPackage
	for _, raw := range libraries {
		library := asMap(raw)
		ref, _ := library["runtimeRef"].(string)
		if library == nil || deployments[ref] == nil {
			return referenceNotFound("runtimeRef")
		}
		for name, rawExport := range asMap(library["provided_connections"]) {
			for field, rawCredential := range asMap(asMap(rawExport)["credentials"]) {
				if asMap(asMap(rawCredential)["source"])["kind"] != "literal" {
					continue
				}
				if packages == nil {
					packages, err = readManagedApplicationPackages(c.root)
					if err != nil {
						return err
					}
				}
				packageRef, _ := library["libraryRef"].(string)
				declaration := asMap(asMap(packages["library:"+packageRef].Definition["provided_connections"])[name])
				credential := asMap(asMap(declaration["credentials"])[field])
				if sensitive, declared := credential["sensitive"].(bool); !declared || sensitive {
					return blocked("SECRET_REFERENCE_INVALID", "Literal credential requires an explicitly non-sensitive package declaration", "provided_connections")
				}
			}
		}
		for _, rawBinding := range asMap(library["bindings"]) {
			ref, _ := asMap(rawBinding)["deploymentRef"].(string)
			if ref != "" && deployments[ref] == nil {
				return referenceNotFound("bindings")
			}
		}
	}
	inventory, err := c.inventory()
	if err != nil {
		return err
	}
	for logical, doc := range c.documents {
		if !strings.HasPrefix(logical, "inventory/host_vars/") {
			continue
		}
		for id := range asMap(doc["platform_application_libraries"]) {
			if libraries[id] == nil || inventory.targets[hostIDFromManagedDocument(logical)] == nil {
				return referenceInUse("applicationLibraryPlacement")
			}
		}
	}
	return nil
}

// Paths describe authored writes, not resolved application settings.
func applicationWritePaths(c EditCommand) []string {
	root := "library/" + c.DeploymentID
	if c.HostID != "" {
		root = "host/" + c.HostID + "/library/" + c.DeploymentID
	}
	switch c.Operation {
	case "CreateApplicationLibraryDeployment":
		// Creation may be followed by slot and placement edits in the same session.
		paths := []string{root + "/@create"}
		for key := range c.Entity {
			paths = append(paths, root+"/"+key)
		}
		return paths
	case "UpdateApplicationLibraryDeployment":
		var paths []string
		for key := range c.Entity {
			paths = append(paths, root+"/"+key)
		}
		return paths
	case "DeleteApplicationLibraryDeployment", "RemoveApplicationLibraryPlacement":
		return []string{root}
	case "SetApplicationLibraryPlacement":
		var paths []string
		for key := range c.Placement {
			paths = append(paths, root+"/"+key)
		}
		return paths
	case "RemoveApplicationLibrarySlot":
		return []string{root + "/applications/" + c.EntityID}
	case "SetApplicationLibrarySlot":
		var paths []string
		for key := range c.Entity {
			paths = append(paths, root+"/applications/"+c.EntityID+"/"+key)
		}
		return paths
	default:
		if c.EntityID != "" {
			root += "/applications/" + c.EntityID
		}
		root += "/overrides"
		if c.Property != "" {
			root += "/" + c.Property
		}
		return []string{root + "/" + c.Setting}
	}
}

// Validate the authored settings surface, not package connection declarations or arbitrary parameters.
func validApplicationConnectionSettings(v any) bool {
	if v == nil {
		return true
	}
	entries := asMap(v)
	if entries == nil {
		return false
	}
	for name, raw := range entries {
		entry := asMap(raw)
		if !validLibraryInputID(name) || entry == nil || !applicationKeys(entry, "enabled") {
			return false
		}
		if _, ok := entry["enabled"].(bool); !ok {
			return false
		}
	}
	return true
}

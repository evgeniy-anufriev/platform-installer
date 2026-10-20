package installer

import (
	"strings"
	"testing"
)

func TestRegistryCredentialsSaveOnlyRuntimeReferences(t *testing.T) {
	source := func(ref string) any {
		return map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": ref}}
	}
	pair := map[string]any{"username": source("registry-user"), "password": source("registry-password")}
	command := EditCommand{APIVersion: EditCommandAPIVersionV11, Kind: "EditCommand", BaseProjectRevision: "sha256:" + strings.Repeat("a", 64),
		Operation: "UpdateApplicationLibraryDeployment", DeploymentID: "sdku-main", Entity: map[string]any{"registry_credentials": map[string]any{"registry.example": pair}}}
	if err := validateApplicationEdit(command); err != nil {
		t.Fatal(err)
	}
	for _, invalid := range []any{"plaintext", map[string]any{"source": map[string]any{"kind": "literal", "value": "fixture-only"}}, map[string]any{"source": map[string]any{"kind": "generated"}}} {
		pair["password"] = invalid
		if err := validateApplicationEdit(command); err == nil {
			t.Fatal("accepted non-runtime registry password")
		}
	}
	pair["password"] = source("registry-password")
	for _, registry := range []string{"https://registry.example", "registry.example/team", "user@registry.example", "*.example", "[::1]:5000", "registry.example:", "registry.example:port", "Registry.example"} {
		command.Entity["registry_credentials"] = map[string]any{registry: pair}
		if err := validateApplicationEdit(command); err == nil {
			t.Fatalf("accepted malformed authority %q", registry)
		}
	}
	command.Entity["registry_credentials"] = map[string]any{"localhost:5000": pair}
	if err := validateApplicationEdit(command); err != nil {
		t.Fatalf("host:port rejected: %v", err)
	}
}

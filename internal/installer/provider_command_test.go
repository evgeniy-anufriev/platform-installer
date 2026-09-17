package installer

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestV6ProviderCommandValidation(t *testing.T) {
	revision := "sha256:" + strings.Repeat("a", 64)
	valid := EditCommand{
		APIVersion: EditCommandAPIVersionV6, Kind: "EditCommand", BaseProjectRevision: revision,
		Operation: "ReconcileEndpointProvider", DeploymentID: "keepalived-main", EndpointGroupID: "edge",
		VirtualRouterID: 42, VirtualAddresses: []VirtualAddress{{Address: "192.0.2.42", Interface: "eth0"}},
	}
	if err := validateCommand(valid); err != nil {
		t.Fatalf("valid provider command: %v", err)
	}
	for name, command := range map[string]EditCommand{
		"empty addresses": func() EditCommand { value := valid; value.VirtualAddresses = nil; return value }(),
		"router range":    func() EditCommand { value := valid; value.VirtualRouterID = 0; return value }(),
		"ipv6": func() EditCommand {
			value := valid
			value.VirtualAddresses = []VirtualAddress{{Address: "2001:db8::1", Interface: "eth0"}}
			return value
		}(),
		"interface length": func() EditCommand {
			value := valid
			value.VirtualAddresses = []VirtualAddress{{Address: "192.0.2.42", Interface: strings.Repeat("e", 129)}}
			return value
		}(),
		"duplicate": func() EditCommand {
			value := valid
			value.VirtualAddresses = []VirtualAddress{{Address: "192.0.2.42", Interface: "eth0"}, {Address: "192.0.2.42", Interface: "eth0"}}
			return value
		}(),
	} {
		t.Run(name, func(t *testing.T) {
			if err := validateCommand(command); err == nil {
				t.Fatal("expected invalid provider command")
			}
		})
	}
}

func TestV7SessionAcceptsInheritedProviderCommands(t *testing.T) {
	revision := "sha256:" + strings.Repeat("a", 64)
	for _, command := range []EditCommand{
		{APIVersion: EditCommandAPIVersionV7, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "ReconcileEndpointProvider", DeploymentID: "keepalived-main", EndpointGroupID: "edge", VirtualRouterID: 42, VirtualAddresses: []VirtualAddress{{Address: "192.0.2.42", Interface: "eth0"}}},
		{APIVersion: EditCommandAPIVersionV7, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "ClearEndpointProvider", DeploymentID: "keepalived-main"},
	} {
		if err := validateCommand(command); err != nil {
			t.Fatalf("%s rejected by v1alpha7: %v", command.Operation, err)
		}
	}
}

func TestV6ProviderCommandRejectsUnknownNestedField(t *testing.T) {
	revision := "sha256:" + strings.Repeat("a", 64)
	content := `{"apiVersion":"platform.installer/edit-command/v1alpha6","kind":"EditCommand","baseProjectRevision":"` + revision + `","operation":"ReconcileEndpointProvider","deploymentId":"keepalived-main","endpointGroupId":"edge","virtualRouterId":42,"virtualAddresses":[{"address":"192.0.2.42","interface":"eth0","rawYaml":"unsafe"}]}`
	var command EditCommand
	if err := json.Unmarshal([]byte(content), &command); err != nil {
		t.Fatal(err)
	}
	if err := validateCommand(command); err == nil {
		t.Fatal("expected unknown nested field rejection")
	}
}

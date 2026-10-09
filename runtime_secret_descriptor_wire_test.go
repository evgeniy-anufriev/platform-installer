package main

import (
	"encoding/json"
	"reflect"
	"sort"
	"testing"
)

func TestRuntimeSecretDescriptorWireUsesExistingLowerCamelShape(t *testing.T) {
	operation := RuntimeSecretDescriptorOperation{Status: "READY", ProjectRevision: "revision",
		DescriptorSetFingerprint: "fingerprint", Descriptors: []RuntimeSecretDescriptorView{{
			RequirementRef: "requirement", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-qa",
			Setting: "setting", DisplayLabel: "Admin token", RequiredWhen: "INITIALIZED",
			Operations: []string{"SERVICE_APPLY"}, ReferenceConfigured: true, Hosts: []string{"node1"},
		}}}
	encoded, err := json.Marshal(operation)
	if err != nil {
		t.Fatal(err)
	}
	var wire map[string]any
	if err := json.Unmarshal(encoded, &wire); err != nil {
		t.Fatal(err)
	}
	assertWireKeys := func(value map[string]any, expected []string) {
		t.Helper()
		actual := make([]string, 0, len(value))
		for key := range value {
			actual = append(actual, key)
		}
		sort.Strings(actual)
		sort.Strings(expected)
		if !reflect.DeepEqual(actual, expected) {
			t.Fatalf("unexpected wire keys: %v, want %v", actual, expected)
		}
	}
	assertWireKeys(wire, []string{"status", "projectRevision", "descriptorSetFingerprint", "descriptors"})
	if wire["status"] != "READY" {
		t.Fatal("READY status lost")
	}
	descriptor := wire["descriptors"].([]any)[0].(map[string]any)
	assertWireKeys(descriptor, []string{"requirementRef", "purpose", "serviceDeployment", "setting",
		"displayLabel", "requiredWhen", "operations", "referenceConfigured", "hosts"})
	var decoded RuntimeSecretDescriptorOperation
	if err := json.Unmarshal(encoded, &decoded); err != nil || !reflect.DeepEqual(decoded, operation) {
		t.Fatal("descriptor data changed during wire round-trip")
	}
}

func TestRuntimeSecretDescriptorUnavailableWireHasSafeLowerCamelError(t *testing.T) {
	encoded, err := json.Marshal(RuntimeSecretDescriptorOperation{Status: "UNAVAILABLE",
		Error: &ProjectOpenError{Code: "PROJECT_NOT_OPEN", Message: "Project not open"}})
	if err != nil {
		t.Fatal(err)
	}
	var wire map[string]any
	if err := json.Unmarshal(encoded, &wire); err != nil {
		t.Fatal(err)
	}
	if len(wire) != 2 || wire["status"] != "UNAVAILABLE" || wire["error"].(map[string]any)["code"] != "PROJECT_NOT_OPEN" {
		t.Fatalf("unsafe unavailable wire: %s", encoded)
	}
	if _, present := wire["descriptors"]; present {
		t.Fatal("absent descriptors should remain absent")
	}
}

func TestRuntimeSecretDescriptorWireIncludesConfirmedServiceSecretStatus(t *testing.T) {
	encoded, err := json.Marshal(RuntimeSecretDescriptorOperation{Status: "READY", SecretsInstalled: true})
	if err != nil {
		t.Fatal(err)
	}
	var wire map[string]any
	if err := json.Unmarshal(encoded, &wire); err != nil {
		t.Fatal(err)
	}
	if wire["status"] != "READY" || wire["secretsInstalled"] != true || len(wire) != 2 {
		t.Fatalf("confirmed service status lost or unexpected metadata: %s", encoded)
	}
}

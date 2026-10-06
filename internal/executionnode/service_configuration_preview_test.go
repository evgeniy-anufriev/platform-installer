package executionnode

import (
	"strings"
	"testing"
)

func TestServiceConfigurationPreviewValueBoundary(t *testing.T) {
	tests := []struct {
		name  string
		value ServiceConfigurationValue
		valid bool
	}{
		{"ordinary value", ServiceConfigurationValue{State: "RESOLVED", Source: "ROLE_DEFAULT", Value: 8200.0}, true},
		{"ordinary string", ServiceConfigurationValue{State: "RESOLVED", Source: "DEPLOYMENT_OVERRIDE", Value: "service-user"}, true},
		{"unresolved state", ServiceConfigurationValue{State: "DEFERRED", Source: "RUNTIME_DEFERRED"}, true},
		{"secret object", ServiceConfigurationValue{State: "RESOLVED", Source: "ROLE_DEFAULT", Value: map[string]any{"passwordSecretRef": "runtime:secret"}}, false},
		{"unresolved value", ServiceConfigurationValue{State: "DEFERRED", Source: "RUNTIME_DEFERRED", Value: "{{ secret }}"}, false},
		{"oversized value", ServiceConfigurationValue{State: "RESOLVED", Source: "ROLE_DEFAULT", Value: strings.Repeat("x", 4097)}, false},
		{"unknown source", ServiceConfigurationValue{State: "RESOLVED", Source: "OTHER", Value: 1.0}, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := validPreviewValues(map[string]ServiceConfigurationValue{"apiPort": test.value})
			if got != test.valid {
				t.Fatalf("validPreviewValues=%v want %v", got, test.valid)
			}
		})
	}
	if validPreviewValues(map[string]ServiceConfigurationValue{"bad/id": tests[0].value}) {
		t.Fatal("invalid setting ID was admitted")
	}
}

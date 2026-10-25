package executionnode

import (
	"encoding/json"
	"os"
	"testing"
)

func TestApplicationProgressDecodeCloneAndDuplicateIDs(t *testing.T) {
	fixture, err := os.ReadFile("../../ansible-core/tests/fixtures/application-progress-service-action.json")
	if err != nil {
		t.Fatal(err)
	}
	var invalid map[string]any
	if err := json.Unmarshal(fixture, &invalid); err != nil {
		t.Fatal(err)
	}
	if _, err := decodeDeploymentPlanAction(invalid, map[string]bool{}); err == nil {
		t.Fatal("shared invalid schema fixture admitted by decoder")
	}
	action := map[string]any{"id": "applications:apply", "type": "APPLICATION_LIBRARIES_APPLY", "targets": []any{"node1"},
		"dependsOn": []any{}, "mutating": true, "reboot": "NONE", "summary": "Apply libraries",
		"progressSteps": []any{map[string]any{"id": "applications:prepare", "summary": "Prepare"},
			map[string]any{"id": "applications:library:sdku", "summary": "SDKU"}}}
	decoded, err := decodeDeploymentPlanAction(action, map[string]bool{})
	if err != nil || len(decoded.ProgressSteps) != 2 {
		t.Fatalf("steps lost: %+v %v", decoded, err)
	}
	cloned := clonePlanPhases([]DeploymentPlanPhase{{Actions: []DeploymentPlanAction{decoded}}})
	cloned[0].Actions[0].ProgressSteps[0].Summary = "changed"
	if decoded.ProgressSteps[0].Summary != "Prepare" {
		t.Fatal("caller can mutate retained plan")
	}
	steps := action["progressSteps"].([]any)
	steps[1].(map[string]any)["id"] = "applications:prepare"
	if _, err := decodeDeploymentPlanAction(action, map[string]bool{}); err == nil {
		t.Fatal("duplicate progress ID admitted")
	}
	steps[1].(map[string]any)["id"] = "applications:apply"
	if _, err := decodeDeploymentPlanAction(action, map[string]bool{}); err == nil {
		t.Fatal("parent ID admitted as child")
	}
	steps[1].(map[string]any)["id"] = "applications:library:sdku"
	action["type"] = "SERVICE_APPLY"
	if _, err := decodeDeploymentPlanAction(action, map[string]bool{}); err == nil {
		t.Fatal("service action can contain application steps")
	}
}

func TestApplicationProgressCapability(t *testing.T) {
	c := map[string]any{"apiVersion": "platform.installer/execution-capabilities/v1alpha13", "applicationProgress": map[string]any{
		"protocol": "ApplicationProgress/v1alpha1", "planContract": "platform.installer/plan/v1alpha10"}}
	if !applicationProgressCapabilitySupported(c) {
		t.Fatal("new capability rejected")
	}
	c["apiVersion"] = "platform.installer/execution-capabilities/v1alpha12"
	if applicationProgressCapabilitySupported(c) {
		t.Fatal("legacy capability silently promotes contract")
	}
}

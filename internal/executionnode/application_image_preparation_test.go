package executionnode

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

type imagePreparationRunner struct {
	b1PlanRunner
	steps     []string
	target    bool
	selection bool
	requests  []map[string]any
}

func (r *imagePreparationRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	var request map[string]any
	_ = json.Unmarshal(input, &request)
	r.requests = append(r.requests, request)
	switch request["operation"] {
	case "GetCapabilities":
		capability := b0Capability()
		capability["apiVersion"] = "platform.installer/execution-capabilities/v1alpha10"
		capability["skipInfrastructureVerify"] = true
		capability["supportedOperations"] = []any{"BuildDeploymentPlan", "PrepareApplicationImages"}
		capability["deploymentPlanRequestVersions"] = append(capability["deploymentPlanRequestVersions"].([]any), "platform.installer/execution-runtime/v1alpha5", imagePlanRequestVersion)
		capability["applicationImages"] = map[string]any{"protocol": "PrepareApplicationImages/v1alpha1", "leaseProtocol": "platform.installer/application-image-preparation-lease/v1alpha1"}
		if r.selection {
			capability["apiVersion"] = "platform.installer/execution-capabilities/v1alpha11"
			capability["applicationLibrarySelection"] = map[string]any{"protocol": "ApplicationLibrarySelection/v1alpha1"}
			capability["deploymentPlanRequestVersions"] = append(capability["deploymentPlanRequestVersions"].([]any), selectionPlanRequestVersion)
		}
		return json.Marshal(capability)
	case "PrepareApplicationImages":
		phase := request["phase"].(string)
		r.steps = append(r.steps, phase)
		if phase == "DESCRIBE" {
			targets := map[string]any{}
			if r.target {
				targets["node1"] = map[string]any{"address": "127.0.0.1", "port": 22}
			}
			return json.Marshal(map[string]any{"status": "INPUTS_READY", "inputsDigest": "sha256:" + strings.Repeat("a", 64),
				"inputs": map[string]any{"projectIdentity": "project-one", "projectRevision": "sha256:" + strings.Repeat("b", 64), "targetConnections": targets, "requirements": []any{}}, "leaseBinding": map[string]any{}})
		}
		if !r.target && request["preparationLease"] != nil {
			panic("offline preparation requested credentials")
		}
		return json.Marshal(map[string]any{"status": "READY", "preparationDigest": "sha256:" + strings.Repeat("c", 64)})
	case "BuildDeploymentPlan":
		r.steps = append(r.steps, "PLAN")
		version := "platform.installer/plan/v1alpha7"
		if r.selection {
			version = "platform.installer/plan/v1alpha8"
		}
		return json.Marshal(map[string]any{"deploymentPlan": map[string]any{"apiVersion": version, "skipApplicationLibraries": request["skipApplicationLibraries"],
			"executionMode": request["executionMode"], "skipInfrastructureVerify": false,
			"infrastructureVerification": r.summary, "id": "plan-images", "status": "BLOCKED", "projectIdentity": "project-one",
			"projectRevision": "sha256:" + strings.Repeat("b", 64), "fingerprints": map[string]any{"plan": "sha256:" + strings.Repeat("d", 64)},
			"runtimeRelease": request["runtimeRelease"], "acknowledgements": []any{}, "phases": []any{}, "requiredCredentials": []any{}, "findings": []any{}}})
	}
	return r.b1PlanRunner.RunBounded(ctx, name, args, input, limit)
}

func TestImageMetadataPreparationPrecedesAuthoritativePlan(t *testing.T) {
	for _, target := range []bool{false, true} {
		root := t.TempDir()
		if err := os.Mkdir(filepath.Join(root, "inventory"), 0o700); err != nil {
			t.Fatal(err)
		}
		runner := &imagePreparationRunner{b1PlanRunner: b1PlanRunner{summary: testInfrastructureSummary(t)}, target: target}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		plan, err := transport.BuildDeploymentPlanForMode(context.Background(), testNode(), root,
			map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{}, ApplicationLibrariesOnly, nil)
		if target {
			if err == nil || err.Error() != "TARGET_CREDENTIAL_REQUIRED" || !reflect.DeepEqual(runner.steps, []string{"DESCRIBE"}) {
				t.Fatalf("missing target auth: %v %v", err, runner.steps)
			}
		} else if err != nil || plan.ExecutionMode != ApplicationLibrariesOnly || !reflect.DeepEqual(runner.steps, []string{"DESCRIBE", "PREPARE", "PLAN"}) {
			t.Fatalf("wrong preparation order: %v %v", err, runner.steps)
		}
	}
}

func TestSelectionIsBoundToImageDescriptionAndPlan(t *testing.T) {
	for _, supported := range []bool{false, true} {
		root := t.TempDir()
		if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
			t.Fatal(err)
		}
		runner := &imagePreparationRunner{b1PlanRunner: b1PlanRunner{summary: testInfrastructureSummary(t)}, selection: supported}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		selection := []string{"identity-east"}
		ctx := WithApplicationLibrarySelection(context.Background(), selection)
		selection[0] = "must-not-change-context"
		plan, err := transport.BuildDeploymentPlanForModeWithLibraryOrder(ctx, testNode(), root,
			map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{}, []string{"identity-east", "consumer"}, ApplicationLibrariesOnly, nil)
		if !supported {
			if err == nil || err.Error() != "APPLICATION_LIBRARY_SELECTION_RUNTIME_UNSUPPORTED" || len(runner.steps) != 0 {
				t.Fatalf("old runtime must reject before preparation: %v %v", err, runner.steps)
			}
			continue
		}
		if err != nil || !reflect.DeepEqual(plan.SkipApplicationLibraries, []string{"identity-east"}) {
			t.Fatalf("selection lost: %v %+v", err, plan)
		}
		for _, request := range runner.requests {
			if request["operation"] == "BuildDeploymentPlan" || request["phase"] == "DESCRIBE" {
				if !reflect.DeepEqual(request["skipApplicationLibraries"], []any{"identity-east"}) {
					t.Fatalf("selection missing in %v", request["operation"])
				}
			}
		}
	}
}

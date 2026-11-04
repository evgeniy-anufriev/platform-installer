package executionnode

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type availabilityRunner struct {
	serviceSelectionRunner
	wrongMarker       bool
	capabilityRuntime map[string]any
}

func (r *availabilityRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	data, err := r.serviceSelectionRunner.RunBounded(ctx, name, args, input, limit)
	if err != nil {
		return data, err
	}
	var request, response map[string]any
	_ = json.Unmarshal(input, &request)
	if request["operation"] == nil {
		return data, err
	}
	_ = json.Unmarshal(data, &response)
	switch request["operation"] {
	case "GetCapabilities":
		if r.capabilityRuntime != nil {
			response["runtime"] = map[string]any{"bundleDigest": r.capabilityRuntime["bundleDigest"]}
			response["coreVersion"] = r.capabilityRuntime["coreVersion"]
			response["catalogDigest"] = r.capabilityRuntime["catalogDigest"]
		}
		response["apiVersion"] = "platform.installer/execution-capabilities/v1alpha15"
		response["deploymentPlanRequestVersions"] = append(response["deploymentPlanRequestVersions"].([]any), availabilityPlanRequestVersion)
		response["applicationImagePlanning"] = map[string]any{"protocol": "RegistryAvailabilityPlanning/v1alpha1", "planContract": "platform.installer/plan/v1alpha12", "manifestContract": "platform.installer/execution-manifest/v1alpha9"}
	case "BuildDeploymentPlan":
		plan := response["deploymentPlan"].(map[string]any)
		plan["apiVersion"] = "platform.installer/plan/v1alpha12"
		plan["imageResolution"] = "AT_EXECUTION"
		if r.wrongMarker {
			plan["imageResolution"] = "AT_PLAN"
		}
	}
	return json.Marshal(response)
}

func TestPlanReusesCapabilitiesOnlyWithinMatchingRuntimeOperation(t *testing.T) {
	for _, changed := range []string{"", "bundleDigest", "coreVersion", "catalogDigest", "missing-identity"} {
		t.Run(changed, func(t *testing.T) {
			root := t.TempDir()
			if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
				t.Fatal(err)
			}
			release := map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64), "coreVersion": "test-core", "catalogDigest": "sha256:" + strings.Repeat("c", 64)}
			identity := map[string]any{}
			for key, value := range release {
				identity[key] = value
			}
			if changed == "missing-identity" {
				identity = nil
			} else if changed != "" {
				identity[changed] = "different"
			}
			runner := &availabilityRunner{capabilityRuntime: identity, serviceSelectionRunner: serviceSelectionRunner{imagePreparationRunner: imagePreparationRunner{selection: true, b1PlanRunner: b1PlanRunner{summary: testInfrastructureSummary(t)}}}}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			for i := 0; i < 2; i++ {
				before := len(runner.requests)
				if _, err := transport.BuildDeploymentPlanForModeWithLibraryOrder(context.Background(), testNode(), root, release, []string{"docker"}, []string{"sdku"}, ApplicationLibrariesOnly, nil); err != nil {
					t.Fatal(err)
				}
				calls := 0
				for _, request := range runner.requests[before:] {
					if request["operation"] == "GetCapabilities" {
						calls++
					}
				}
				want := 2
				if changed == "" {
					want = 1
				}
				if calls != want {
					t.Fatalf("capability calls=%d want=%d", calls, want)
				}
			}
		})
	}
}

func TestAvailabilityPlanningNegotiatesAndBindsEveryMode(t *testing.T) {
	for _, mode := range []ExecutionMode{FullProject, ApplicationLibrariesOnly, InfrastructureVerifyOnly} {
		t.Run(string(mode), func(t *testing.T) {
			root := t.TempDir()
			if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
				t.Fatal(err)
			}
			runner := &availabilityRunner{serviceSelectionRunner: serviceSelectionRunner{imagePreparationRunner: imagePreparationRunner{selection: true, b1PlanRunner: b1PlanRunner{summary: testInfrastructureSummary(t)}}}}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			plan, err := transport.BuildDeploymentPlanForModeWithLibraryOrder(context.Background(), testNode(), root,
				map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{"docker"}, []string{"sdku"}, mode, nil)
			if err != nil || plan.ExecutionMode != mode {
				t.Fatalf("mode negotiation: %+v %v", plan, err)
			}
			for _, request := range runner.requests {
				if request["phase"] == "DESCRIBE" || request["operation"] == "BuildDeploymentPlan" {
					if request["apiVersion"] != availabilityPlanRequestVersion || request["executionMode"] != string(mode) {
						t.Fatalf("wrong request: %+v", request)
					}
				}
			}
			runner.wrongMarker = true
			if _, err = transport.BuildDeploymentPlanForModeWithLibraryOrder(context.Background(), testNode(), root,
				map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{"docker"}, []string{"sdku"}, mode, nil); err == nil {
				t.Fatal("wrong image resolution admitted")
			}
		})
	}
}

func TestDeferredImagesCannotMasqueradeAsResolvedIdentities(t *testing.T) {
	image := map[string]any{"id": "sdku:gateway:node1:image", "name": "registry.example/gateway:qa", "artifactType": "container-image", "resolution": "AT_EXECUTION", "applicationLibrary": "sdku", "instanceId": "gateway", "hosts": []any{"node1"}, "sourcePolicy": "REPOSITORY_THEN_OFFLINE"}
	if _, err := decodeApplicationImage(image); err == nil {
		t.Fatal("legacy plan accepted unresolved image")
	}
	if _, err := decodeApplicationImage(image, true); err != nil {
		t.Fatal(err)
	}
	image["imageId"] = "sha256:" + strings.Repeat("a", 64)
	if _, err := decodeApplicationImage(image, true); err == nil {
		t.Fatal("fabricated identity admitted")
	}
}

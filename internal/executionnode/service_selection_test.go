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

type serviceSelectionRunner struct {
	imagePreparationRunner
	unsupported    bool
	wrongSelection bool
}

func (r *serviceSelectionRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	data, err := r.imagePreparationRunner.RunBounded(ctx, name, args, input, limit)
	if err != nil || r.unsupported {
		return data, err
	}
	var request, response map[string]any
	if json.Unmarshal(input, &request) != nil || request["operation"] == nil {
		return data, err
	}
	_ = json.Unmarshal(data, &response)
	switch request["operation"] {
	case "GetCapabilities":
		response["apiVersion"] = "platform.installer/execution-capabilities/v1alpha14"
		response["deploymentPlanRequestVersions"] = append(response["deploymentPlanRequestVersions"].([]any), serviceSelectionRequestVersion)
		response["applicationPostInstall"] = map[string]any{"protocol": "ApplicationPostInstall/v1alpha1", "packageManifestVersion": "platform.installer/application-package/v1alpha3", "planContract": "platform.installer/plan/v1alpha9", "manifestContract": "platform.installer/execution-manifest/v1alpha7"}
		response["applicationProgress"] = map[string]any{"protocol": "ApplicationProgress/v1alpha1", "planContract": "platform.installer/plan/v1alpha10"}
		response["serviceSelection"] = map[string]any{"protocol": "ServiceSelection/v1alpha1", "planContract": "platform.installer/plan/v1alpha11", "manifestContract": "platform.installer/execution-manifest/v1alpha8"}
	case "BuildDeploymentPlan":
		plan := response["deploymentPlan"].(map[string]any)
		plan["apiVersion"] = "platform.installer/plan/v1alpha11"
		plan["skipServiceDeployments"] = request["skipServiceDeployments"]
		if r.wrongSelection {
			plan["skipServiceDeployments"] = []string{"other-provider"}
		}
	}
	return json.Marshal(response)
}
func TestServiceSelectionBindsDescriptionPlanAndRejectsUnsupportedRuntime(t *testing.T) {
	for _, supported := range []bool{false, true} {
		root := t.TempDir()
		if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
			t.Fatal(err)
		}
		runner := &serviceSelectionRunner{imagePreparationRunner: imagePreparationRunner{selection: true, b1PlanRunner: b1PlanRunner{summary: testInfrastructureSummary(t)}}, unsupported: !supported}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		skipped := []string{"kafka-existing"}
		ctx := WithServiceSelection(context.Background(), skipped)
		skipped[0] = "mutated"
		plan, err := transport.BuildDeploymentPlanForModeWithLibraryOrder(ctx, testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{"kafka-existing", "docker"}, []string{"sdku"}, FullProject, nil)
		if !supported {
			if err == nil || err.Error() != "SERVICE_SELECTION_RUNTIME_UNSUPPORTED" || len(runner.steps) != 0 {
				t.Fatalf("unsupported runtime started work: %v %v", err, runner.steps)
			}
			continue
		}
		if err != nil || !reflect.DeepEqual(plan.SkipServiceDeployments, []string{"kafka-existing"}) {
			t.Fatalf("selection lost: %v %+v", err, plan)
		}
		for _, request := range runner.requests {
			if request["phase"] == "DESCRIBE" || request["operation"] == "BuildDeploymentPlan" {
				if !reflect.DeepEqual(request["skipServiceDeployments"], []any{"kafka-existing"}) {
					t.Fatal("request selection differs")
				}
			}
		}
		runner.wrongSelection = true
		if _, err = transport.BuildDeploymentPlanForModeWithLibraryOrder(ctx, testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("e", 64)}, []string{"kafka-existing", "docker"}, []string{"sdku"}, FullProject, nil); err == nil {
			t.Fatal("mismatched selection admitted")
		}
	}
}
func TestServiceSelectionCopiesRetainedPlanAndRecord(t *testing.T) {
	original := DeploymentPlan{SkipServiceDeployments: []string{"existing"}}
	clone := cloneDeploymentPlan(original)
	clone.SkipServiceDeployments[0] = "changed"
	if original.SkipServiceDeployments[0] != "existing" {
		t.Fatal("plan selection aliases input")
	}
	record := PlanRecord{SkipServiceDeployments: []string{"existing"}, Plan: original}
	copy := clonePlanRecord(record)
	copy.SkipServiceDeployments[0] = "changed"
	if record.SkipServiceDeployments[0] != "existing" {
		t.Fatal("record selection aliases input")
	}
}

type selectedServiceLifecycleBuilder struct {
	modeLifecycleBuilder
	seen [][]string
	drop bool
}

func (b *selectedServiceLifecycleBuilder) BuildDeploymentPlanForMode(ctx context.Context, n Node, root string, release map[string]any, order []string, mode ExecutionMode, sources map[string]string, skip ...bool) (DeploymentPlan, error) {
	p, err := b.modeLifecycleBuilder.BuildDeploymentPlanForMode(ctx, n, root, release, order, mode, sources, skip...)
	b.seen = append(b.seen, serviceSelection(ctx))
	if !b.drop {
		p.SkipServiceDeployments = serviceSelection(ctx)
	}
	return p, err
}
func TestServiceSelectionSurvivesApprovalAndFreshStart(t *testing.T) {
	for _, drop := range []bool{false, true} {
		b := &selectedServiceLifecycleBuilder{}
		c := &lifecycleClient{}
		s := NewExecutionService(b, c)
		record, err := s.CreatePlanForMode(WithServiceSelection(context.Background(), []string{"existing"}), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"}, nil, FullProject, nil)
		if err != nil {
			t.Fatal(err)
		}
		if err = s.ApprovePlan(record.ID, []string{"ACK_RISK"}); err != nil {
			t.Fatal(err)
		}
		b.drop = drop
		_, err = s.Start(context.Background(), Node{}, record.ID)
		if drop {
			if err == nil || c.starts != 0 {
				t.Fatal("changed selection dispatched")
			}
		} else if err != nil || c.starts != 1 || len(b.seen) != 2 || b.seen[1][0] != "existing" {
			t.Fatalf("selection not bound to fresh Start: %v", err)
		}
	}
}

package desktop

import (
	"context"
	"os"
	"path/filepath"
	"platform-installer/internal/executionnode"
	"testing"
)

type modeInstallationBuilder struct {
	installationPlanBuilder
	requests []InstallationPlanRequest
}

func (b *modeInstallationBuilder) BuildDeploymentPlanForMode(ctx context.Context, n executionnode.Node, root string, release map[string]any, order []string, mode executionnode.ExecutionMode, sources map[string]string) (executionnode.DeploymentPlan, error) {
	b.requests = append(b.requests, InstallationPlanRequest{ExecutionMode: mode, DeploymentOrder: order, ApplicationVaultSources: sources})
	p, err := b.installationPlanBuilder.BuildDeploymentPlan(ctx, n, root, release, order)
	p.ExecutionMode = mode
	p.InfrastructureVerification = &executionnode.InfrastructureVerification{Status: "PASS", Deployments: []executionnode.InfrastructureDeploymentVerification{}}
	return p, err
}
func TestB3InstallationModeProjectionCacheAndOrdinaryApproval(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	app.infrastructureVerificationRoot = t.TempDir()
	builder := &modeInstallationBuilder{}
	app.binding.plans = executionnode.NewExecutionService(builder, client)
	result := app.CreateInstallationPlanForMode(InstallationPlanRequest{ExecutionMode: executionnode.ApplicationLibrariesOnly, ApplicationVaultSources: map[string]string{"vault-main": "RUNTIME_INPUT"}})
	if result.Error != nil || result.Plan == nil || result.Plan.ExecutionMode != executionnode.ApplicationLibrariesOnly || result.Plan.InfrastructureVerification.Status != "PASS" {
		t.Fatalf("%+v", result)
	}
	if result.Plan.InfrastructureCacheWarning || result.Plan.InfrastructureObservedAt == "" {
		t.Fatal("observation not stored")
	}
	cached := app.GetInfrastructureVerification()
	if cached.Availability != "UNKNOWN" || cached.Previous == nil {
		t.Fatal("cache granted current admission or lost observation")
	}
	if got := app.ApproveInstallationPlan(result.Plan.ID, []string{"ACK_RISK"}); got.Error != nil || !got.Plan.Approved {
		t.Fatalf("approval: %+v", got)
	}
	got := app.GetInstallationPlan(result.Plan.ID)
	if got.Plan == nil || got.Plan.InfrastructureObservedAt != result.Plan.InfrastructureObservedAt {
		t.Fatal("projection changed on reload")
	}
	app.binding.node.User = "another-user"
	if got := app.GetInfrastructureVerification(); got.Previous == nil {
		t.Fatal("account change erased infra observation")
	}
}
func TestB3InstallationModeDoesNotFallbackOrReadCacheForAdmission(t *testing.T) {
	app, builder, _ := installationPlanApp(t, false)
	if got := app.CreateInstallationPlanForMode(InstallationPlanRequest{ExecutionMode: executionnode.ApplicationLibrariesOnly}); got.Error == nil || got.Error.Code != "EXECUTION_MODE_RUNTIME_UNSUPPORTED" {
		t.Fatalf("%+v", got)
	}
	if builder.calls != 0 {
		t.Fatal("legacy Build used")
	}
	if got := app.CreateInstallationPlanForMode(InstallationPlanRequest{}); got.Error == nil {
		t.Fatal("empty explicit mode accepted")
	}
}

func TestB3InstallationModeCacheFailureIsObservationWarning(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	blockedStore := filepath.Join(t.TempDir(), "file")
	if err := os.WriteFile(blockedStore, []byte("not a directory"), 0600); err != nil {
		t.Fatal(err)
	}
	app.infrastructureVerificationRoot = blockedStore
	app.localRunRecordRoot = t.TempDir()
	builder := &modeInstallationBuilder{}
	app.binding.plans = executionnode.NewExecutionService(builder, client)
	result := app.CreateInstallationPlanForMode(InstallationPlanRequest{ExecutionMode: executionnode.InfrastructureVerifyOnly})
	if result.Error != nil || result.Plan == nil || !result.Plan.InfrastructureCacheWarning {
		t.Fatalf("%+v", result)
	}
	if got := app.ApproveInstallationPlan(result.Plan.ID, []string{"ACK_RISK"}); got.Error != nil {
		t.Fatal(got.Error)
	}
	// This fixture deliberately has no staged Start binding. The common lifecycle
	// must restore the PENDING marker when it refuses before dispatch.
	got := app.StartApprovedInstallation(result.Plan.ID)
	if got.Error == nil || got.Error.Code != "EXECUTION_START_BINDING_MISSING" {
		t.Fatalf("%+v", got)
	}
	record, err := readLocalRunRecord(app.localRunRecordRoot, app.current.Root, app.current.Project.ID)
	if err != nil || record != nil || app.startOutcomeUnknown {
		t.Fatal("pre-dispatch marker not restored")
	}
	if len(builder.requests) != 2 || builder.requests[1].ExecutionMode != executionnode.InfrastructureVerifyOnly {
		t.Fatal("Start rebuilt a different mode")
	}
}

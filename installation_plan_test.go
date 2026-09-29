package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

type installationPlanTransport struct{}

func TestInstallationPlanActionEmptyListsMarshalAsArrays(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	created := app.CreateInstallationPlan()
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	action := created.Plan.Phases[0].Actions[0]
	if action.DependsOn == nil {
		t.Fatal("empty dependencies must be a non-nil presentation array")
	}
	data, err := json.Marshal(action)
	if err != nil || !strings.Contains(string(data), `"dependsOn":[]`) {
		t.Fatalf("dependency JSON shape invalid: %s %v", data, err)
	}
	// Both nil and explicit empty source collections have the same wire shape.
	record := executionnode.PlanRecord{ID: "empty-lists", Plan: executionnode.DeploymentPlan{
		RuntimeRelease:  app.binding.reader.runtimeRelease,
		PlanFingerprint: "fingerprint", ProjectRevision: "revision",
		Phases: []executionnode.DeploymentPlanPhase{{ID: "phase", Actions: []executionnode.DeploymentPlanAction{{ID: "action"}}}},
	}}
	view, err := installationPlanView(record, app.binding)
	if err != nil {
		t.Fatal(err)
	}
	data, err = json.Marshal(view.Phases[0].Actions[0])
	if err != nil || !strings.Contains(string(data), `"targets":[]`) || !strings.Contains(string(data), `"dependsOn":[]`) {
		t.Fatalf("empty list wire shape invalid: %s %v", data, err)
	}
}

type outputCapabilityGateTransport struct {
	secretOutputTransportStub
	cap    executionnode.SecretOutputCapabilities
	capErr error
}

func (s *outputCapabilityGateTransport) GetSecretOutputCapabilities(context.Context, executionnode.Node, string, string) (executionnode.SecretOutputCapabilities, error) {
	return s.cap, s.capErr
}

func TestOutputCapabilityGateBlocksBeforeStart(t *testing.T) {
	for _, mode := range []string{"unsupported", "unavailable", "malformed"} {
		t.Run(mode, func(t *testing.T) {
			app, _, client := installationPlanApp(t, false)
			created := app.CreateInstallationPlan()
			app.current.Managed = &installer.ManagedProjectView{Deployments: map[string]installer.ManagedDeployment{"vault-ha": {ServiceType: "vault"}}}
			app.current.Catalog = &projectlifecycle.ProjectCatalogView{Status: "READY", Services: []projectlifecycle.ProjectCatalogService{{ID: "vault", SecretOutputEntries: []string{"admin-token", "unseal-shares"}}}}
			if err := app.secrets.SetOutputEncryptionPassword(runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}, []byte("synthetic-session-password")); err != nil {
				t.Fatal(err)
			}
			approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
			if approved.Error != nil {
				t.Fatal(approved.Error)
			}
			if mode != "unsupported" {
				transport := &outputCapabilityGateTransport{}
				if mode == "unavailable" {
					transport.capErr = errors.New("test handshake failure")
				}
				app.binding.reader.transport = transport
			}
			result := app.StartApprovedInstallation(created.Plan.ID)
			if result.Status != "BLOCKED" || result.Error == nil || !strings.HasPrefix(result.Error.Code, "SECRET_OUTPUT_") || client.starts != 0 {
				t.Fatalf("result=%#v starts=%d", result, client.starts)
			}
		})
	}
}

func (installationPlanTransport) BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error) {
	return nil, errors.New("snapshot must not be called by installation plan")
}

type installationPlanBuilder struct {
	blocked bool
	calls   int
}

func (b *installationPlanBuilder) BuildDeploymentPlan(_ context.Context, _ executionnode.Node, root string, release map[string]any) (executionnode.DeploymentPlan, error) {
	b.calls++
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		return executionnode.DeploymentPlan{}, err
	}
	status := "EXECUTABLE"
	identity := "project-aaaaaaaaaaaaaaaa"
	findings := []executionnode.Finding(nil)
	if b.blocked {
		status, identity = "BLOCKED", ""
		findings = []executionnode.Finding{{Code: "PROJECT_VALIDATION_BLOCKED", SafeMessage: "Authoritative project validation is blocked"}}
	}
	return executionnode.DeploymentPlan{
		ID: "plan-1", Status: status, ProjectIdentity: identity, ProjectRevision: revision,
		PlanFingerprint: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", RuntimeRelease: release,
		Acknowledgements: []string{"ACK_RISK"}, AcknowledgementDetails: []executionnode.PlanAcknowledgement{{Code: "ACK_RISK", Summary: "Review the planned change"}},
		Phases: []executionnode.DeploymentPlanPhase{{ID: "apply", Order: 0, Actions: []executionnode.DeploymentPlanAction{{ID: "apply:kafka-main", Type: "SERVICE_APPLY", ServiceDeployment: "kafka-main", Targets: []string{"node1"}, DependsOn: []string{}, Mutating: true, Reboot: "NONE", Summary: "Apply Kafka"}}}}, Findings: findings,
	}, nil
}

type installationPlanClient struct{ starts int }

func (c *installationPlanClient) StartExecution(context.Context, executionnode.Node, executionnode.ExecutionStartRequest) (executionnode.ExecutionRun, error) {
	c.starts++
	return executionnode.ExecutionRun{}, errors.New("Start must not be called by UI-02B")
}
func (*installationPlanClient) GetExecution(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, errors.New("not used")
}
func (*installationPlanClient) GetEvents(context.Context, executionnode.Node, string, int, int) (executionnode.ExecutionEventPage, error) {
	return executionnode.ExecutionEventPage{}, errors.New("not used")
}
func (*installationPlanClient) CancelExecution(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, errors.New("not used")
}

func TestInstallationPlanCreatesProjectsAndApprovesOnlyTheCurrentBoundPlan(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	created := app.CreateInstallationPlan()
	if created.Status != "PLAN_REVIEW" || created.Plan == nil || created.Plan.ID != "plan-1" || len(created.Plan.Phases) != 1 || created.Plan.Phases[0].Actions[0].Targets[0] != "node1" {
		t.Fatalf("created=%#v error=%#v", created, created.Error)
	}
	if builder.calls != 1 || client.starts != 0 {
		t.Fatalf("builder=%d starts=%d", builder.calls, client.starts)
	}
	wrong := app.ApproveInstallationPlan(created.Plan.ID, nil)
	if wrong.Error == nil || wrong.Error.Code != executionnode.AcknowledgementRequired {
		t.Fatalf("wrong=%#v", wrong)
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Status != "PLAN_APPROVED" || approved.Plan == nil || !approved.Plan.Approved || client.starts != 0 {
		t.Fatalf("approved=%#v starts=%d", approved, client.starts)
	}
	state := app.GetInstallationState()
	if state.Status != "PLAN_APPROVED" || state.Plan.PlanID != created.Plan.ID {
		t.Fatalf("state=%#v", state)
	}
}

func TestInstallationPlanKeepsBlockedPlanReadableButNeverApprovable(t *testing.T) {
	app, _, client := installationPlanApp(t, true)
	created := app.CreateInstallationPlan()
	if created.Status != "PLAN_BLOCKED" || created.Plan == nil || len(created.Plan.Findings) != 1 {
		t.Fatalf("created=%#v error=%#v", created, created.Error)
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, nil)
	if approved.Error == nil || approved.Error.Code != executionnode.PlanBlocked || client.starts != 0 {
		t.Fatalf("approved=%#v starts=%d", approved, client.starts)
	}
}

func TestInstallationPlanRejectsUnknownPlanIDWithoutNodeCall(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	result := app.GetInstallationPlan("not-current")
	if result.Error == nil || result.Error.Code != "INSTALLATION_PLAN_NOT_FOUND" || builder.calls != 0 || client.starts != 0 {
		t.Fatalf("result=%#v builder=%d starts=%d", result, builder.calls, client.starts)
	}
}

func TestInstallationPlanRejectsApprovalAfterCanonicalRevisionChanges(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	created := app.CreateInstallationPlan()
	if created.Plan == nil {
		t.Fatalf("created=%#v", created)
	}
	if err := os.WriteFile(filepath.Join(app.current.Root, "project.yml"), []byte("apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Changed\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Error == nil || approved.Error.Code != executionnode.PlanStale || client.starts != 0 {
		t.Fatalf("approved=%#v starts=%d", approved, client.starts)
	}
}

func TestInstallationPlanRuntimeSecretRequirementsUseOnlyClosedCorePlanEntries(t *testing.T) {
	plan := executionnode.DeploymentPlan{RequiredCredentials: []executionnode.RequiredCredential{
		{RequirementRef: "redis-sentinel-password", Purpose: "SERVICE_PASSWORD"},
		{RequirementRef: "pki-store-password", Purpose: "PKI_STORE_PASSWORD"},
		{RequirementRef: "redis-password", Purpose: "SERVICE_PASSWORD"},
	}}
	got, err := installationPlanRuntimeSecretRequirements(plan)
	if err != nil || strings.Join(got, ",") != "redis-password,redis-sentinel-password" {
		t.Fatalf("requirements=%v err=%v", got, err)
	}
	plan.RequiredCredentials = append(plan.RequiredCredentials, executionnode.RequiredCredential{RequirementRef: "invalid_ref", Purpose: "SERVICE_PASSWORD"})
	if _, err := installationPlanRuntimeSecretRequirements(plan); err == nil || err.Error() != "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE" {
		t.Fatalf("invalid plan secret reference error=%v", err)
	}
}

func installationPlanApp(t *testing.T, blocked bool) (*App, *installationPlanBuilder, *installationPlanClient) {
	t.Helper()
	root := t.TempDir()
	writeInstallationProject(t, root)
	node := executionnode.Node{ID: "node-1", Address: "192.0.2.10"}
	release := map[string]any{
		"bundleDigest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
		"coreVersion":  "test-core", "catalogDigest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc", "planningProtocol": "platform.installer/execution-runtime/v1alpha1",
	}
	builder, client := &installationPlanBuilder{blocked: blocked}, &installationPlanClient{}
	plans := executionnode.NewExecutionService(builder, client)
	binding := executionNodeBinding{node: node, reader: projectReader{transport: installationPlanTransport{}, node: node, runtimeRelease: release}, service: &executionLifecycleStub{}, plans: plans, bundleRoot: "bundle"}
	app := NewApp(snapshotReaderStub{}, lifecycleStub{}, WithTrustedExecutionNodeBinding(binding))
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
	app.execution.external = &executionNodeCandidate{hostID: node.ID, label: "node-1 · 192.0.2.10"}
	app.execution.context = ExecutionNodeContext{Status: "READY", SelectionKind: "EXPLICIT_EXTERNAL", SelectionSource: "EXPLICIT", SafeLabel: "node-1 · 192.0.2.10", Locked: true}
	return app, builder, client
}

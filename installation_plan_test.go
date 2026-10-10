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

type countingSecretDescriptorTransport struct {
	installationPlanTransport
	calls       int
	descriptors []executionnode.RuntimeSecretDescriptor
}

func (transport *countingSecretDescriptorTransport) BuildRuntimeSecretDescriptors(_ context.Context, _ executionnode.Node, _ string, _ map[string]any, request executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error) {
	transport.calls++
	descriptors := transport.descriptors
	if descriptors == nil {
		descriptors = []executionnode.RuntimeSecretDescriptor{
			{RequirementRef: "service-password", Purpose: "SERVICE_PASSWORD", ServiceDeployment: "service-main", DisplayLabel: "Пароль сервиса", RequiredWhen: "ALWAYS", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}, Hosts: []string{"node-1"}},
			{RequirementRef: "si-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "service-main", DisplayLabel: "Токен", RequiredWhen: "INITIALIZED", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}, Hosts: []string{"node-1"}},
		}
	}
	return executionnode.RuntimeSecretDescriptorResult{
		ProjectIdentity: request.ProjectIdentity, ProjectRevision: request.ProjectRevision,
		DescriptorSetFingerprint: "synthetic-fingerprint",
		Runtime:                  executionnode.RuntimeEvidence{BundleDigest: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", CoreVersion: "test-core", CatalogDigest: "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc", Protocol: "platform.installer/execution-runtime/v1alpha1"},
		Descriptors:              descriptors,
	}, nil
}

func TestInstallationPlanActionEmptyListsMarshalAsArrays(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	created := app.CreateInstallationPlan([]string{})
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
			created := app.CreateInstallationPlan([]string{})
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
	blocked             bool
	calls               int
	onBuild             func()
	requiredCredentials []executionnode.RequiredCredential
}

func (b *installationPlanBuilder) BuildDeploymentPlan(_ context.Context, _ executionnode.Node, root string, release map[string]any, _ []string) (executionnode.DeploymentPlan, error) {
	b.calls++
	if b.onBuild != nil {
		b.onBuild()
	}
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
		Phases: []executionnode.DeploymentPlanPhase{{ID: "apply", Order: 0, Actions: []executionnode.DeploymentPlanAction{{ID: "apply:kafka-main", Type: "SERVICE_APPLY", ServiceDeployment: "kafka-main", Targets: []string{"node1"}, DependsOn: []string{}, Mutating: true, Reboot: "NONE", Summary: "Apply Kafka"}}}}, Findings: findings, RequiredCredentials: b.requiredCredentials,
	}, nil
}

func TestRequiredPKISecretBlocksApprovalAndIsRecheckedBeforeStart(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	builder.requiredCredentials = []executionnode.RequiredCredential{{RequirementRef: "pki-store-password", Purpose: "PKI_STORE_PASSWORD"}}
	binding := runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh-password"}); err != nil {
		t.Fatal(err)
	}
	created := app.CreateInstallationPlan(nil)
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	missing := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if missing.Error == nil || missing.Error.Code != "INSTALLATION_SECRETS_MISSING" || missing.Plan == nil || missing.Plan.Approved {
		t.Fatalf("missing secret approval=%+v", missing)
	}
	if _, err := app.secrets.SetPKIStorePassword(binding, "synthetic-test-password"); err != nil {
		t.Fatal(err)
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Error != nil || approved.Plan == nil || !approved.Plan.Approved {
		t.Fatalf("approval after secret=%+v", approved)
	}
	app.secrets.Clear()
	start := app.StartApprovedInstallation(created.Plan.ID)
	if start.Error == nil || start.Error.Code != "INSTALLATION_SECRETS_MISSING" || client.starts != 0 {
		t.Fatalf("start after secret loss=%+v starts=%d", start, client.starts)
	}
}

func TestRequiredServicePasswordBlocksApprovalUntilPresent(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	builder.requiredCredentials = []executionnode.RequiredCredential{{RequirementRef: "postgresql-admin-password", Purpose: "SERVICE_PASSWORD"}}
	binding := runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh-password"}); err != nil {
		t.Fatal(err)
	}
	created := app.CreateInstallationPlan(nil)
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	missing := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if missing.Error == nil || missing.Error.Code != "INSTALLATION_SECRETS_MISSING" || !strings.Contains(missing.Error.Message, "postgresql-admin-password") || missing.Plan == nil || missing.Plan.Approved {
		t.Fatalf("missing service password approval=%+v", missing)
	}
	if err := app.secrets.SetRuntimeSecretValuesForRequirements(binding, []string{"postgresql-admin-password"}, map[string]string{"postgresql-admin-password": "synthetic-service-password"}); err != nil {
		t.Fatal(err)
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Error != nil || approved.Plan == nil || !approved.Plan.Approved {
		t.Fatalf("approval after service password=%+v", approved)
	}
	app.secrets.ClearRuntimeSecretValues(binding)
	start := app.StartApprovedInstallation(created.Plan.ID)
	if start.Error == nil || start.Error.Code != "INSTALLATION_SECRETS_MISSING" || client.starts != 0 {
		t.Fatalf("start after service password loss=%+v starts=%d", start, client.starts)
	}
}

func TestStartPromotesPendingPasswordsForPasswordOnlyPlan(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	transport := &countingSecretDescriptorTransport{}
	app.binding.reader.transport = transport
	services := map[string][]string{
		"qa-postgresql": {"postgresql-admin-password", "postgresql-monitor-password", "postgresql-replication-password"},
		"qa-redis":      {"redis-password", "redis-sentinel-password"},
	}
	passwords := make([]string, 0, 5)
	for deployment, references := range services {
		for _, reference := range references {
			passwords = append(passwords, reference)
			builder.requiredCredentials = append(builder.requiredCredentials, executionnode.RequiredCredential{RequirementRef: reference, Purpose: "SERVICE_PASSWORD"})
			transport.descriptors = append(transport.descriptors, executionnode.RuntimeSecretDescriptor{RequirementRef: reference, Purpose: "SERVICE_PASSWORD", ServiceDeployment: deployment, DisplayLabel: reference, RequiredWhen: "ALWAYS", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}, Hosts: []string{"node-1"}})
		}
	}
	binding := runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh-password"}); err != nil {
		t.Fatal(err)
	}
	for _, references := range services {
		values := make(map[string]string, len(references))
		for _, reference := range references {
			values[reference] = "synthetic-service-password"
		}
		if err := app.secrets.SetPendingRuntimeSecretValuesForRequirements(binding, references, values); err != nil {
			t.Fatal(err)
		}
	}
	if missing := app.secrets.MissingRequiredSecrets(binding, passwords, false, true); len(missing) != 0 {
		t.Fatalf("pending passwords not visible at approval: %v", missing)
	}
	created := app.CreateInstallationPlan(nil)
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Error != nil || approved.Plan == nil || !approved.Plan.Approved {
		t.Fatalf("approval=%+v", approved)
	}
	start := app.StartApprovedInstallation(created.Plan.ID)
	if transport.calls != 1 || start.Error != nil && (start.Error.Code == "INSTALLATION_SECRETS_MISSING" || strings.HasPrefix(start.Error.Code, "RUNTIME_SECRET_DESCRIPTORS_")) {
		t.Fatalf("pending passwords were not Core-attested before Start: calls=%d status=%s error=%+v starts=%d", transport.calls, start.Status, start.Error, client.starts)
	}
	if missing := app.secrets.MissingRequiredSecrets(binding, passwords, false, false); len(missing) != 0 {
		t.Fatalf("passwords not attached after Core attestation: %v", missing)
	}
}

func TestTypedDescriptorFailureKeepsItsActualStartError(t *testing.T) {
	app, builder, client := installationPlanApp(t, false)
	builder.requiredCredentials = []executionnode.RequiredCredential{{RequirementRef: "si-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", Purpose: "SERVICE_ADMIN_TOKEN"}}
	created := app.CreateInstallationPlan(nil)
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"})
	if approved.Error != nil || approved.Plan == nil || !approved.Plan.Approved {
		t.Fatalf("approval=%+v", approved)
	}
	start := app.StartApprovedInstallation(created.Plan.ID)
	if start.Error == nil || start.Error.Code != "RUNTIME_SECRET_DESCRIPTORS_UNSUPPORTED" || client.starts != 0 {
		t.Fatalf("descriptor failure was masked: start=%+v starts=%d", start, client.starts)
	}
}

func TestStartReadsMixedServiceDescriptorsOnce(t *testing.T) {
	app, builder, _ := installationPlanApp(t, false)
	transport := &countingSecretDescriptorTransport{}
	app.binding.reader.transport = transport
	builder.requiredCredentials = []executionnode.RequiredCredential{
		{RequirementRef: "service-password", Purpose: "SERVICE_PASSWORD"},
		{RequirementRef: "si-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", Purpose: "SERVICE_ADMIN_TOKEN"},
	}
	binding := runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh-password"}); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.SetRuntimeSecretValuesForRequirements(binding, []string{"service-password"}, map[string]string{"service-password": "synthetic-service-password"}); err != nil {
		t.Fatal(err)
	}
	created := app.CreateInstallationPlan(nil)
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	if approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"}); approved.Error != nil {
		t.Fatalf("approval=%+v", approved)
	}
	start := app.StartApprovedInstallation(created.Plan.ID)
	if transport.calls != 1 || start.Error == nil || start.Error.Code == "RUNTIME_SECRET_DESCRIPTORS_STALE" || start.Error.Code == "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE" {
		t.Fatalf("mixed descriptor check: calls=%d start=%+v", transport.calls, start)
	}
}

type installationPlanClient struct{ starts int }

func TestPreDispatchStartFailureDoesNotLeaveActiveRunReservation(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	app.localRunRecordRoot = t.TempDir()
	created := app.CreateInstallationPlan([]string{})
	if created.Plan == nil {
		t.Fatal("plan unavailable")
	}
	if approved := app.ApproveInstallationPlan(created.Plan.ID, []string{"ACK_RISK"}); approved.Error != nil {
		t.Fatal(approved.Error)
	}

	first := app.StartApprovedInstallation(created.Plan.ID)
	if first.Error == nil || first.Error.Code != "EXECUTION_START_BINDING_MISSING" || client.starts != 0 {
		t.Fatalf("first start=%#v error=%+v starts=%d", first, first.Error, client.starts)
	}
	record, err := readLocalRunRecord(app.localRunRecordRoot, app.current.Root, app.current.Project.ID)
	if err != nil || record != nil || app.startOutcomeUnknown {
		t.Fatalf("pre-dispatch reservation remains: record=%+v unknown=%t err=%v", record, app.startOutcomeUnknown, err)
	}

	second := app.StartApprovedInstallation(created.Plan.ID)
	if second.Error == nil || second.Error.Code == "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("retry was blocked by stale reservation: %#v", second)
	}
	if client.starts != 0 {
		t.Fatalf("test client unexpectedly started a remote run: %d", client.starts)
	}
}

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
	created := app.CreateInstallationPlan([]string{})
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
	created := app.CreateInstallationPlan([]string{})
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

func TestV02PlanDoesNotPublishAfterInFlightBindingInvalidation(t *testing.T) {
	app, builder, _ := installationPlanApp(t, false)
	builder.onBuild = func() { app.binding.dynamic = true }
	result := app.CreateInstallationPlan([]string{})
	if result.Plan != nil || result.Error == nil || app.installationPlanID != "" || app.execution.context.Status == "READY" || app.binding != nil {
		t.Fatalf("in-flight invalidation published plan: %#v", result)
	}
}

func TestInstallationPlanRejectsApprovalAfterCanonicalRevisionChanges(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	created := app.CreateInstallationPlan([]string{})
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
	node := executionnode.Node{ID: "node-1", Address: "192.0.2.10", Port: 22, User: "operator", HostKey: executionnode.HostKeyPolicy{Fingerprint: "SHA256:approved"}}
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

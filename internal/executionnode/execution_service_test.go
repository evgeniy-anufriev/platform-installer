package executionnode

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/artifactsource"
)

type lifecycleBuilder struct {
	calls         int
	stale         bool
	targets       []string
	requiresPKI   bool
	typedInputs   bool
	runtimeValues bool
}

func (b *lifecycleBuilder) BuildDeploymentPlan(_ context.Context, _ Node, _ string, release map[string]any) (DeploymentPlan, error) {
	b.calls++
	fp := "sha256:plan"
	if b.stale && b.calls > 1 {
		fp = "sha256:changed"
	}
	plan := DeploymentPlan{ID: "plan-1", Status: "EXECUTABLE", ProjectIdentity: "project-1", ProjectRevision: "sha256:revision", PlanFingerprint: fp, Acknowledgements: []string{"ACK_RISK"}, RuntimeRelease: release, stagingID: "staging-1", executionManifestDigest: "sha256:" + strings.Repeat("a", 64)}
	if b.requiresPKI {
		plan.RequiredCredentials = []RequiredCredential{{RequirementRef: "pki-store-password", Purpose: "PKI_STORE_PASSWORD", Hosts: []string{"node1"}}}
	}
	if b.typedInputs {
		plan.RequiredCredentials = append(plan.RequiredCredentials, RequiredCredential{RequirementRef: "si-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", Purpose: "SERVICE_ADMIN_TOKEN", Hosts: []string{"node1"}})
	}
	if b.runtimeValues {
		plan.RequiredCredentials = append(plan.RequiredCredentials, RequiredCredential{RequirementRef: "clickhouse-default-password", Purpose: "SERVICE_PASSWORD", Hosts: []string{"node1"}})
	}
	if b.targets != nil {
		plan.Phases = []DeploymentPlanPhase{{ID: "apply", Actions: []DeploymentPlanAction{{ID: "apply:service", Targets: append([]string(nil), b.targets...)}}}}
	}
	return plan, nil
}

type lifecycleClient struct {
	starts, cancels int
	events          []ExecutionEvent
	requests        []ExecutionStartV2Request
	startErr        error
	ops             []string
	typedCapability bool
}

type priorRunClient struct {
	*lifecycleClient
	priorState   string
	observeErr   error
	wrongProject bool
}

func (c *priorRunClient) StartExecutionV2(_ context.Context, _ Node, _ ExecutionStartV2Request) (ExecutionStartV2Response, error) {
	c.starts++
	return ExecutionStartV2Response{Status: "STARTED", RunID: fmt.Sprintf("installer-%d", c.starts)}, nil
}

func (c *priorRunClient) GetExecution(_ context.Context, _ Node, runID string) (ExecutionRun, error) {
	if c.observeErr != nil {
		return ExecutionRun{}, c.observeErr
	}
	project := "project-1"
	if c.wrongProject {
		project = "another-project"
	}
	return ExecutionRun{RunID: runID, ProjectIdentity: project, State: c.priorState}, nil
}

func (c *lifecycleClient) CredentialStartCapability(context.Context, Node) (CredentialStartCapability, error) {
	if c.typedCapability {
		return CredentialStartCapability{MaxPayloadBytes: 1114112, PayloadVersions: []string{credentialPayloadVersionV4}, TypedRuntimeInputs: true}, nil
	}
	return CredentialStartCapability{MaxPayloadBytes: 1114112, PayloadVersions: []string{credentialPayloadVersion, credentialPayloadVersionV2}}, nil
}
func (c *lifecycleClient) StartExecutionV2(_ context.Context, _ Node, request ExecutionStartV2Request) (ExecutionStartV2Response, error) {
	c.starts++
	c.ops = append(c.ops, "start-v2")
	c.requests = append(c.requests, request)
	if c.startErr != nil {
		return ExecutionStartV2Response{}, c.startErr
	}
	return ExecutionStartV2Response{Status: "STARTED", StartAttemptID: "attempt", RunID: "installer-1"}, nil
}
func (c *lifecycleClient) PutRuntimeSecretLease(context.Context, Node, CredentialLeaseRequest, TargetCredentialLeasePayload, int) (CredentialLeaseResponse, error) {
	c.ops = append(c.ops, "put-lease")
	return CredentialLeaseResponse{LeaseID: strings.Repeat("a", 32)}, nil
}

type syncPageClient struct {
	pages  map[int]ExecutionEventPage
	afters []int
}

func (c *syncPageClient) StartExecution(context.Context, Node, ExecutionStartRequest) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}
func (c *syncPageClient) GetExecution(_ context.Context, _ Node, runID string) (ExecutionRun, error) {
	return ExecutionRun{RunID: runID, State: "RUNNING", Sequence: maxObservedExecutionEvents + 1}, nil
}
func (c *syncPageClient) GetEvents(_ context.Context, _ Node, _ string, after, _ int) (ExecutionEventPage, error) {
	c.afters = append(c.afters, after)
	return c.pages[after], nil
}
func (c *syncPageClient) CancelExecution(context.Context, Node, string) (ExecutionRun, error) {
	return ExecutionRun{}, nil
}

func (c *lifecycleClient) StartExecution(_ context.Context, _ Node, r ExecutionStartRequest) (ExecutionRun, error) {
	c.starts++
	return ExecutionRun{RunID: "run-1", State: "RUNNING", Sequence: 0}, nil
}
func (c *lifecycleClient) GetExecution(context.Context, Node, string) (ExecutionRun, error) {
	return ExecutionRun{RunID: "run-1", State: "SUCCEEDED", Sequence: 2}, nil
}
func (c *lifecycleClient) GetEvents(_ context.Context, _ Node, _ string, after, _ int) (ExecutionEventPage, error) {
	events := make([]ExecutionEvent, 0, len(c.events))
	for _, event := range c.events {
		if event.Sequence > after {
			events = append(events, event)
		}
	}
	next := after
	if len(events) > 0 {
		next = events[len(events)-1].Sequence
	}
	return ExecutionEventPage{Events: events, NextSequence: next}, nil
}
func (c *lifecycleClient) CancelExecution(context.Context, Node, string) (ExecutionRun, error) {
	c.cancels++
	return ExecutionRun{RunID: "run-1", State: "CANCELLED", Sequence: 3}, nil
}

func TestCloneDeploymentPlanPreservesRuntimeRelease(t *testing.T) {
	plan := cloneDeploymentPlan(DeploymentPlan{RuntimeRelease: map[string]any{"bundleDigest": "sha256:x"}})
	if plan.RuntimeRelease["bundleDigest"] != "sha256:x" {
		t.Fatalf("runtime release=%v", plan.RuntimeRelease)
	}
}

func TestCloneServicePlanRequestPreservesPKISecretFiles(t *testing.T) {
	request := cloneServicePlanRequest(ServicePlanRequest{PKISecretFiles: map[string]string{"runtime:pki-store-password": "/var/lib/platform-installer/secrets/pki-password"}})
	if request.PKISecretFiles["runtime:pki-store-password"] != "/var/lib/platform-installer/secrets/pki-password" {
		t.Fatalf("pki secret files=%v", request.PKISecretFiles)
	}
}

func TestExecutionServiceApprovalFreshPlanAndOneShotStart(t *testing.T) {
	b := &lifecycleBuilder{}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	p, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(p.ID, nil); err == nil || err.(*ExecutionError).Code != AcknowledgementRequired {
		t.Fatalf("missing acknowledgement: %v", err)
	}
	if err := s.ApprovePlan(p.ID, []string{"ACK_RISK"}); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Start(context.Background(), Node{}, p.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Start(context.Background(), Node{}, p.ID); err == nil || err.(*ExecutionError).Code != ApprovalRequired {
		t.Fatalf("approval reused: %v", err)
	}
	if c.starts != 1 || b.calls != 2 {
		t.Fatalf("calls builder=%d starts=%d", b.calls, c.starts)
	}
	if len(c.requests) != 1 || c.requests[0].StartAttemptID == "" || c.requests[0].LeaseID != "" {
		t.Fatalf("UI-02 Start did not use the closed v2 request: %#v", c.requests)
	}
}

func TestExecutionServiceRequiresTypedV4AndAllowsConditionalInputsAbsent(t *testing.T) {
	b := &lifecycleBuilder{typedInputs: true}
	c := &lifecycleClient{typedCapability: true}
	s := NewExecutionService(b, c)
	plan, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(plan.ID, plan.Plan.Acknowledgements); err != nil {
		t.Fatal(err)
	}
	s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if len(request.RuntimeSecretInputs) != 1 || request.RuntimeSecretInputs[0].Purpose != "SERVICE_ADMIN_TOKEN" {
			t.Fatal("typed plan requirements not bound")
		}
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "ssh", UseTypedRuntimeInputs: true})
	})
	if _, err := s.Start(context.Background(), Node{}, plan.ID); err != nil {
		t.Fatal("conditional secret absence blocked initial run")
	}
	c = &lifecycleClient{}
	s = NewExecutionService(b, c)
	plan, err = s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(plan.ID, plan.Plan.Acknowledgements); err != nil {
		t.Fatal(err)
	}
	s.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "ssh", UseTypedRuntimeInputs: true})
	})
	if _, err := s.Start(context.Background(), Node{}, plan.ID); err == nil || err.Error() != "RUNTIME_SECRET_INPUTS_UNAVAILABLE" {
		t.Fatal("missing v4 capability did not block typed plan")
	}
}

func TestExecutionServiceV4OnlyRuntimeCarriesPasswordAndTypedInputs(t *testing.T) {
	b := &lifecycleBuilder{requiresPKI: true, typedInputs: true, runtimeValues: true}
	c := &lifecycleClient{typedCapability: true}
	s := NewExecutionService(b, c)
	s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if !request.RequiresPKIStorePassword || len(request.RuntimeSecretRequirements) != 1 || request.RuntimeSecretRequirements[0] != "clickhouse-default-password" || len(request.RuntimeSecretInputs) != 1 {
			t.Fatal("mixed plan requirements were not bound")
		}
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "ssh", PKIStorePassword: "pki", RuntimeSecretValues: map[string]string{"clickhouse-default-password": "test-password"}, UseTypedRuntimeInputs: true})
	})
	plan, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(plan.ID, plan.Plan.Acknowledgements); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Start(context.Background(), Node{}, plan.ID); err != nil {
		t.Fatal(err)
	}
	if got := strings.Join(c.ops, ","); got != "put-lease,start-v2" {
		t.Fatalf("mixed v4 Start operations=%s", got)
	}
}

func TestExecutionServiceDistinguishesMissingServicePasswordsFromPKI(t *testing.T) {
	b := &lifecycleBuilder{requiresPKI: true, runtimeValues: true}
	c := &lifecycleClient{typedCapability: true}
	s := NewExecutionService(b, c)
	s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if !request.RequiresPKIStorePassword || len(request.RuntimeSecretRequirements) != 1 {
			t.Fatal("expected PKI and service-password requirements")
		}
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "ssh", PKIStorePassword: "pki"})
	})
	plan, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(plan.ID, plan.Plan.Acknowledgements); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Start(context.Background(), Node{}, plan.ID); err == nil || err.Error() != "RUNTIME_SECRET_VALUES_UNAVAILABLE" {
		t.Fatalf("missing service password: %v", err)
	}
	if len(c.ops) != 0 {
		t.Fatalf("missing service password reached node: %v", c.ops)
	}
}

func TestExecutionServiceRetriesUnknownStartWithSameAttempt(t *testing.T) {
	b := &lifecycleBuilder{}
	c := &lifecycleClient{startErr: errors.New("transport unknown")}
	s := NewExecutionService(b, c)
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	if _, err := s.Start(context.Background(), Node{}, p.ID); err == nil {
		t.Fatal("unknown Start unexpectedly succeeded")
	} else {
		var notDispatched *StartNotDispatchedError
		if errors.As(err, &notDispatched) {
			t.Fatalf("transport error after dispatch was marked safe to retry: %v", err)
		}
	}
	c.startErr = nil
	if _, err := s.Start(context.Background(), Node{}, p.ID); err != nil {
		t.Fatal(err)
	}
	if len(c.requests) != 2 || c.requests[0].StartAttemptID == "" || c.requests[0].StartAttemptID != c.requests[1].StartAttemptID {
		t.Fatalf("retry generated a new start attempt: %#v", c.requests)
	}
}

func TestExecutionServiceMarksTargetTrustRejectionAsNotDispatched(t *testing.T) {
	b := &lifecycleBuilder{targets: []string{"node1"}}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	p, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(p.ID, p.Plan.Acknowledgements); err != nil {
		t.Fatal(err)
	}
	_, err = s.Start(context.Background(), Node{}, p.ID)
	var notDispatched *StartNotDispatchedError
	if !errors.As(err, &notDispatched) || err.Error() != "TARGET_HOST_TRUST_REQUIRED" || c.starts != 0 {
		t.Fatalf("pre-dispatch rejection=%v starts=%d", err, c.starts)
	}
}

func TestExecutionServiceStagesCredentialLeaseBeforeV2Start(t *testing.T) {
	b := &lifecycleBuilder{}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	s.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "secret"})
	})
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	if _, err := s.Start(context.Background(), Node{}, p.ID); err != nil {
		t.Fatal(err)
	}
	if got, want := strings.Join(c.ops, ","), "put-lease,start-v2"; got != want {
		t.Fatalf("credentialed Start order=%s want=%s", got, want)
	}
	if len(c.requests) != 1 || c.requests[0].LeaseID == "" {
		t.Fatalf("lease did not remain private to v2 request: %#v", c.requests)
	}
}

func TestExecutionServiceRequiresBoundPKIStorePasswordBeforeLeasePut(t *testing.T) {
	b := &lifecycleBuilder{requiresPKI: true}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if !request.RequiresPKIStorePassword {
			t.Fatal("PKI requirement was not passed to private provider")
		}
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "secret", PKIStorePassword: "pki"})
	})
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	if _, err := s.Start(context.Background(), Node{}, p.ID); err != nil {
		t.Fatal(err)
	}
	if got, want := strings.Join(c.ops, ","), "put-lease,start-v2"; got != want {
		t.Fatalf("credentialed Start order=%s want=%s", got, want)
	}
}

func TestExecutionServicePKIPasswordWithV4OnlyRuntime(t *testing.T) {
	for _, missing := range []bool{false, true} {
		t.Run(fmt.Sprintf("missing=%t", missing), func(t *testing.T) {
			b := &lifecycleBuilder{requiresPKI: true, typedInputs: true}
			c := &lifecycleClient{typedCapability: true}
			s := NewExecutionService(b, c)
			s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
				if !request.RequiresPKIStorePassword || len(request.RuntimeSecretInputs) != 1 {
					t.Fatal("missing bound requirements")
				}
				password := "pki"
				if missing {
					password = ""
				}
				return use(TargetCredentialLeasePayload{Username: "operator", Password: "ssh", PKIStorePassword: password, UseTypedRuntimeInputs: true})
			})
			p, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
			if err != nil {
				t.Fatal(err)
			}
			if err := s.ApprovePlan(p.ID, p.Plan.Acknowledgements); err != nil {
				t.Fatal(err)
			}
			_, err = s.Start(context.Background(), Node{}, p.ID)
			if missing {
				if err == nil || err.Error() != "PKI_STORE_PASSWORD_UNAVAILABLE" || len(c.ops) != 0 {
					t.Fatalf("missing PKI admitted: error=%v ops=%v", err, c.ops)
				}
			} else if err != nil || strings.Join(c.ops, ",") != "put-lease,start-v2" {
				t.Fatalf("v4 PKI start: error=%v ops=%v", err, c.ops)
			}
		})
	}
}

func TestExecutionServiceRejectsMissingPKIStorePasswordBeforeLeasePut(t *testing.T) {
	b := &lifecycleBuilder{requiresPKI: true}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	s.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "secret"})
	})
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	if _, err := s.Start(context.Background(), Node{}, p.ID); err == nil || err.Error() != "PKI_STORE_PASSWORD_UNAVAILABLE" {
		t.Fatalf("start error=%v", err)
	}
	if len(c.ops) != 0 {
		t.Fatalf("missing PKI password reached node: %v", c.ops)
	}
}

func TestExecutionServiceRejectsStalePlanBeforeStart(t *testing.T) {
	b := &lifecycleBuilder{stale: true}
	c := &lifecycleClient{}
	s := NewExecutionService(b, c)
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	_, err := s.Start(context.Background(), Node{}, p.ID)
	if err == nil || err.(*ExecutionError).Code != PlanStale {
		t.Fatalf("stale=%v", err)
	}
	if c.starts != 0 {
		t.Fatal("stale plan was started")
	}
}

func TestExecutionServiceSyncReplayOverflowAndCancel(t *testing.T) {
	c := &lifecycleClient{events: []ExecutionEvent{{RunID: "run-1", Sequence: 1, Status: "RUNNING"}, {RunID: "run-1", Sequence: 2, Status: "SUCCEEDED"}}}
	s := NewExecutionService(&lifecycleBuilder{}, c)
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	_ = s.ApprovePlan(p.ID, []string{"ACK_RISK"})
	run, _ := s.Start(context.Background(), Node{}, p.ID)
	sub, _ := s.Subscribe(run.RunID, 1)
	_, events, err := s.Reconnect(context.Background(), Node{}, run.RunID)
	if err != nil || len(events) != 2 {
		t.Fatalf("replay err=%v events=%d", err, len(events))
	}
	if _, ok := <-sub.C; !ok {
	} else {
		if _, ok := <-sub.C; ok {
			t.Fatal("overflow subscriber remained open")
		}
	}
	if _, err := s.Cancel(context.Background(), Node{}, run.RunID); err != nil || c.cancels != 1 {
		t.Fatalf("cancel err=%v", err)
	}
}

func TestExecutionServiceSyncTerminalClearsProjectActiveRun(t *testing.T) {
	c := &lifecycleClient{}
	s := NewExecutionService(&lifecycleBuilder{}, c)
	plan, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(plan.ID, []string{"ACK_RISK"}); err != nil {
		t.Fatal(err)
	}
	run, err := s.Start(context.Background(), Node{}, plan.ID)
	if err != nil {
		t.Fatal(err)
	}
	current, _, err := s.Sync(context.Background(), Node{}, run.RunID)
	if err != nil || current.State != "SUCCEEDED" {
		t.Fatalf("terminal=%#v err=%v", current, err)
	}
	s.mu.Lock()
	_, active := s.projects["project-1"]
	s.mu.Unlock()
	if active {
		t.Fatal("terminal run remained active for its project")
	}
}

func TestExecutionServiceStartRechecksDetachedPriorRun(t *testing.T) {
	for _, scenario := range []struct {
		name, state  string
		err          error
		wrongProject bool
		wantCode     string
	}{
		{name: "failed terminal permits fresh start", state: "FAILED"},
		{name: "succeeded terminal permits fresh start", state: "SUCCEEDED"},
		{name: "cancelled terminal permits fresh start", state: "CANCELLED"},
		{name: "interrupted terminal permits fresh start", state: "INTERRUPTED"},
		{name: "running remains blocked", state: "RUNNING", wantCode: ActiveRunExists},
		{name: "unknown status remains blocked", state: "UNKNOWN", wantCode: ActiveRunExists},
		{name: "identity mismatch fails closed", state: "FAILED", wrongProject: true, wantCode: OwnershipMismatch},
		{name: "unavailable status fails closed", err: &ExecutionError{Code: ExecutionNodeUnavailable}, wantCode: ExecutionNodeUnavailable},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			client := &priorRunClient{lifecycleClient: &lifecycleClient{}, priorState: scenario.state, observeErr: scenario.err, wrongProject: scenario.wrongProject}
			service := NewExecutionService(&lifecycleBuilder{}, client)
			first, err := service.CreatePlan(t.Context(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
			if err != nil {
				t.Fatal(err)
			}
			if err := service.ApprovePlan(first.ID, []string{"ACK_RISK"}); err != nil {
				t.Fatal(err)
			}
			initial, err := service.Start(t.Context(), Node{}, first.ID)
			if err != nil || initial.RunID != "installer-1" {
				t.Fatalf("initial=%#v err=%v", initial, err)
			}
			second, err := service.CreatePlan(t.Context(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
			if err != nil {
				t.Fatal(err)
			}
			if err := service.ApprovePlan(second.ID, []string{"ACK_RISK"}); err != nil {
				t.Fatal(err)
			}
			restarted, err := service.Start(t.Context(), Node{}, second.ID)
			if scenario.wantCode != "" {
				var executionErr *ExecutionError
				if !errors.As(err, &executionErr) || executionErr.Code != scenario.wantCode || client.starts != 1 {
					t.Fatalf("unexpected retry result=%#v err=%v starts=%d", restarted, err, client.starts)
				}
				return
			}
			if err != nil || restarted.RunID != "installer-2" || client.starts != 2 {
				t.Fatalf("terminal retry=%#v err=%v starts=%d", restarted, err, client.starts)
			}
		})
	}
}

func TestExecutionServiceExpiredPlan(t *testing.T) {
	s := NewExecutionService(&lifecycleBuilder{}, &lifecycleClient{})
	clock := time.Now()
	s.now = func() time.Time { return clock }
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	clock = clock.Add(59 * time.Minute)
	if _, err := s.GetPlan(p.ID); err != nil {
		t.Fatalf("plan expired before one-hour TTL: %v", err)
	}
	clock = clock.Add(time.Minute)
	if _, err := s.GetPlan(p.ID); err == nil || err.(*ExecutionError).Code != PlanExpired {
		t.Fatal(err)
	}
}

func TestExecutionServiceSyncAdvancesPastExplicitHistoryTruncation(t *testing.T) {
	runID := "installer-500"
	event := validEvent(runID, 5)
	client := &syncPageClient{pages: map[int]ExecutionEventPage{
		0: {Events: []ExecutionEvent{event}, NextSequence: 5, EarliestSequence: 5, HistoryTruncated: true},
		5: {NextSequence: 5},
	}}
	service := NewExecutionService(&lifecycleBuilder{}, client)
	service.sessions[runID] = &session{run: ExecutionRun{RunID: runID}, project: "project", subs: map[uint64]*Subscription{}}
	_, events, err := service.Sync(context.Background(), Node{}, runID)
	if len(events) != 1 || events[0].Sequence != 5 || err == nil || err.Error() != ObserverHistoryTruncated {
		t.Fatalf("events=%v err=%v", events, err)
	}
	_, events, err = service.Sync(context.Background(), Node{}, runID)
	if err != nil || len(events) != 0 || len(client.afters) != 2 || client.afters[1] != 5 {
		t.Fatalf("second events=%v err=%v afters=%v", events, err, client.afters)
	}
}

func TestExecutionServiceSyncRejectsMoreThanJournalCapacity(t *testing.T) {
	runID := "installer-501"
	pages := map[int]ExecutionEventPage{}
	after := 0
	for after < maxObservedExecutionEvents+1 {
		count := ExecutionEventPageLimit
		if remaining := maxObservedExecutionEvents + 1 - after; remaining < count {
			count = remaining
		}
		events := eventSeries(runID, after+count)[after:]
		next := after + count
		pages[after] = ExecutionEventPage{Events: events, NextSequence: next, HasMore: next < maxObservedExecutionEvents+1}
		after = next
	}
	client := &syncPageClient{pages: pages}
	service := NewExecutionService(&lifecycleBuilder{}, client)
	service.sessions[runID] = &session{run: ExecutionRun{RunID: runID}, project: "project", subs: map[uint64]*Subscription{}}
	if _, _, err := service.Sync(context.Background(), Node{}, runID); err == nil || err.Error() != ObserverIntegrityFailure {
		t.Fatalf("capacity err=%v", err)
	}
	maxPages := (maxObservedExecutionEvents + 1 + ExecutionEventPageLimit - 1) / ExecutionEventPageLimit
	if len(client.afters) > maxPages {
		t.Fatalf("unbounded page drain: %d", len(client.afters))
	}
}

type servicePlanBuilder struct {
	requirements []artifactsource.Requirement
	calls        int
}

func (b *servicePlanBuilder) BuildDeploymentPlan(_ context.Context, _ Node, _ string, release map[string]any) (DeploymentPlan, error) {
	b.calls++
	return DeploymentPlan{ID: "service-plan", Status: "EXECUTABLE", ProjectIdentity: "service-project", ProjectRevision: "revision", PlanFingerprint: "plan-fingerprint", RuntimeRelease: release, ArtifactRequirements: b.requirements, stagingID: "staging-1", executionManifestDigest: "sha256:test"}, nil
}

func TestExecutionServiceKeepsBlockedPlanReviewableButNotApprovable(t *testing.T) {
	b := &lifecycleBuilder{}
	s := NewExecutionService(b, &lifecycleClient{})
	b.stale = false
	record, err := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	s.mu.Lock()
	stored := s.plans[record.ID]
	stored.Plan.Status = "BLOCKED"
	stored.Plan.Findings = []Finding{{Code: "PROJECT_VALIDATION_BLOCKED", SafeMessage: "Authoritative project validation is blocked"}}
	s.plans[record.ID] = stored
	s.mu.Unlock()
	err = s.ApprovePlan(record.ID, record.Plan.Acknowledgements)
	executionErr, ok := err.(*ExecutionError)
	if !ok || executionErr.Code != PlanBlocked || len(executionErr.Findings) != 1 {
		t.Fatalf("err=%#v", err)
	}
}

type projectionStager struct {
	calls       int
	projections map[string]map[string]artifactsource.Result
}

func (s *projectionStager) StageRuntimeProjection(_ context.Context, _ Node, _ string, _ string, _ string, _ string, projections map[string]map[string]artifactsource.Result, _ map[string]string) error {
	s.calls++
	s.projections = projections
	return nil
}

func TestExecutionServiceStartServiceResolvesFreshPlanBeforeStart(t *testing.T) {
	requirement := artifactsource.Requirement{ID: "kafka-java", Name: "java-21-openjdk-headless", OS: "redos", Architecture: "x86_64"}
	b := &servicePlanBuilder{requirements: []artifactsource.Requirement{requirement}}
	c := &lifecycleClient{}
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{Status: artifactsource.NotFound}}
	stager := &projectionStager{}
	s := NewExecutionService(b, c)
	s.ConfigureServiceExecution(probe, stager)
	request := ServicePlanRequest{Service: "kafka", Operation: "apply", Target: Node{ID: "target-1"}, ArtifactTargets: []Node{{ID: "target-1"}}, BundleCandidates: []artifactsource.Candidate{{ID: "java", Name: requirement.Name, OS: requirement.OS, Architecture: requirement.Architecture, Artifacts: []artifactsource.Artifact{{Ref: "runtime/java.rpm", SHA256: "sha256:x", Size: 1}}}}}
	record, err := s.CreateServicePlan(context.Background(), Node{}, request, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(record.ID, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := s.StartService(context.Background(), Node{}, record.ID); err != nil {
		t.Fatal(err)
	}
	if b.calls != 2 || probe.calls != 1 || stager.calls != 1 || c.starts != 1 {
		t.Fatalf("builder=%d probe=%d stager=%d starts=%d", b.calls, probe.calls, stager.calls, c.starts)
	}
	if stager.projections["target-1"][requirement.ID].Source != artifactsource.OfflineBundle {
		t.Fatalf("projection=%v", stager.projections)
	}
}

func TestExecutionServiceStartServiceBlocksBeforeStart(t *testing.T) {
	requirement := artifactsource.Requirement{ID: "kafka-java", Name: "java-21-openjdk-headless", OS: "redos", Architecture: "x86_64"}
	b := &servicePlanBuilder{requirements: []artifactsource.Requirement{requirement}}
	c := &lifecycleClient{}
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{Status: artifactsource.NotFound}}
	stager := &projectionStager{}
	s := NewExecutionService(b, c)
	s.ConfigureServiceExecution(probe, stager)
	record, err := s.CreateServicePlan(context.Background(), Node{}, ServicePlanRequest{Service: "kafka", Target: Node{ID: "target-1"}, ArtifactTargets: []Node{{ID: "target-1"}}}, "project", map[string]any{"bundleDigest": "sha256:x"})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.ApprovePlan(record.ID, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := s.StartService(context.Background(), Node{}, record.ID); err == nil || err.Error() != ServiceExecutionBlocked {
		t.Fatalf("err=%v", err)
	}
	if c.starts != 0 || stager.calls != 0 {
		t.Fatalf("starts=%d stager=%d", c.starts, stager.calls)
	}
}

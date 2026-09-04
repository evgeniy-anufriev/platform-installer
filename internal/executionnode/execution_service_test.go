package executionnode

import (
	"context"
	"testing"
	"time"

	"platform-installer/internal/artifactsource"
)

type lifecycleBuilder struct {
	calls int
	stale bool
}

func (b *lifecycleBuilder) BuildDeploymentPlan(_ context.Context, _ Node, _ string, release map[string]any) (DeploymentPlan, error) {
	b.calls++
	fp := "sha256:plan"
	if b.stale && b.calls > 1 {
		fp = "sha256:changed"
	}
	return DeploymentPlan{ID: "plan-1", Status: "EXECUTABLE", ProjectIdentity: "project-1", ProjectRevision: "sha256:revision", PlanFingerprint: fp, Acknowledgements: []string{"ACK_RISK"}, RuntimeRelease: release}, nil
}

type lifecycleClient struct {
	starts, cancels int
	events          []ExecutionEvent
}

func (c *lifecycleClient) StartExecution(_ context.Context, _ Node, r ExecutionStartRequest) (ExecutionRun, error) {
	c.starts++
	return ExecutionRun{RunID: "run-1", State: "RUNNING", Sequence: 0}, nil
}
func (c *lifecycleClient) GetExecution(context.Context, Node, string) (ExecutionRun, error) {
	return ExecutionRun{RunID: "run-1", State: "SUCCEEDED", Sequence: 2}, nil
}
func (c *lifecycleClient) GetEvents(context.Context, Node, string, int) ([]ExecutionEvent, error) {
	return c.events, nil
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

func TestExecutionServiceExpiredPlan(t *testing.T) {
	s := NewExecutionService(&lifecycleBuilder{}, &lifecycleClient{})
	clock := time.Now()
	s.now = func() time.Time { return clock }
	p, _ := s.CreatePlan(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"})
	clock = clock.Add(time.Hour)
	if _, err := s.GetPlan(p.ID); err == nil || err.(*ExecutionError).Code != PlanExpired {
		t.Fatal(err)
	}
}

type servicePlanBuilder struct {
	requirements []artifactsource.Requirement
	calls        int
}

func (b *servicePlanBuilder) BuildDeploymentPlan(_ context.Context, _ Node, _ string, release map[string]any) (DeploymentPlan, error) {
	b.calls++
	return DeploymentPlan{ID: "service-plan", Status: "EXECUTABLE", ProjectIdentity: "service-project", ProjectRevision: "revision", PlanFingerprint: "plan-fingerprint", RuntimeRelease: release, ArtifactRequirements: b.requirements}, nil
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

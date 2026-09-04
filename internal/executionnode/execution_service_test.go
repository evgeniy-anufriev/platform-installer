package executionnode

import (
	"context"
	"testing"
	"time"
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
	return DeploymentPlan{ID: "plan-1", ProjectIdentity: "project-1", ProjectRevision: "sha256:revision", PlanFingerprint: fp, Acknowledgements: []string{"ACK_RISK"}, RuntimeRelease: release}, nil
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

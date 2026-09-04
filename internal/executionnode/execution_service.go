package executionnode

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

// ExecutionError is a semantic application error.  Transport diagnostics are
// deliberately not used as an API and are never needed to make lifecycle
// decisions.
type ExecutionError struct {
	Code  string
	RunID string
}

func (e *ExecutionError) Error() string {
	if e.RunID == "" {
		return e.Code
	}
	return fmt.Sprintf("%s: %s", e.Code, e.RunID)
}

const (
	PlanExpired              = "PLAN_EXPIRED"
	PlanStale                = "PLAN_STALE"
	ApprovalRequired         = "APPROVAL_REQUIRED"
	AcknowledgementRequired  = "ACKNOWLEDGEMENT_REQUIRED"
	ActiveRunExists          = "ACTIVE_RUN_EXISTS"
	RunNotFound              = "RUN_NOT_FOUND"
	ExecutionNodeUnavailable = "EXECUTION_NODE_UNAVAILABLE"
	OwnershipMismatch        = "OWNERSHIP_MISMATCH"
	CancelNotAllowed         = "CANCEL_NOT_ALLOWED"
)

type DeploymentPlan struct {
	ID               string
	ProjectIdentity  string
	ProjectRevision  string
	PlanFingerprint  string
	Acknowledgements []string
	RuntimeRelease   map[string]any
}

type PlanRecord struct {
	ID        string
	Plan      DeploymentPlan
	CreatedAt time.Time
	ExpiresAt time.Time
	Approved  bool
	Consumed  bool
}

type PlanBuilder interface {
	BuildDeploymentPlan(context.Context, Node, string, map[string]any) (DeploymentPlan, error)
}

type ExecutionClient interface {
	StartExecution(context.Context, Node, ExecutionStartRequest) (ExecutionRun, error)
	GetExecution(context.Context, Node, string) (ExecutionRun, error)
	GetEvents(context.Context, Node, string, int) ([]ExecutionEvent, error)
	CancelExecution(context.Context, Node, string) (ExecutionRun, error)
}

type session struct {
	mu           sync.Mutex
	run          ExecutionRun
	project      string
	lastSequence int
	subs         map[uint64]*Subscription
	nextSub      uint64
}

type Subscription struct {
	C            <-chan ExecutionEvent
	c            chan ExecutionEvent
	done         chan struct{}
	once         sync.Once
	closeChannel sync.Once
}

func (s *Subscription) Close() {
	s.once.Do(func() { close(s.done); s.closeChannel.Do(func() { close(s.c) }) })
}

type ExecutionService struct {
	startMu      sync.Mutex
	builder      PlanBuilder
	client       ExecutionClient
	now          func() time.Time
	ttl          time.Duration
	mu           sync.Mutex
	plans        map[string]PlanRecord
	sessions     map[string]*session
	projects     map[string]string
	projectRoots map[string]string
}

func NewExecutionService(builder PlanBuilder, client ExecutionClient) *ExecutionService {
	return &ExecutionService{builder: builder, client: client, now: time.Now, ttl: 15 * time.Minute, plans: map[string]PlanRecord{}, sessions: map[string]*session{}, projects: map[string]string{}, projectRoots: map[string]string{}}
}

func (s *ExecutionService) CreatePlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (PlanRecord, error) {
	if s == nil || s.builder == nil || projectRoot == "" {
		return PlanRecord{}, errors.New("EXECUTION_PLAN_INPUT_INVALID")
	}
	plan, err := s.builder.BuildDeploymentPlan(ctx, node, projectRoot, runtimeRelease)
	if err != nil {
		return PlanRecord{}, err
	}
	if plan.ID == "" || plan.ProjectIdentity == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" {
		return PlanRecord{}, errors.New("DEPLOYMENT_PLAN_INVALID")
	}
	now := s.now().UTC()
	record := PlanRecord{ID: plan.ID, Plan: cloneDeploymentPlan(plan), CreatedAt: now, ExpiresAt: now.Add(s.ttl)}
	s.mu.Lock()
	s.plans[record.ID] = record
	s.projectRoots[record.ID] = projectRoot
	s.mu.Unlock()
	return clonePlanRecord(record), nil
}

func (s *ExecutionService) GetPlan(id string) (PlanRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.plans[id]
	if !ok {
		return PlanRecord{}, &ExecutionError{Code: PlanExpired}
	}
	if !s.now().Before(record.ExpiresAt) {
		delete(s.plans, id)
		return PlanRecord{}, &ExecutionError{Code: PlanExpired}
	}
	return clonePlanRecord(record), nil
}

func (s *ExecutionService) ApprovePlan(id string, acknowledgements []string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	record, ok := s.plans[id]
	if !ok || !s.now().Before(record.ExpiresAt) {
		delete(s.plans, id)
		return &ExecutionError{Code: PlanExpired}
	}
	if record.Consumed {
		return &ExecutionError{Code: ApprovalRequired}
	}
	if !sameStrings(record.Plan.Acknowledgements, acknowledgements) {
		return &ExecutionError{Code: AcknowledgementRequired}
	}
	record.Approved = true
	s.plans[id] = record
	return nil
}

func (s *ExecutionService) Start(ctx context.Context, node Node, planID string) (ExecutionRun, error) {
	s.startMu.Lock()
	defer s.startMu.Unlock()
	record, err := s.GetPlan(planID)
	if err != nil {
		return ExecutionRun{}, err
	}
	if !record.Approved || record.Consumed {
		return ExecutionRun{}, &ExecutionError{Code: ApprovalRequired}
	}
	s.mu.Lock()
	if prior := s.projects[record.Plan.ProjectIdentity]; prior != "" {
		if existing := s.sessions[prior]; existing != nil {
			existing.mu.Lock()
			state := existing.run.State
			existing.mu.Unlock()
			if state == "RUNNING" || state == "STARTING" || state == "CANCELLING" {
				s.mu.Unlock()
				return ExecutionRun{}, &ExecutionError{Code: ActiveRunExists, RunID: prior}
			}
		}
	}
	s.mu.Unlock()
	s.mu.Lock()
	projectRoot := s.projectRoots[planID]
	s.mu.Unlock()
	fresh, err := s.builder.BuildDeploymentPlan(ctx, node, projectRoot, record.Plan.RuntimeRelease)
	if err != nil {
		return ExecutionRun{}, err
	}
	if fresh.PlanFingerprint != record.Plan.PlanFingerprint {
		s.invalidate(planID)
		return ExecutionRun{}, &ExecutionError{Code: PlanStale}
	}
	run, err := s.client.StartExecution(ctx, node, ExecutionStartRequest{RunID: newRunID(), ProjectIdentity: fresh.ProjectIdentity, PlanFingerprint: fresh.PlanFingerprint, RuntimeRelease: fresh.RuntimeRelease})
	if err != nil {
		return ExecutionRun{}, err
	}
	s.mu.Lock()
	record.Consumed = true
	s.plans[planID] = record
	if prior := s.projects[fresh.ProjectIdentity]; prior != "" && prior != run.RunID {
		s.mu.Unlock()
		return ExecutionRun{}, &ExecutionError{Code: ActiveRunExists, RunID: prior}
	}
	s.projects[fresh.ProjectIdentity] = run.RunID
	s.sessions[run.RunID] = &session{run: run, project: fresh.ProjectIdentity, lastSequence: run.Sequence, subs: map[uint64]*Subscription{}}
	s.mu.Unlock()
	return run, nil
}

func (s *ExecutionService) invalidate(id string) {
	s.mu.Lock()
	if p, ok := s.plans[id]; ok {
		p.Approved = false
		p.Consumed = true
		s.plans[id] = p
	}
	s.mu.Unlock()
}

func (s *ExecutionService) Sync(ctx context.Context, node Node, runID string) (ExecutionRun, []ExecutionEvent, error) {
	s.mu.Lock()
	current, ok := s.sessions[runID]
	s.mu.Unlock()
	if !ok {
		return ExecutionRun{}, nil, &ExecutionError{Code: RunNotFound, RunID: runID}
	}
	run, err := s.client.GetExecution(ctx, node, runID)
	if err != nil {
		return ExecutionRun{}, nil, err
	}
	current.mu.Lock()
	after := current.lastSequence
	current.mu.Unlock()
	events, err := s.client.GetEvents(ctx, node, runID, after)
	if err != nil {
		return run, nil, err
	}
	current.mu.Lock()
	current.run = run
	for _, event := range events {
		if event.Sequence <= current.lastSequence {
			continue
		}
		current.lastSequence = event.Sequence
		for id, sub := range current.subs {
			select {
			case sub.c <- event:
			default:
				sub.Close()
				delete(current.subs, id)
			}
		}
	}
	current.mu.Unlock()
	return run, events, nil
}

func (s *ExecutionService) Reconnect(ctx context.Context, node Node, runID string) (ExecutionRun, []ExecutionEvent, error) {
	s.mu.Lock()
	_, known := s.sessions[runID]
	s.mu.Unlock()
	if !known {
		run, err := s.client.GetExecution(ctx, node, runID)
		if err != nil {
			return ExecutionRun{}, nil, err
		}
		if run.RunID == "" {
			return ExecutionRun{}, nil, &ExecutionError{Code: RunNotFound, RunID: runID}
		}
		s.mu.Lock()
		s.sessions[runID] = &session{run: run, project: run.ProjectIdentity, lastSequence: run.Sequence, subs: map[uint64]*Subscription{}}
		if run.ProjectIdentity != "" {
			s.projects[run.ProjectIdentity] = runID
		}
		s.mu.Unlock()
	}
	return s.Sync(ctx, node, runID)
}

func (s *ExecutionService) Subscribe(runID string, capacity int) (*Subscription, error) {
	if capacity < 1 {
		return nil, errors.New("SUBSCRIBER_CAPACITY_INVALID")
	}
	s.mu.Lock()
	current, ok := s.sessions[runID]
	s.mu.Unlock()
	if !ok {
		return nil, &ExecutionError{Code: RunNotFound, RunID: runID}
	}
	channel := make(chan ExecutionEvent, capacity)
	sub := &Subscription{C: channel, c: channel, done: make(chan struct{})}
	current.mu.Lock()
	subID := current.nextSub
	current.nextSub++
	current.subs[subID] = sub
	current.mu.Unlock()
	return sub, nil
}

func (s *ExecutionService) Unsubscribe(runID string, sub *Subscription) {
	if sub == nil {
		return
	}
	s.mu.Lock()
	current := s.sessions[runID]
	s.mu.Unlock()
	if current != nil {
		current.mu.Lock()
		for id, candidate := range current.subs {
			if candidate == sub {
				delete(current.subs, id)
				break
			}
		}
		current.mu.Unlock()
	}
	sub.Close()
}

func (s *ExecutionService) Cancel(ctx context.Context, node Node, runID string) (ExecutionRun, error) {
	s.mu.Lock()
	current := s.sessions[runID]
	s.mu.Unlock()
	if current == nil {
		return ExecutionRun{}, &ExecutionError{Code: RunNotFound, RunID: runID}
	}
	return s.client.CancelExecution(ctx, node, runID)
}

func sameStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	seen := map[string]bool{}
	for _, v := range a {
		seen[v] = true
	}
	for _, v := range b {
		if !seen[v] {
			return false
		}
	}
	return true
}
func cloneDeploymentPlan(p DeploymentPlan) DeploymentPlan {
	p.Acknowledgements = append([]string(nil), p.Acknowledgements...)
	if p.RuntimeRelease != nil {
		p.RuntimeRelease = map[string]any{}
		for k, v := range p.RuntimeRelease {
			p.RuntimeRelease[k] = v
		}
	}
	return p
}
func clonePlanRecord(p PlanRecord) PlanRecord { p.Plan = cloneDeploymentPlan(p.Plan); return p }
func newRunID() string                        { return fmt.Sprintf("installer-%d", time.Now().UnixNano()) }

package executionnode

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"sync"
	"time"

	"platform-installer/internal/artifactsource"
)

// ExecutionError is a semantic application error.  Transport diagnostics are
// deliberately not used as an API and are never needed to make lifecycle
// decisions.
type ExecutionError struct {
	Code     string
	RunID    string
	Findings []Finding
}

func (e *ExecutionError) Error() string {
	if e.RunID == "" {
		return e.Code
	}
	return fmt.Sprintf("%s: %s", e.Code, e.RunID)
}

const (
	PlanExpired              = "PLAN_EXPIRED"
	PlanBlocked              = "PLAN_BLOCKED"
	PlanStale                = "PLAN_STALE"
	ApprovalRequired         = "APPROVAL_REQUIRED"
	AcknowledgementRequired  = "ACKNOWLEDGEMENT_REQUIRED"
	ActiveRunExists          = "ACTIVE_RUN_EXISTS"
	RunNotFound              = "RUN_NOT_FOUND"
	ExecutionNodeUnavailable = "EXECUTION_NODE_UNAVAILABLE"
	OwnershipMismatch        = "OWNERSHIP_MISMATCH"
	CancelNotAllowed         = "CANCEL_NOT_ALLOWED"
	ServiceExecutionBlocked  = "SERVICE_EXECUTION_BLOCKED"
)

type DeploymentPlan struct {
	ID                     string
	Status                 string
	ProjectIdentity        string
	ProjectRevision        string
	PlanFingerprint        string
	Acknowledgements       []string
	AcknowledgementDetails []PlanAcknowledgement
	Phases                 []DeploymentPlanPhase
	RuntimeRelease         map[string]any
	ArtifactRequirements   []artifactsource.Requirement
	Findings               []Finding
	executionID            string
}

// PlanAcknowledgement and DeploymentPlanPhase retain the closed, Core-owned
// planning vocabulary needed by the Installation facade. They do not describe
// desired state and are never persisted by the Installer.
type PlanAcknowledgement struct {
	Code    string
	Summary string
}

type DeploymentPlanPhase struct {
	ID      string
	Order   int
	Actions []DeploymentPlanAction
}

type DeploymentPlanAction struct {
	ID                string
	Type              string
	ServiceDeployment string
	Targets           []string
	DependsOn         []string
	Mutating          bool
	Reboot            string
	Summary           string
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
	GetEvents(context.Context, Node, string, int, int) (ExecutionEventPage, error)
	CancelExecution(context.Context, Node, string) (ExecutionRun, error)
}

// ServicePlanRequest contains only operator/project routing and approved
// bundle candidates. Artifact requirements are read from the fresh Core plan.
type ServicePlanRequest struct {
	Service          string
	Operation        string
	Target           Node
	ArtifactTargets  []Node
	BundleCandidates []artifactsource.Candidate
	PKISecretFiles   map[string]string
}

type RuntimeProjectionStager interface {
	StageRuntimeProjection(context.Context, Node, string, string, string, string, map[string]map[string]artifactsource.Result, map[string]string) error
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
	startMu          sync.Mutex
	builder          PlanBuilder
	client           ExecutionClient
	now              func() time.Time
	ttl              time.Duration
	mu               sync.Mutex
	plans            map[string]PlanRecord
	sessions         map[string]*session
	projects         map[string]string
	projectRoots     map[string]string
	serviceRequests  map[string]ServicePlanRequest
	probe            TargetRepositoryProbe
	projectionStager RuntimeProjectionStager
}

func NewExecutionService(builder PlanBuilder, client ExecutionClient) *ExecutionService {
	return &ExecutionService{builder: builder, client: client, now: time.Now, ttl: 15 * time.Minute, plans: map[string]PlanRecord{}, sessions: map[string]*session{}, projects: map[string]string{}, projectRoots: map[string]string{}, serviceRequests: map[string]ServicePlanRequest{}}
}

func (s *ExecutionService) ConfigureServiceExecution(probe TargetRepositoryProbe, stager RuntimeProjectionStager) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.probe, s.projectionStager = probe, stager
}

func (s *ExecutionService) CreateServicePlan(ctx context.Context, node Node, request ServicePlanRequest, projectRoot string, runtimeRelease map[string]any) (PlanRecord, error) {
	if request.Service == "" || request.Target.ID == "" || len(request.ArtifactTargets) == 0 {
		return PlanRecord{}, errors.New("SERVICE_PLAN_INPUT_INVALID")
	}
	record, err := s.CreatePlan(ctx, node, projectRoot, runtimeRelease)
	if err != nil {
		return PlanRecord{}, err
	}
	s.mu.Lock()
	s.serviceRequests[record.ID] = cloneServicePlanRequest(request)
	s.mu.Unlock()
	return record, nil
}

func (s *ExecutionService) CreatePlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (PlanRecord, error) {
	if s == nil || s.builder == nil || projectRoot == "" {
		return PlanRecord{}, errors.New("EXECUTION_PLAN_INPUT_INVALID")
	}
	plan, err := s.builder.BuildDeploymentPlan(ctx, node, projectRoot, runtimeRelease)
	if err != nil {
		return PlanRecord{}, err
	}
	if plan.ID == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" || (plan.Status != "EXECUTABLE" && plan.Status != "BLOCKED") || (plan.Status == "EXECUTABLE" && plan.ProjectIdentity == "") {
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
	if record.Plan.Status != "EXECUTABLE" {
		return &ExecutionError{Code: PlanBlocked, Findings: append([]Finding(nil), record.Plan.Findings...)}
	}
	if !sameStrings(record.Plan.Acknowledgements, acknowledgements) {
		return &ExecutionError{Code: AcknowledgementRequired}
	}
	record.Approved = true
	s.plans[id] = record
	return nil
}

func (s *ExecutionService) Start(ctx context.Context, node Node, planID string) (ExecutionRun, error) {
	return s.start(ctx, node, planID, nil)
}

func (s *ExecutionService) StartService(ctx context.Context, node Node, planID string) (ExecutionRun, error) {
	return s.start(ctx, node, planID, func(fresh DeploymentPlan, request ServicePlanRequest, runID string) error {
		s.mu.Lock()
		probe, stager := s.probe, s.projectionStager
		s.mu.Unlock()
		if probe == nil || stager == nil || len(fresh.ArtifactRequirements) == 0 {
			return errors.New("SERVICE_EXECUTION_INPUT_INVALID")
		}
		resolved, _, err := NewServiceExecutionService(probe, nil).Resolve(ctx, ServiceExecutionRequest{
			Service: request.Service, Operation: request.Operation, ProjectRoot: s.projectRoots[planID], Target: request.Target,
			ArtifactTargets: request.ArtifactTargets, Requirements: fresh.ArtifactRequirements, BundleCandidates: request.BundleCandidates,
		})
		if err != nil {
			return err
		}
		for _, projection := range resolved {
			for _, result := range projection {
				if result.Source == artifactsource.Blocked {
					return errors.New(ServiceExecutionBlocked)
				}
			}
		}
		requirements, err := json.Marshal(fresh.ArtifactRequirements)
		if err != nil {
			return err
		}
		sum := sha256.Sum256(requirements)
		return stager.StageRuntimeProjection(ctx, node, runID, fresh.ProjectIdentity, fresh.PlanFingerprint, "sha256:"+hex.EncodeToString(sum[:]), resolved, request.PKISecretFiles)
	})
}

func (s *ExecutionService) start(ctx context.Context, node Node, planID string, prepare func(DeploymentPlan, ServicePlanRequest, string) error) (ExecutionRun, error) {
	s.startMu.Lock()
	defer s.startMu.Unlock()
	record, err := s.GetPlan(planID)
	if err != nil {
		return ExecutionRun{}, err
	}
	if !record.Approved || record.Consumed {
		return ExecutionRun{}, &ExecutionError{Code: ApprovalRequired}
	}
	if record.Plan.Status != "EXECUTABLE" {
		return ExecutionRun{}, &ExecutionError{Code: PlanBlocked, Findings: append([]Finding(nil), record.Plan.Findings...)}
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
	if projectRoot == "" {
		return ExecutionRun{}, errors.New("EXECUTION_PLAN_PROJECT_ROOT_MISSING")
	}
	if len(record.Plan.RuntimeRelease) == 0 {
		return ExecutionRun{}, errors.New("EXECUTION_PLAN_RUNTIME_RELEASE_MISSING")
	}
	fresh, err := s.builder.BuildDeploymentPlan(ctx, node, projectRoot, record.Plan.RuntimeRelease)
	if err != nil {
		return ExecutionRun{}, err
	}
	if fresh.PlanFingerprint != record.Plan.PlanFingerprint {
		s.invalidate(planID)
		return ExecutionRun{}, &ExecutionError{Code: PlanStale}
	}
	runID := fresh.executionID
	if runID == "" {
		runID, err = newRunID()
		if err != nil {
			return ExecutionRun{}, err
		}
	}
	if prepare != nil {
		s.mu.Lock()
		request, ok := s.serviceRequests[planID]
		projectRoot := s.projectRoots[planID]
		s.mu.Unlock()
		if !ok || projectRoot == "" {
			return ExecutionRun{}, errors.New("SERVICE_PLAN_NOT_FOUND")
		}
		if err := prepare(fresh, request, runID); err != nil {
			return ExecutionRun{}, err
		}
	}
	run, err := s.client.StartExecution(ctx, node, ExecutionStartRequest{RunID: runID, ProjectIdentity: fresh.ProjectIdentity, PlanFingerprint: fresh.PlanFingerprint, RuntimeRelease: fresh.RuntimeRelease})
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
	events := []ExecutionEvent{}
	historyTruncated := false
	for {
		page, pageErr := s.client.GetEvents(ctx, node, runID, after, ExecutionEventPageLimit)
		if pageErr != nil {
			return run, nil, pageErr
		}
		if len(events)+len(page.Events) > maxObservedExecutionEvents {
			return run, nil, &ObserverError{Code: ObserverIntegrityFailure}
		}
		historyTruncated = historyTruncated || page.HistoryTruncated
		events = append(events, page.Events...)
		after = page.NextSequence
		if !page.HasMore {
			break
		}
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
	if run.State == "SUCCEEDED" || run.State == "FAILED" || run.State == "CANCELLED" || run.State == "INTERRUPTED" {
		s.mu.Lock()
		if s.projects[current.project] == runID {
			delete(s.projects, current.project)
		}
		s.mu.Unlock()
	}
	if historyTruncated {
		return run, events, &ObserverError{Code: ObserverHistoryTruncated}
	}
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
	p.AcknowledgementDetails = append([]PlanAcknowledgement(nil), p.AcknowledgementDetails...)
	p.Phases = clonePlanPhases(p.Phases)
	p.ArtifactRequirements = append([]artifactsource.Requirement(nil), p.ArtifactRequirements...)
	p.Findings = append([]Finding(nil), p.Findings...)
	if p.RuntimeRelease != nil {
		runtimeRelease := p.RuntimeRelease
		p.RuntimeRelease = map[string]any{}
		for k, v := range runtimeRelease {
			p.RuntimeRelease[k] = v
		}
	}
	return p
}

func clonePlanPhases(phases []DeploymentPlanPhase) []DeploymentPlanPhase {
	result := make([]DeploymentPlanPhase, len(phases))
	for index, phase := range phases {
		result[index] = phase
		result[index].Actions = make([]DeploymentPlanAction, len(phase.Actions))
		for actionIndex, action := range phase.Actions {
			result[index].Actions[actionIndex] = action
			result[index].Actions[actionIndex].Targets = append([]string(nil), action.Targets...)
			result[index].Actions[actionIndex].DependsOn = append([]string(nil), action.DependsOn...)
		}
	}
	return result
}
func cloneServicePlanRequest(r ServicePlanRequest) ServicePlanRequest {
	r.ArtifactTargets = append([]Node(nil), r.ArtifactTargets...)
	r.BundleCandidates = append([]artifactsource.Candidate(nil), r.BundleCandidates...)
	secretFiles := r.PKISecretFiles
	if secretFiles != nil {
		r.PKISecretFiles = make(map[string]string, len(r.PKISecretFiles))
		for reference, secretPath := range secretFiles {
			r.PKISecretFiles[reference] = secretPath
		}
	}
	return r
}
func clonePlanRecord(p PlanRecord) PlanRecord { p.Plan = cloneDeploymentPlan(p.Plan); return p }
func newRunID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return "installer-" + new(big.Int).SetBytes(value).String(), nil
}

// Package executionnode owns the narrow pre-Core readiness lifecycle.
package executionnode

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/executionbundle"
)

const APIVersion = "platform.installer/execution-node/v1alpha1"

type State string

const (
	Unreachable         State = "UNREACHABLE"
	Unprepared          State = "UNPREPARED"
	PreparationRequired State = "PREPARATION_REQUIRED"
	Ready               State = "READY"
	UpdateRequired      State = "UPDATE_REQUIRED"
	Incompatible        State = "INCOMPATIBLE"
	Broken              State = "BROKEN"
)

type Node struct {
	ID, Address, User, CredentialRef string
	Port                             uint16
	HostKey                          HostKeyPolicy
}
type HostKeyPolicy struct{ State, KnownHosts, Fingerprint string }
type Runtime struct {
	BundleVersion, BundleDigest, CoreVersion, Protocol string
	Ansible, Capabilities                              bool
}
type Finding struct{ Code, SafeMessage string }
type Inspection struct {
	State                       State
	OS, OSVersion, Architecture string
	Elevation                   bool
	FreeBytes                   int64
	Runtime                     Runtime
	Findings                    []Finding
}
type Step struct {
	ID, Action string
	Mutates    bool
}
type Plan struct {
	APIVersion, Kind, ID, Digest, NodeID string
	State                                State
	BundleDigest                         string
	Steps                                []Step
	ExpiresAt                            time.Time
}
type Result struct {
	APIVersion, Kind, PlanID string
	State                    State
	Changed                  bool
	Findings                 []Finding
	Runtime                  Runtime
}

// PreparationStepError exposes only the failed preparation boundary to the UI.
// The underlying transport error remains internal: it may contain command
// arguments, local paths, or remote output and must not cross Wails.
type PreparationStepError struct {
	Code  string
	cause error
}

func (e *PreparationStepError) Error() string { return e.Code }
func (e *PreparationStepError) Unwrap() error { return e.cause }

// ServiceExecutionRequest is the production boundary for one service run.
// Requirements and bundle candidates are package metadata. The request does
// not contain a selected source; source selection remains in artifactsource.
type ServiceExecutionRequest struct {
	Service          string
	Operation        string
	ProjectRoot      string
	Target           Node
	ArtifactTargets  []Node
	Requirements     []artifactsource.Requirement
	BundleCandidates []artifactsource.Candidate
	PKISecretFiles   map[string]string
}

type ServiceExecutionResult struct {
	Projection        map[string]artifactsource.Result
	TargetProjections map[string]map[string]artifactsource.Result
	Probes            []artifactsource.RepositoryProbeResult
	Applied           bool
}

// ServiceRuntimeExecutor is implemented by the execution-node transport. It
// receives derived runtime variables only after the shared Go-side gate.
type ServiceRuntimeExecutor interface {
	ExecuteService(context.Context, ServiceExecutionRequest, map[string]map[string]artifactsource.Result) (bool, error)
}

type TargetRepositoryProbe interface {
	ProbeRepository(context.Context, Node, artifactsource.Requirement) (artifactsource.RepositoryProbeResult, error)
}

type requestRepositoryProbe struct {
	target Node
	probe  TargetRepositoryProbe
}

func (p requestRepositoryProbe) ProbeRepository(ctx context.Context, requirement artifactsource.Requirement) (artifactsource.RepositoryProbeResult, error) {
	return p.probe.ProbeRepository(ctx, p.target, requirement)
}

// ServiceExecutionService wires the existing probe, resolver and projection
// to the existing Ansible service entrypoint. It deliberately has no Ansible
// or service policy of its own.
type ServiceExecutionService struct {
	probe   TargetRepositoryProbe
	runtime ServiceRuntimeExecutor
}

func NewServiceExecutionService(probe TargetRepositoryProbe, runtime ServiceRuntimeExecutor) *ServiceExecutionService {
	return &ServiceExecutionService{probe: probe, runtime: runtime}
}

func (s *ServiceExecutionService) Execute(ctx context.Context, request ServiceExecutionRequest) (ServiceExecutionResult, error) {
	if s == nil || s.probe == nil || s.runtime == nil || request.Service == "" || request.ProjectRoot == "" || len(request.Requirements) == 0 {
		return ServiceExecutionResult{}, errors.New("SERVICE_EXECUTION_INPUT_INVALID")
	}
	projections, probes, err := s.Resolve(ctx, request)
	if err != nil {
		return ServiceExecutionResult{Projection: projections[request.Target.ID], TargetProjections: projections, Probes: probes}, err
	}
	for _, projection := range projections {
		for _, result := range projection {
			if result.Source == artifactsource.Blocked {
				return ServiceExecutionResult{Projection: projections[request.Target.ID], TargetProjections: projections, Probes: probes}, errors.New("SERVICE_EXECUTION_BLOCKED")
			}
		}
	}
	applied, err := s.runtime.ExecuteService(ctx, request, projections)
	return ServiceExecutionResult{Projection: projections[request.Target.ID], TargetProjections: projections, Probes: probes, Applied: applied}, err
}

// Resolve performs only the existing read-only probe/resolver/projection
// phase. It never calls a service runtime or mutates a target.
func (s *ServiceExecutionService) Resolve(ctx context.Context, request ServiceExecutionRequest) (map[string]map[string]artifactsource.Result, []artifactsource.RepositoryProbeResult, error) {
	if s == nil || s.probe == nil || request.ProjectRoot == "" || len(request.Requirements) == 0 {
		return nil, nil, errors.New("SERVICE_EXECUTION_INPUT_INVALID")
	}
	targets := request.ArtifactTargets
	if len(targets) == 0 {
		targets = []Node{request.Target}
	}
	projections := make(map[string]map[string]artifactsource.Result, len(targets))
	var probes []artifactsource.RepositoryProbeResult
	for _, target := range targets {
		projection, targetProbes, err := ResolveRequirementsWithTargetProbe(ctx, target, request.Requirements, requestRepositoryProbe{target: target, probe: s.probe}, artifactsource.CandidatesProvider(request.BundleCandidates))
		projections[target.ID] = projection
		probes = append(probes, targetProbes...)
		if err != nil {
			return projections, probes, err
		}
	}
	return projections, probes, nil
}

// Transport is internal and semantic: it does not expose arbitrary remote
// command execution to the application or a future UI.
type Transport interface {
	InspectExecutionNode(context.Context, Node) (Inspection, error)
	StageVerifiedBundle(context.Context, Node, executionbundle.Verified) (string, error)
	ActivateStagedRuntime(context.Context, Node, string, executionbundle.Verified) (Runtime, error)
	DiscardStagedRuntime(context.Context, Node, string) error
}

type Service struct {
	transport Transport
	cache     executionbundle.Cache
	now       func() time.Time
	ttl       time.Duration
	mu        sync.Mutex
	plans     map[string]Plan
}

type Option func(*Service)

func WithBundleCache(cache executionbundle.Cache) Option {
	return func(service *Service) { service.cache = cache }
}

func NewService(transport Transport, options ...Option) *Service {
	service := &Service{transport: transport, now: time.Now, ttl: time.Hour, plans: map[string]Plan{}}
	for _, option := range options {
		option(service)
	}
	return service
}

func (s *Service) InspectExecutionNode(ctx context.Context, node Node) (Inspection, error) {
	if err := validNode(node); err != nil {
		return Inspection{State: Incompatible, Findings: []Finding{{"EXECUTION_NODE_INPUT_INVALID", "Execution Node connection details are invalid"}}}, nil
	}
	if node.HostKey.State != "TRUSTED" {
		return Inspection{State: Broken, Findings: []Finding{{"EXECUTION_NODE_HOST_KEY_UNTRUSTED", "Execution Node host key must be explicitly trusted"}}}, nil
	}
	inspection, err := s.transport.InspectExecutionNode(ctx, node)
	if err == nil && inspection.OS != "" && !inspection.Elevation && inspection.State != Unreachable {
		inspection.State = Broken
		inspection.Findings = append(inspection.Findings, Finding{"EXECUTION_NODE_ELEVATION_REQUIRED", "Execution Node preparation requires non-interactive sudo access"})
	}
	return inspection, err
}

func (s *Service) PlanExecutionNodePreparation(ctx context.Context, node Node, bundleRoot string) (Plan, error) {
	inspection, err := s.InspectExecutionNode(ctx, node)
	if err != nil {
		return Plan{}, err
	}
	bundle, err := s.resolveBundle(bundleRoot, inspection)
	if err != nil {
		return Plan{APIVersion: APIVersion, Kind: "ExecutionNodePreparationPlan", NodeID: node.ID, State: inspection.State, Steps: []Step{{"bundle-invalid", "BLOCKED", false}}}, nil
	}
	plan := Plan{APIVersion: APIVersion, Kind: "ExecutionNodePreparationPlan", NodeID: node.ID, State: requiredState(inspection, bundle), BundleDigest: bundle.Digest, Steps: preparationSteps(requiredState(inspection, bundle)), ExpiresAt: s.now().UTC().Add(s.ttl)}
	plan.Digest, plan.ID = planDigest(plan), planDigest(plan)
	s.mu.Lock()
	s.plans[plan.ID] = plan
	s.mu.Unlock()
	return plan, nil
}

func (s *Service) Prepare(ctx context.Context, node Node, bundleRoot, planID string) (Result, error) {
	result := Result{APIVersion: APIVersion, Kind: "ExecutionNodePreparationResult", PlanID: planID}
	s.mu.Lock()
	plan, exists := s.plans[planID]
	s.mu.Unlock()
	if !exists || plan.ID != planID || plan.Digest != planDigest(plan) || !s.now().Before(plan.ExpiresAt) {
		result.State = Broken
		result.Findings = []Finding{{"EXECUTION_NODE_PLAN_INVALID", "Preparation plan is missing, changed or expired"}}
		return result, nil
	}
	if plan.NodeID != node.ID {
		result.State = Broken
		result.Findings = []Finding{{"EXECUTION_NODE_PLAN_NODE_MISMATCH", "Preparation plan belongs to another Execution Node"}}
		return result, nil
	}
	inspection, err := s.InspectExecutionNode(ctx, node)
	if err != nil {
		return Result{}, &PreparationStepError{Code: "EXECUTION_NODE_PREPARE_INSPECT_FAILED", cause: err}
	}
	bundle, err := s.resolveBundle(bundleRoot, inspection)
	if err != nil || bundle.Digest != plan.BundleDigest {
		result.State = Broken
		result.Findings = []Finding{{"EXECUTION_NODE_BUNDLE_CHANGED", "Offline runtime bundle changed after planning"}}
		return result, nil
	}
	state := requiredState(inspection, bundle)
	if state == Ready {
		result.State, result.Runtime = Ready, inspection.Runtime
		return result, nil
	}
	if state == Incompatible || state == Broken || state == Unreachable {
		result.State, result.Findings = state, inspection.Findings
		return result, nil
	}
	stage, err := s.transport.StageVerifiedBundle(ctx, node, bundle)
	if err != nil {
		return Result{}, &PreparationStepError{Code: "EXECUTION_NODE_PREPARE_STAGE_FAILED", cause: err}
	}
	runtime, err := s.transport.ActivateStagedRuntime(ctx, node, stage, bundle)
	if err != nil {
		_ = s.transport.DiscardStagedRuntime(context.Background(), node, stage)
		return Result{}, &PreparationStepError{Code: "EXECUTION_NODE_PREPARE_ACTIVATE_FAILED", cause: err}
	}
	_ = s.transport.DiscardStagedRuntime(context.Background(), node, stage)
	result.Changed, result.Runtime = true, runtime
	if runtime.BundleDigest != bundle.Digest || runtime.Protocol != executionbundle.ProtocolVersion || !runtime.Ansible || !runtime.Capabilities {
		result.State = Broken
		result.Findings = []Finding{{"EXECUTION_NODE_RUNTIME_VERIFY_FAILED", "Prepared runtime did not pass the capability handshake"}}
		return result, nil
	}
	result.State = Ready
	return result, nil
}

func (s *Service) resolveBundle(override string, inspection Inspection) (executionbundle.Verified, error) {
	if s.cache.Root == "" {
		return executionbundle.ValidateRoot(override)
	}
	return s.cache.Resolve(override, executionbundle.Platform{
		OS: inspection.OS, Version: inspection.OSVersion, Architecture: inspection.Architecture,
	})
}

func requiredState(i Inspection, bundle executionbundle.Verified) State {
	if i.State == Unreachable || i.State == Incompatible || i.State == Broken {
		return i.State
	}
	if !i.Elevation {
		return Broken
	}
	if i.OS == "" || i.OSVersion == "" || i.Architecture == "" || i.FreeBytes <= 0 {
		return PreparationRequired
	}
	compatible := false
	for _, platform := range bundle.Manifest.Platforms {
		if platform.OS == i.OS && platform.Version == i.OSVersion && platform.Architecture == i.Architecture {
			compatible = true
			break
		}
	}
	if !compatible {
		return Incompatible
	}
	if i.Runtime.BundleDigest == "" {
		return Unprepared
	}
	if i.Runtime.BundleDigest != bundle.Digest || i.Runtime.Protocol != executionbundle.ProtocolVersion {
		return UpdateRequired
	}
	if !i.Runtime.Ansible || !i.Runtime.Capabilities {
		return Broken
	}
	return Ready
}
func preparationSteps(state State) []Step {
	if state == Ready {
		return []Step{{"verify-ready", "VERIFY", false}}
	}
	if state == Incompatible || state == Broken || state == Unreachable {
		return []Step{{"blocked", "BLOCKED", false}}
	}
	return []Step{{"verify-bundle", "VERIFY", false}, {"stage-runtime", "TRANSFER", true}, {"activate-runtime", "ACTIVATE", true}, {"capability-handshake", "VERIFY", false}}
}
func planDigest(plan Plan) string {
	plan.ID, plan.Digest, plan.ExpiresAt = "", "", time.Time{}
	data, _ := json.Marshal(plan)
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}
func validNode(node Node) error {
	if node.ID == "" || node.Address == "" || node.User == "" || node.Port == 0 || node.CredentialRef == "" || node.HostKey.KnownHosts == "" || node.HostKey.Fingerprint == "" {
		return errors.New("invalid node")
	}
	return nil
}

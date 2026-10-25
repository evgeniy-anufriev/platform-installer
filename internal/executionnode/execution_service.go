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
	"slices"
	"strings"
	"sync"
	"time"

	"platform-installer/internal/artifactsource"
)

// ExecutionError is a semantic application error.  Transport diagnostics are
// deliberately not used as an API and are never needed to make lifecycle
// decisions.
type ExecutionError struct {
	Code          string
	RunID         string
	Findings      []Finding
	notDispatched bool
}

func (e *ExecutionError) StartWasNotDispatched() bool { return e.notDispatched }

// StartNotDispatchedError proves that Start returned before the credentialed
// StartExecution request was handed to the transport. Callers may safely
// release a local PENDING reservation; transport errors after dispatch remain
// ambiguous and are deliberately not wrapped in this type.
type StartNotDispatchedError struct{ cause error }

func (e *StartNotDispatchedError) Error() string             { return e.cause.Error() }
func (e *StartNotDispatchedError) Unwrap() error             { return e.cause }
func (*StartNotDispatchedError) StartWasNotDispatched() bool { return true }

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
	SkipApplicationLibraries   []string
	SkipInfrastructureVerify   bool
	ExecutionMode              ExecutionMode
	InfrastructureVerification *InfrastructureVerification
	ID                         string
	Status                     string
	ProjectIdentity            string
	ProjectRevision            string
	PlanFingerprint            string
	Acknowledgements           []string
	AcknowledgementDetails     []PlanAcknowledgement
	Phases                     []DeploymentPlanPhase
	RuntimeRelease             map[string]any
	ArtifactRequirements       []artifactsource.Requirement
	ApplicationImages          []ApplicationImageRequirement
	RequiredCredentials        []RequiredCredential
	Findings                   []Finding
	stagingID                  string
	executionManifestDigest    string
}

// RequiredCredential is the bounded public-plan requirement projection. It
// carries no runtime secret reference, lease identity, or secret material.
type RequiredCredential struct {
	RequirementRef string
	Purpose        string
	Hosts          []string
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
	ProgressSteps     []DeploymentProgressStep
}

type DeploymentProgressStep struct {
	ID      string `json:"id"`
	Summary string `json:"summary"`
}

// TargetHostKeyApproval is runtime-only operator approval for one exact
// Core-planned SSH endpoint. It never enters the portable project or plan.
type TargetHostKeyApproval struct {
	HostID    string `json:"hostId"`
	Address   string `json:"address"`
	Port      int    `json:"port"`
	KeyType   string `json:"keyType"`
	PublicKey string `json:"publicKey"`
}

type TargetHostTrustStager interface {
	StageTargetHostTrust(context.Context, Node, DeploymentPlan, []TargetHostKeyApproval) error
}

type TargetHostTrustProvider func(DeploymentPlan) ([]TargetHostKeyApproval, error)

type PlanRecord struct {
	SkipApplicationLibraries []string
	skipInfrastructureVerify bool
	mode                     ExecutionMode
	vaultSources             map[string]string
	ID                       string
	Plan                     DeploymentPlan
	DeploymentOrder          []string
	ApplicationLibraryOrder  []string
	CreatedAt                time.Time
	ExpiresAt                time.Time
	Approved                 bool
	Consumed                 bool
}

type PlanBuilder interface {
	BuildDeploymentPlan(context.Context, Node, string, map[string]any, []string) (DeploymentPlan, error)
}

type ModePlanBuilder interface {
	BuildDeploymentPlanForMode(context.Context, Node, string, map[string]any, []string, ExecutionMode, map[string]string, ...bool) (DeploymentPlan, error)
}

type OrderedLibraryModePlanBuilder interface {
	BuildDeploymentPlanForModeWithLibraryOrder(context.Context, Node, string, map[string]any, []string, []string, ExecutionMode, map[string]string, ...bool) (DeploymentPlan, error)
}

type ExecutionClient interface {
	StartExecution(context.Context, Node, ExecutionStartRequest) (ExecutionRun, error)
	GetExecution(context.Context, Node, string) (ExecutionRun, error)
	GetEvents(context.Context, Node, string, int, int) (ExecutionEventPage, error)
	CancelExecution(context.Context, Node, string) (ExecutionRun, error)
}

type CredentialedExecutionClient interface {
	ExecutionClient
	StartExecutionV2(context.Context, Node, ExecutionStartV2Request) (ExecutionStartV2Response, error)
	CredentialStartCapability(context.Context, Node) (CredentialStartCapability, error)
	PutRuntimeSecretLease(context.Context, Node, CredentialLeaseRequest, TargetCredentialLeasePayload, int) (CredentialLeaseResponse, error)
}

// TargetCredentialLeaseProvider exposes a credential only to the synchronous
// trusted Start flow. Its closure is deliberately private to Go; neither the
// Wails facade nor plan/session state receives the credential or lease id.
type TargetCredentialLeaseRequest struct {
	RequiresPKIStorePassword  bool
	RuntimeSecretRequirements []string
	RuntimeSecretInputs       []RuntimeSecretInputRequirement
}

type RuntimeSecretInputRequirement struct{ RequirementRef, Purpose string }

type TargetCredentialLeaseProvider func(TargetCredentialLeaseRequest, func(TargetCredentialLeasePayload) error) error

type pendingStart struct {
	attemptID string
	leaseID   string
}

// ServicePlanRequest contains only operator/project routing and approved
// bundle candidates. Artifact requirements are read from the fresh Core plan.
type ServicePlanRequest struct {
	Service          string
	Operation        string
	DeploymentOrder  []string
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
	startMu             sync.Mutex
	builder             PlanBuilder
	client              ExecutionClient
	now                 func() time.Time
	ttl                 time.Duration
	mu                  sync.Mutex
	plans               map[string]PlanRecord
	sessions            map[string]*session
	projects            map[string]string
	projectRoots        map[string]string
	serviceRequests     map[string]ServicePlanRequest
	probe               TargetRepositoryProbe
	projectionStager    RuntimeProjectionStager
	credentialProvider  TargetCredentialLeaseProvider
	targetTrustProvider TargetHostTrustProvider
	targetTrustStager   TargetHostTrustStager
	pendingStarts       map[string]pendingStart
}

func NewExecutionService(builder PlanBuilder, client ExecutionClient) *ExecutionService {
	return &ExecutionService{builder: builder, client: client, now: time.Now, ttl: time.Hour, plans: map[string]PlanRecord{}, sessions: map[string]*session{}, projects: map[string]string{}, projectRoots: map[string]string{}, serviceRequests: map[string]ServicePlanRequest{}, pendingStarts: map[string]pendingStart{}}
}

// ConfigureTargetCredentialLease installs the existing runtime-only
// credential seam. A nil provider selects the non-credentialed v2 path.
func (s *ExecutionService) ConfigureTargetCredentialLease(provider TargetCredentialLeaseProvider) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.credentialProvider = provider
}

func (s *ExecutionService) ConfigureTargetHostTrust(provider TargetHostTrustProvider, stager TargetHostTrustStager) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.targetTrustProvider, s.targetTrustStager = provider, stager
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
	record, err := s.CreatePlanWithOrder(ctx, node, projectRoot, runtimeRelease, request.DeploymentOrder)
	if err != nil {
		return PlanRecord{}, err
	}
	s.mu.Lock()
	s.serviceRequests[record.ID] = cloneServicePlanRequest(request)
	s.mu.Unlock()
	return record, nil
}

func (s *ExecutionService) CreatePlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (PlanRecord, error) {
	return s.CreatePlanWithOrder(ctx, node, projectRoot, runtimeRelease, nil)
}

func (s *ExecutionService) CreatePlanWithOrder(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, deploymentOrder []string) (PlanRecord, error) {
	return s.createPlan(ctx, node, projectRoot, runtimeRelease, deploymentOrder, nil, "", nil)
}

// Explicit modes share the ordinary approval/Start lifecycle. An older builder
// is never silently substituted for a mode-aware request.
func (s *ExecutionService) CreatePlanForMode(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, deploymentOrder []string, mode ExecutionMode, vaultSources map[string]string, skipInfrastructureVerify ...bool) (PlanRecord, error) {
	if !validModePlanInput(append([]string{}, deploymentOrder...), mode, vaultSources) {
		return PlanRecord{}, errors.New("DEPLOYMENT_PLAN_INPUT_INVALID")
	}
	return s.createPlan(ctx, node, projectRoot, runtimeRelease, deploymentOrder, nil, mode, vaultSources, skipInfrastructureVerify...)
}

func (s *ExecutionService) CreatePlanForModeWithLibraryOrder(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, deploymentOrder, libraryOrder []string, mode ExecutionMode, vaultSources map[string]string, skipInfrastructureVerify ...bool) (PlanRecord, error) {
	if libraryOrder == nil || !validModePlanInput(append([]string{}, deploymentOrder...), mode, vaultSources) {
		return PlanRecord{}, errors.New("DEPLOYMENT_PLAN_INPUT_INVALID")
	}
	return s.createPlan(ctx, node, projectRoot, runtimeRelease, deploymentOrder, libraryOrder, mode, vaultSources, skipInfrastructureVerify...)
}

func (s *ExecutionService) buildPlan(ctx context.Context, node Node, root string, release map[string]any, order, libraryOrder []string, mode ExecutionMode, sources map[string]string, skipInfrastructureVerify ...bool) (DeploymentPlan, error) {
	if mode == "" {
		if len(applicationLibrarySelection(ctx)) > 0 {
			return DeploymentPlan{}, errors.New("APPLICATION_LIBRARY_SELECTION_RUNTIME_UNSUPPORTED")
		}
		return s.builder.BuildDeploymentPlan(ctx, node, root, release, slices.Clone(order))
	}
	builder, ok := s.builder.(ModePlanBuilder)
	if !ok {
		return DeploymentPlan{}, errors.New("EXECUTION_MODE_RUNTIME_UNSUPPORTED")
	}
	var plan DeploymentPlan
	var err error
	if libraryOrder != nil {
		ordered, supported := s.builder.(OrderedLibraryModePlanBuilder)
		if !supported {
			return DeploymentPlan{}, errors.New("APPLICATION_LIBRARY_ORDER_RUNTIME_UNSUPPORTED")
		}
		plan, err = ordered.BuildDeploymentPlanForModeWithLibraryOrder(ctx, node, root, release, append([]string{}, order...), slices.Clone(libraryOrder), mode, cloneVaultSources(sources), skipInfrastructureVerify...)
	} else {
		plan, err = builder.BuildDeploymentPlanForMode(ctx, node, root, release, append([]string{}, order...), mode, cloneVaultSources(sources), skipInfrastructureVerify...)
	}
	if err == nil && (plan.ExecutionMode != mode || !sameLibrarySelection(plan.SkipApplicationLibraries, applicationLibrarySelection(ctx)) || plan.SkipInfrastructureVerify != (len(skipInfrastructureVerify) > 0 && skipInfrastructureVerify[0]) || plan.InfrastructureVerification == nil || !plan.InfrastructureVerification.Validate()) {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	return plan, err
}

func cloneVaultSources(source map[string]string) map[string]string {
	result := make(map[string]string, len(source))
	for key, value := range source {
		result[key] = value
	}
	return result
}

func (s *ExecutionService) createPlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any, deploymentOrder, libraryOrder []string, mode ExecutionMode, vaultSources map[string]string, skipInfrastructureVerify ...bool) (PlanRecord, error) {
	if s == nil || s.builder == nil || projectRoot == "" {
		return PlanRecord{}, errors.New("EXECUTION_PLAN_INPUT_INVALID")
	}
	plan, err := s.buildPlan(ctx, node, projectRoot, runtimeRelease, deploymentOrder, libraryOrder, mode, vaultSources, skipInfrastructureVerify...)
	if err != nil {
		return PlanRecord{}, err
	}
	if plan.ID == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" || (plan.Status != "EXECUTABLE" && plan.Status != "BLOCKED") || (plan.Status == "EXECUTABLE" && plan.ProjectIdentity == "") {
		return PlanRecord{}, errors.New("DEPLOYMENT_PLAN_INVALID")
	}
	now := s.now().UTC()
	record := PlanRecord{SkipApplicationLibraries: applicationLibrarySelection(ctx), skipInfrastructureVerify: len(skipInfrastructureVerify) > 0 && skipInfrastructureVerify[0], mode: mode, vaultSources: cloneVaultSources(vaultSources), ID: plan.ID, Plan: cloneDeploymentPlan(plan), DeploymentOrder: slices.Clone(deploymentOrder), ApplicationLibraryOrder: slices.Clone(libraryOrder), CreatedAt: now, ExpiresAt: now.Add(s.ttl)}
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

func (s *ExecutionService) start(ctx context.Context, node Node, planID string, prepare func(DeploymentPlan, ServicePlanRequest, string) error) (result ExecutionRun, resultErr error) {
	s.startMu.Lock()
	defer s.startMu.Unlock()
	startRequestDispatched := false
	defer func() {
		if resultErr != nil && !startRequestDispatched {
			var executionErr *ExecutionError
			if errors.As(resultErr, &executionErr) {
				copy := *executionErr
				copy.notDispatched = true
				resultErr = &copy
			} else {
				resultErr = &StartNotDispatchedError{cause: resultErr}
			}
		}
	}()
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
	prior := s.projects[record.Plan.ProjectIdentity]
	s.mu.Unlock()
	if prior != "" {
		// The local session is only a cache. A detached controller may have
		// become terminal since its last observer poll; only the authoritative
		// Execution Node may release this project's active-run guard.
		observed, observeErr := s.client.GetExecution(ctx, node, prior)
		if observeErr != nil {
			return ExecutionRun{}, observeErr
		}
		if observed.RunID != prior || observed.ProjectIdentity != record.Plan.ProjectIdentity {
			return ExecutionRun{}, &ExecutionError{Code: OwnershipMismatch, RunID: prior}
		}
		switch observed.State {
		case "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED":
			s.mu.Lock()
			if s.projects[record.Plan.ProjectIdentity] == prior {
				delete(s.projects, record.Plan.ProjectIdentity)
			}
			existing := s.sessions[prior]
			s.mu.Unlock()
			if existing != nil {
				existing.mu.Lock()
				existing.run = observed
				existing.mu.Unlock()
			}
		default:
			return ExecutionRun{}, &ExecutionError{Code: ActiveRunExists, RunID: prior}
		}
	}
	s.mu.Lock()
	projectRoot := s.projectRoots[planID]
	s.mu.Unlock()
	if projectRoot == "" {
		return ExecutionRun{}, errors.New("EXECUTION_PLAN_PROJECT_ROOT_MISSING")
	}
	if len(record.Plan.RuntimeRelease) == 0 {
		return ExecutionRun{}, errors.New("EXECUTION_PLAN_RUNTIME_RELEASE_MISSING")
	}
	fresh, err := s.buildPlan(WithApplicationLibrarySelection(ctx, record.SkipApplicationLibraries), node, projectRoot, record.Plan.RuntimeRelease, record.DeploymentOrder, record.ApplicationLibraryOrder, record.mode, record.vaultSources, record.skipInfrastructureVerify)
	if err != nil {
		return ExecutionRun{}, err
	}
	if fresh.Status != "EXECUTABLE" || fresh.ProjectIdentity != record.Plan.ProjectIdentity || fresh.ProjectRevision != record.Plan.ProjectRevision || fresh.PlanFingerprint != record.Plan.PlanFingerprint {
		s.invalidate(planID)
		return ExecutionRun{}, &ExecutionError{Code: PlanStale}
	}
	if fresh.stagingID == "" || fresh.executionManifestDigest == "" {
		return ExecutionRun{}, errors.New("EXECUTION_START_BINDING_MISSING")
	}
	s.mu.Lock()
	trustProvider, trustStager := s.targetTrustProvider, s.targetTrustStager
	s.mu.Unlock()
	if len(planTargetHostIDs(fresh)) > 0 {
		if trustProvider == nil || trustStager == nil {
			return ExecutionRun{}, errors.New("TARGET_HOST_TRUST_REQUIRED")
		}
		approvals, trustErr := trustProvider(fresh)
		if trustErr != nil {
			return ExecutionRun{}, trustErr
		}
		if trustErr = trustStager.StageTargetHostTrust(ctx, node, fresh, approvals); trustErr != nil {
			return ExecutionRun{}, trustErr
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
		if err := prepare(fresh, request, fresh.stagingID); err != nil {
			return ExecutionRun{}, err
		}
	}
	client, ok := s.client.(CredentialedExecutionClient)
	if !ok {
		return ExecutionRun{}, errors.New("EXECUTION_START_V2_UNSUPPORTED")
	}
	capability, err := client.CredentialStartCapability(ctx, node)
	if err != nil {
		return ExecutionRun{}, err
	}
	s.mu.Lock()
	pending, hasPending := s.pendingStarts[planID]
	provider := s.credentialProvider
	s.mu.Unlock()
	if !hasPending {
		requiresPKIStorePassword := planRequiresPKIStorePassword(fresh)
		runtimeSecretRequirements := planRuntimeSecretRequirements(fresh)
		typedRuntimeSecretRequirements := planRuntimeSecretInputRequirements(fresh)
		// The closed v4 payload carries pkiStorePassword too; v4 runtimes
		// deliberately advertise only v4, not the legacy payload versions.
		pkiPayloadSupported := capability.supportsPayloadVersion(credentialPayloadVersionV2) ||
			(capability.TypedRuntimeInputs && capability.supportsPayloadVersion(credentialPayloadVersionV4))
		if requiresPKIStorePassword && (!pkiPayloadSupported || capability.MaxPayloadBytes < 4096) {
			return ExecutionRun{}, errors.New("PKI_STORE_PASSWORD_RUNTIME_UNSUPPORTED")
		}
		if requiresPKIStorePassword && provider == nil {
			return ExecutionRun{}, errors.New("PKI_STORE_PASSWORD_UNAVAILABLE")
		}
		// v4 carries the same runtimeSecretValues object alongside typed inputs.
		// A v4-only runtime intentionally does not advertise legacy v3.
		runtimeValuesSupported := capability.supportsPayloadVersion(credentialPayloadVersionV3) ||
			(capability.TypedRuntimeInputs && capability.supportsPayloadVersion(credentialPayloadVersionV4))
		if len(runtimeSecretRequirements) > 0 && (!runtimeValuesSupported || provider == nil) {
			return ExecutionRun{}, errors.New("RUNTIME_SECRET_VALUES_UNAVAILABLE")
		}
		if len(typedRuntimeSecretRequirements) > 0 && (!capability.TypedRuntimeInputs || !capability.supportsPayloadVersion(credentialPayloadVersionV4) || provider == nil) {
			return ExecutionRun{}, errors.New("RUNTIME_SECRET_INPUTS_UNAVAILABLE")
		}
		attempt, err := newStartAttemptID()
		if err != nil {
			return ExecutionRun{}, err
		}
		pending = pendingStart{attemptID: attempt}
		if provider != nil {
			requestID, err := newStartAttemptID()
			if err != nil {
				return ExecutionRun{}, err
			}
			err = provider(TargetCredentialLeaseRequest{RequiresPKIStorePassword: requiresPKIStorePassword, RuntimeSecretRequirements: append([]string(nil), runtimeSecretRequirements...), RuntimeSecretInputs: append([]RuntimeSecretInputRequirement(nil), typedRuntimeSecretRequirements...)}, func(payload TargetCredentialLeasePayload) error {
				if requiresPKIStorePassword != (payload.PKIStorePassword != "") {
					return errors.New("PKI_STORE_PASSWORD_UNAVAILABLE")
				}
				if !sameRuntimeSecretRequirementSet(runtimeSecretRequirements, payload.RuntimeSecretValues) {
					return errors.New("RUNTIME_SECRET_VALUES_UNAVAILABLE")
				}
				if len(typedRuntimeSecretRequirements) > 0 && (!payload.UseTypedRuntimeInputs || !sameRuntimeSecretInputSet(typedRuntimeSecretRequirements, payload.RuntimeSecretInputs)) {
					return errors.New("RUNTIME_SECRET_INPUTS_UNAVAILABLE")
				}
				lease, leaseErr := client.PutRuntimeSecretLease(ctx, node, CredentialLeaseRequest{RequestID: requestID, StartAttemptID: attempt, ProjectIdentity: fresh.ProjectIdentity, ProjectRevision: fresh.ProjectRevision, PlanFingerprint: fresh.PlanFingerprint, ExecutionManifestDigest: fresh.executionManifestDigest, RuntimeRelease: fresh.RuntimeRelease}, payload, capability.MaxPayloadBytes)
				if leaseErr == nil {
					pending.leaseID = lease.LeaseID
				}
				return leaseErr
			})
			if err != nil {
				return ExecutionRun{}, err
			}
		}
		s.mu.Lock()
		s.pendingStarts[planID] = pending
		s.mu.Unlock()
	}
	// Set the boundary immediately before handing the request to the transport:
	// any error from this call may conceal a committed remote Start.
	startRequestDispatched = true
	response, err := client.StartExecutionV2(ctx, node, ExecutionStartV2Request{StartAttemptID: pending.attemptID, ProjectIdentity: fresh.ProjectIdentity, ProjectRevision: fresh.ProjectRevision, PlanFingerprint: fresh.PlanFingerprint, ExecutionManifestDigest: fresh.executionManifestDigest, RuntimeRelease: fresh.RuntimeRelease, LeaseID: pending.leaseID})
	if err != nil {
		return ExecutionRun{}, err
	}
	run := ExecutionRun{RunID: response.RunID, ProjectIdentity: fresh.ProjectIdentity, State: "STARTING"}
	s.mu.Lock()
	record.Consumed = true
	s.plans[planID] = record
	delete(s.pendingStarts, planID)
	if prior := s.projects[fresh.ProjectIdentity]; prior != "" && prior != run.RunID {
		s.mu.Unlock()
		return ExecutionRun{}, &ExecutionError{Code: ActiveRunExists, RunID: prior}
	}
	s.projects[fresh.ProjectIdentity] = run.RunID
	s.sessions[run.RunID] = &session{run: run, project: fresh.ProjectIdentity, lastSequence: run.Sequence, subs: map[uint64]*Subscription{}}
	s.mu.Unlock()
	return run, nil
}

func planTargetHostIDs(plan DeploymentPlan) []string {
	seen := make(map[string]bool)
	for _, phase := range plan.Phases {
		for _, action := range phase.Actions {
			for _, id := range action.Targets {
				seen[id] = true
			}
		}
	}
	result := make([]string, 0, len(seen))
	for id := range seen {
		result = append(result, id)
	}
	slices.Sort(result)
	return result
}

func planRequiresPKIStorePassword(plan DeploymentPlan) bool {
	for _, requirement := range plan.RequiredCredentials {
		if requirement.RequirementRef == "pki-store-password" && requirement.Purpose == "PKI_STORE_PASSWORD" {
			return true
		}
	}
	return false
}

func planRuntimeSecretRequirements(plan DeploymentPlan) []string {
	result := []string{}
	for _, requirement := range plan.RequiredCredentials {
		if RuntimeSecretValuePurpose(requirement.Purpose) && runtimeSecretRequirementPattern.MatchString(requirement.RequirementRef) {
			result = append(result, requirement.RequirementRef)
		}
	}
	slices.Sort(result)
	return result
}

// RuntimeSecretValuePurpose identifies values carried in the existing lease map.
func RuntimeSecretValuePurpose(purpose string) bool {
	return purpose == "SERVICE_PASSWORD" || purpose == "APPLICATION_SECRET" || purpose == "APPLICATION_VAULT_ADMIN_TOKEN" || purpose == "APPLICATION_REGISTRY_USERNAME" || purpose == "APPLICATION_REGISTRY_PASSWORD"
}

func planRuntimeSecretInputRequirements(plan DeploymentPlan) []RuntimeSecretInputRequirement {
	result := []RuntimeSecretInputRequirement{}
	for _, requirement := range plan.RequiredCredentials {
		if requirement.Purpose == "SERVICE_ADMIN_TOKEN" || requirement.Purpose == "SERVICE_UNSEAL_SHARES" {
			result = append(result, RuntimeSecretInputRequirement{RequirementRef: requirement.RequirementRef, Purpose: requirement.Purpose})
		}
	}
	slices.SortFunc(result, func(a, b RuntimeSecretInputRequirement) int {
		return strings.Compare(a.RequirementRef, b.RequirementRef)
	})
	return result
}

func sameRuntimeSecretInputSet(required []RuntimeSecretInputRequirement, values []RuntimeSecretInputPayload) bool {
	allowed := make(map[string]string, len(required))
	for _, item := range required {
		allowed[item.RequirementRef] = item.Purpose
	}
	seen := map[string]bool{}
	for _, item := range values {
		if seen[item.RequirementRef] || allowed[item.RequirementRef] != item.Purpose {
			return false
		}
		seen[item.RequirementRef] = true
	}
	return true
}

func sameRuntimeSecretRequirementSet(required []string, values map[string]string) bool {
	if len(required) == 0 {
		return values == nil
	}
	if len(required) != len(values) {
		return false
	}
	for _, reference := range required {
		if _, ok := values[reference]; !ok {
			return false
		}
	}
	return true
}

func (s *ExecutionService) invalidate(id string) {
	s.mu.Lock()
	if p, ok := s.plans[id]; ok {
		p.Approved = false
		p.Consumed = true
		s.plans[id] = p
	}
	delete(s.pendingStarts, id)
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
	p.SkipApplicationLibraries = slices.Clone(p.SkipApplicationLibraries)
	if p.InfrastructureVerification != nil {
		value := *p.InfrastructureVerification
		value.Deployments = append([]InfrastructureDeploymentVerification{}, value.Deployments...)
		if value.Code != nil {
			v := *value.Code
			value.Code = &v
		}
		if value.InfrastructureFingerprint != nil {
			v := *value.InfrastructureFingerprint
			value.InfrastructureFingerprint = &v
		}
		if value.EvidenceRevision != nil {
			v := *value.EvidenceRevision
			value.EvidenceRevision = &v
		}
		p.InfrastructureVerification = &value
	}
	p.Acknowledgements = append([]string(nil), p.Acknowledgements...)
	p.AcknowledgementDetails = append([]PlanAcknowledgement(nil), p.AcknowledgementDetails...)
	p.Phases = clonePlanPhases(p.Phases)
	p.ArtifactRequirements = append([]artifactsource.Requirement(nil), p.ArtifactRequirements...)
	p.RequiredCredentials = cloneRequiredCredentials(p.RequiredCredentials)
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

func cloneRequiredCredentials(values []RequiredCredential) []RequiredCredential {
	result := make([]RequiredCredential, len(values))
	for index, value := range values {
		result[index] = value
		result[index].Hosts = append([]string(nil), value.Hosts...)
	}
	return result
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
			result[index].Actions[actionIndex].ProgressSteps = append([]DeploymentProgressStep(nil), action.ProgressSteps...)
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
func clonePlanRecord(p PlanRecord) PlanRecord {
	p.SkipApplicationLibraries = slices.Clone(p.SkipApplicationLibraries)
	p.Plan = cloneDeploymentPlan(p.Plan)
	p.vaultSources = cloneVaultSources(p.vaultSources)
	p.DeploymentOrder = slices.Clone(p.DeploymentOrder)
	p.ApplicationLibraryOrder = slices.Clone(p.ApplicationLibraryOrder)
	return p
}
func newRunID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return "installer-" + new(big.Int).SetBytes(value).String(), nil
}

func newStartAttemptID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

// NewRequestID returns one opaque bounded id for a request-owned remote
// staging operation. It has no run identity semantics.
func NewRequestID() (string, error) { return newStartAttemptID() }

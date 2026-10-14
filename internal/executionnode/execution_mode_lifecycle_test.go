package executionnode

import (
	"context"
	"errors"
	"strings"
	"testing"
)

type modeLifecycleBuilder struct {
	lifecycleBuilder
	modes                               []ExecutionMode
	sources                             []map[string]string
	wrongMode, blocked, missingEvidence bool
}

func (b *modeLifecycleBuilder) BuildDeploymentPlanForMode(ctx context.Context, n Node, root string, release map[string]any, order []string, mode ExecutionMode, sources map[string]string) (DeploymentPlan, error) {
	b.modes = append(b.modes, mode)
	b.sources = append(b.sources, cloneVaultSources(sources))
	p, err := b.lifecycleBuilder.BuildDeploymentPlan(ctx, n, root, release, order)
	p.ExecutionMode = mode
	p.InfrastructureVerification = &InfrastructureVerification{Status: "PASS", Deployments: []InfrastructureDeploymentVerification{}}
	if b.wrongMode {
		p.ExecutionMode = FullProject
	}
	if b.blocked && b.calls > 1 {
		p.Status = "BLOCKED"
	}
	if b.missingEvidence {
		p.InfrastructureVerification = nil
	}
	return p, err
}
func TestB3ModeLifecycleRebuildsExactRequestAndDoesNotShareObservation(t *testing.T) {
	for _, mode := range []ExecutionMode{FullProject, ApplicationLibrariesOnly, InfrastructureVerifyOnly} {
		t.Run(string(mode), func(t *testing.T) {
			b := &modeLifecycleBuilder{}
			c := &lifecycleClient{}
			s := NewExecutionService(b, c)
			sources := map[string]string{"vault-main": "RUNTIME_INPUT"}
			p, err := s.CreatePlanForMode(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"}, []string{"vault-main"}, mode, sources)
			if err != nil {
				t.Fatal(err)
			}
			sources["vault-main"] = "CURRENT_RUN_BOOTSTRAP"
			p.Plan.InfrastructureVerification.Status = "BLOCKED"
			stored, _ := s.GetPlan(p.ID)
			if stored.Plan.InfrastructureVerification.Status != "PASS" {
				t.Fatal("observation alias")
			}
			if err = s.ApprovePlan(p.ID, []string{"ACK_RISK"}); err != nil {
				t.Fatal(err)
			}
			if _, err = s.Start(context.Background(), Node{}, p.ID); err != nil {
				t.Fatal(err)
			}
			if len(b.modes) != 2 || b.modes[1] != mode || b.sources[1]["vault-main"] != "RUNTIME_INPUT" {
				t.Fatal("fresh Build lost mode/source binding")
			}
			if c.starts != 1 {
				t.Fatal("duplicate Start")
			}
			if _, err = s.Start(context.Background(), Node{}, p.ID); err == nil {
				t.Fatal("approval reused")
			}
		})
	}
}
func TestB3ModeLifecycleRejectsStaleBlockedAndUnsupportedBeforeStart(t *testing.T) {
	for _, failure := range []string{"fingerprint", "blocked", "mode", "evidence"} {
		t.Run(failure, func(t *testing.T) {
			b := &modeLifecycleBuilder{}
			c := &lifecycleClient{}
			s := NewExecutionService(b, c)
			p, err := s.CreatePlanForMode(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"}, nil, ApplicationLibrariesOnly, nil)
			if err != nil {
				t.Fatal(err)
			}
			if err = s.ApprovePlan(p.ID, []string{"ACK_RISK"}); err != nil {
				t.Fatal(err)
			}
			b.stale = failure == "fingerprint"
			b.blocked = failure == "blocked"
			b.wrongMode = failure == "mode"
			b.missingEvidence = failure == "evidence"
			if _, err = s.Start(context.Background(), Node{}, p.ID); err == nil {
				t.Fatal("stale/invalid fresh plan admitted")
			}
			if c.starts != 0 || len(c.ops) != 0 {
				t.Fatal("failure dispatched lease/Start")
			}
		})
	}
	b := &lifecycleBuilder{}
	s := NewExecutionService(b, &lifecycleClient{})
	if _, err := s.CreatePlanForMode(context.Background(), Node{}, "project", map[string]any{}, nil, ApplicationLibrariesOnly, nil); err == nil || !strings.Contains(err.Error(), "UNSUPPORTED") {
		t.Fatal(err)
	}
	if b.calls != 0 {
		t.Fatal("fell back to full Build")
	}
}
func TestB3ModeUnknownStartRetainsAttemptAndCancelUsesSameService(t *testing.T) {
	b := &modeLifecycleBuilder{}
	c := &lifecycleClient{startErr: errors.New("lost response")}
	s := NewExecutionService(b, c)
	p, err := s.CreatePlanForMode(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"}, nil, ApplicationLibrariesOnly, nil)
	if err != nil {
		t.Fatal(err)
	}
	if err = s.ApprovePlan(p.ID, []string{"ACK_RISK"}); err != nil {
		t.Fatal(err)
	}
	if _, err = s.Start(context.Background(), Node{}, p.ID); err == nil {
		t.Fatal("lost response ignored")
	}
	c.startErr = nil
	run, err := s.Start(context.Background(), Node{}, p.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(c.requests) != 2 || c.requests[0].StartAttemptID != c.requests[1].StartAttemptID {
		t.Fatal("new attempt after uncertain Start")
	}
	if _, err = s.Cancel(context.Background(), Node{}, run.RunID); err != nil || c.cancels != 1 {
		t.Fatalf("cancel: %v", err)
	}
}

type modeTrustStager struct{ calls int }

func (s *modeTrustStager) StageTargetHostTrust(_ context.Context, _ Node, p DeploymentPlan, keys []TargetHostKeyApproval) error {
	s.calls++
	if p.ExecutionMode != ApplicationLibrariesOnly || len(keys) != 1 {
		return errors.New("wrong trust scope")
	}
	return nil
}
func TestB3ModeUsesOrdinaryTargetTrustAndTypedLease(t *testing.T) {
	b := &modeLifecycleBuilder{lifecycleBuilder: lifecycleBuilder{targets: []string{"node1"}, typedInputs: true}}
	c := &lifecycleClient{typedCapability: true}
	s := NewExecutionService(b, c)
	p, err := s.CreatePlanForMode(context.Background(), Node{}, "project", map[string]any{"bundleDigest": "sha256:x"}, nil, ApplicationLibrariesOnly, nil)
	if err != nil {
		t.Fatal(err)
	}
	if err = s.ApprovePlan(p.ID, []string{"ACK_RISK"}); err != nil {
		t.Fatal(err)
	}
	if _, err = s.Start(context.Background(), Node{}, p.ID); err == nil || err.Error() != "TARGET_HOST_TRUST_REQUIRED" {
		t.Fatal(err)
	}
	if len(c.ops) != 0 {
		t.Fatal("lease issued before target trust")
	}
	stager := &modeTrustStager{}
	s.ConfigureTargetHostTrust(func(p DeploymentPlan) ([]TargetHostKeyApproval, error) {
		return []TargetHostKeyApproval{{HostID: "node1"}}, nil
	}, stager)
	s.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if len(request.RuntimeSecretInputs) != 1 || request.RuntimeSecretInputs[0].Purpose != "SERVICE_ADMIN_TOKEN" {
			t.Fatal("typed requirement changed")
		}
		return use(TargetCredentialLeasePayload{Username: "operator", Password: "synthetic-transport", UseTypedRuntimeInputs: true})
	})
	if _, err = s.Start(context.Background(), Node{}, p.ID); err != nil {
		t.Fatal(err)
	}
	if stager.calls != 1 || strings.Join(c.ops, ",") != "put-lease,start-v2" || c.requests[0].LeaseID == "" {
		t.Fatal("trust/lease/Start order lost")
	}
}

package executionnode

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/executionbundle"
)

// This opt-in acceptance exercises the generic UI-02 lifecycle, not the
// StartService compatibility path. Its fixture keeps all three Kafka members
// on the one explicitly selected QA target and uses an isolated namespace.
func TestUI02EProductionSingleHostKafkaLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_UI02E_E2E") != "1" {
		t.Skip("set PLATFORM_UI02E_E2E=1 for UI-02E production-shaped Kafka acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	project := os.Getenv("PLATFORM_UI02E_PROJECT")
	targetUser := os.Getenv("PLATFORM_UI02E_TARGET_USER")
	targetPassword := os.Getenv("PLATFORM_UI02E_TARGET_PASSWORD")
	targetSudoPassword := os.Getenv("PLATFORM_UI02E_TARGET_SUDO_PASSWORD")
	pkiStorePassword := os.Getenv("PLATFORM_UI02E_PKI_STORE_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || project == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" {
		t.Fatal("UI02E_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_UI02E_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	node := Node{ID: "ui02e-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if request.RequiresPKIStorePassword && pkiStorePassword == "" {
			return os.ErrNotExist
		}
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword, PKIStorePassword: pkiStorePassword})
	})
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	ctx, cancel := context.WithTimeout(context.Background(), 35*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		started := time.Now()
		record, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("cycle=%d plan: %v", cycle, err)
		}
		if record.Plan.Status != "EXECUTABLE" || record.Plan.ProjectIdentity != "ui02e-singlehost" || len(record.Plan.Phases) < 2 {
			t.Fatalf("cycle=%d unexpected plan: %#v", cycle, record.Plan)
		}
		if err := service.ApprovePlan(record.ID, record.Plan.Acknowledgements); err != nil {
			t.Fatalf("cycle=%d approve: %v", cycle, err)
		}
		run, err := service.Start(ctx, node, record.ID)
		if err != nil {
			t.Fatalf("cycle=%d start: %v", cycle, err)
		}
		observer, err := NewRunObserver(transport, filepath.Join(repo, ".runtime"))
		if err != nil {
			t.Fatal(err)
		}
		subscription, err := observer.Observe(ctx, node, run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		for subscription.Events != nil || subscription.Errors != nil {
			select {
			case _, ok := <-subscription.Events:
				if !ok {
					subscription.Events = nil
				}
			case observeErr, ok := <-subscription.Errors:
				if !ok {
					subscription.Errors = nil
				} else {
					t.Fatalf("cycle=%d observer: %v", cycle, observeErr)
				}
			case <-ctx.Done():
				t.Fatalf("cycle=%d timeout", cycle)
			}
		}
		// Keep the ExecutionService registry authoritative for the next Start.
		// The observer provides presentation/replay evidence, while Sync consumes
		// the same terminal result into the service lifecycle that enforces one
		// active run per project.
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		if len(events) == 0 {
			t.Fatalf("cycle=%d no lifecycle events", cycle)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "apply:ui02e-kafka" {
				apply = true
			}
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "verify:ui02e-kafka" {
				verify = true
			}
			if event.EventType == "TASK_COMPLETED" && event.Status == "CHANGED" {
				changed++
			}
		}
		if !apply || !verify {
			t.Fatalf("cycle=%d missing apply/verify success: apply=%t verify=%t", cycle, apply, verify)
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("repeat apply changed=%d", changed)
		}
		mirror, mirrorErr := EventMirrorPath(filepath.Join(repo, ".runtime"), run.RunID)
		if mirrorErr != nil {
			t.Fatal(mirrorErr)
		}
		info, statErr := os.Stat(mirror)
		if statErr != nil || info.Size() == 0 {
			t.Fatalf("cycle=%d mirror=%q stat=%v", cycle, mirror, statErr)
		}
		t.Logf("cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d mirror=%s", cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed, strings.ReplaceAll(mirror, "\\", "/"))
	}
}

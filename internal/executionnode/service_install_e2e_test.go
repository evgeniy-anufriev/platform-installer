package executionnode

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

// TestServiceInstall01KeepalivedLifecycle is an opt-in, production-shaped
// SERVICE-INSTALL-01 acceptance. It creates the first saved revision of the
// runtime-only cumulative QA project; later service-install milestones must
// open and extend that same project. It proves a fresh plan installs this
// isolated Keepalived deployment and a second fresh plan is idempotent.
func TestServiceInstall01KeepalivedLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_01_E2E") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_01_E2E=1 for SERVICE-INSTALL-01 Keepalived acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	targetUser := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_USER")
	targetPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_PASSWORD")
	targetSudoPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_SUDO_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" {
		t.Fatal("SERVICE_INSTALL_01_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_SERVICE_INSTALL_01_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	project, projectIdentity := configureKeepalivedProjectThroughGo(t, repo, bundle, cumulativeProjectRoot(t, repo))
	node := Node{ID: "service-install-01-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword})
	})
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		started := time.Now()
		record, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("cycle=%d plan: %v", cycle, err)
		}
		if record.Plan.Status != "EXECUTABLE" || record.Plan.ProjectIdentity != projectIdentity {
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
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "apply:service-install-01-keepalived" {
				apply = true
			}
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "verify:service-install-01-keepalived" {
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
		mirror, err := EventMirrorPath(filepath.Join(repo, ".runtime"), run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		info, err := os.Stat(mirror)
		if err != nil || info.Size() == 0 {
			t.Fatalf("cycle=%d mirror=%q stat=%v", cycle, mirror, err)
		}
		t.Logf("cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d mirror=%s", cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed, strings.ReplaceAll(mirror, "\\", "/"))
	}
}

// TestServiceInstall02BindLifecycle is an opt-in, production-shaped cumulative
// acceptance. It extends the UI-created project already accepted by
// SERVICE-INSTALL-01 through the production Go edit/session/review/Save seam,
// then proves BIND apply/verify and a fresh zero-change repeat cycle.
func TestServiceInstall02BindLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_02_E2E") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_02_E2E=1 for SERVICE-INSTALL-02 BIND acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	targetUser := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_USER")
	targetPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_PASSWORD")
	targetSudoPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_SUDO_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" {
		t.Fatal("SERVICE_INSTALL_02_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_SERVICE_INSTALL_01_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	project, projectIdentity := configureBindProjectThroughGo(t, repo, bundle, cumulativeProjectRoot(t, repo))
	node := Node{ID: "service-install-02-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword})
	})
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		started := time.Now()
		record, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("cycle=%d plan: %v", cycle, err)
		}
		if record.Plan.Status != "EXECUTABLE" || record.Plan.ProjectIdentity != projectIdentity {
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
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "apply:service-install-02-bind" {
				apply = true
			}
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "verify:service-install-02-bind" {
				verify = true
			}
			if event.EventType == "TASK_COMPLETED" && event.Status == "CHANGED" {
				changed++
			}
		}
		if !apply || !verify {
			t.Fatalf("cycle=%d missing BIND apply/verify success: apply=%t verify=%t", cycle, apply, verify)
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("repeat apply changed=%d", changed)
		}
		mirror, err := EventMirrorPath(filepath.Join(repo, ".runtime"), run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		if info, err := os.Stat(mirror); err != nil || info.Size() == 0 {
			t.Fatalf("cycle=%d mirror=%q stat=%v", cycle, mirror, err)
		}
		t.Logf("cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d mirror=%s", cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed, strings.ReplaceAll(mirror, "\\", "/"))
	}
}

// TestServiceInstall03DNSClientLifecycle is an opt-in, production-shaped
// cumulative acceptance. It adds the host-scoped DNS client through the same
// typed Go session/review/Save seam, references the already accepted BIND
// deployment, and proves two fresh plan lifecycle runs are idempotent.
func TestServiceInstall03DNSClientLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_03_E2E") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_03_E2E=1 for SERVICE-INSTALL-03 dns-client acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	targetUser := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_USER")
	targetPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_PASSWORD")
	targetSudoPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_SUDO_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" {
		t.Fatal("SERVICE_INSTALL_03_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_SERVICE_INSTALL_01_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	project, projectIdentity := configureDNSClientProjectThroughGo(t, repo, bundle, cumulativeProjectRoot(t, repo))
	node := Node{ID: "service-install-03-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(_ TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword})
	})
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		started := time.Now()
		record, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("cycle=%d plan: %v", cycle, err)
		}
		if record.Plan.Status != "EXECUTABLE" || record.Plan.ProjectIdentity != projectIdentity {
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
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "apply:service-install-03-dns-client" {
				apply = true
			}
			if event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "verify:service-install-03-dns-client" {
				verify = true
			}
			if event.EventType == "TASK_COMPLETED" && event.Status == "CHANGED" {
				changed++
			}
		}
		if !apply || !verify {
			t.Fatalf("cycle=%d missing dns-client apply/verify success: apply=%t verify=%t", cycle, apply, verify)
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("repeat apply changed=%d", changed)
		}
		mirror, err := EventMirrorPath(filepath.Join(repo, ".runtime"), run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		if info, err := os.Stat(mirror); err != nil || info.Size() == 0 {
			t.Fatalf("cycle=%d mirror=%q stat=%v", cycle, mirror, err)
		}
		t.Logf("cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d mirror=%s", cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed, strings.ReplaceAll(mirror, "\\", "/"))
	}
}

// TestServiceInstall04HAProxyLifecycle proves the next cumulative service uses
// the ordinary credentialed Start path for its PKI requirement and remains
// idempotent after all previously accepted network services are present.
func TestServiceInstall04HAProxyLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_04_E2E") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_04_E2E=1 for SERVICE-INSTALL-04 HAProxy acceptance")
	}
	address, user, identity, knownHosts := os.Getenv("PLATFORM_EXEC01A_ADDRESS"), os.Getenv("PLATFORM_EXEC01A_USER"), os.Getenv("PLATFORM_EXEC01A_IDENTITY"), os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	targetUser, targetPassword, targetSudoPassword, pkiStorePassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_USER"), os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_SUDO_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_PKI_STORE_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" || pkiStorePassword == "" {
		t.Fatal("SERVICE_INSTALL_04_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_SERVICE_INSTALL_01_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	project, projectIdentity := configureHAProxyProjectThroughGo(t, repo, bundle, cumulativeProjectRoot(t, repo))
	node := Node{ID: "service-install-04-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if request.RequiresPKIStorePassword != true {
			return os.ErrInvalid
		}
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword, PKIStorePassword: pkiStorePassword})
	})
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		started := time.Now()
		record, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("cycle=%d plan: %v", cycle, err)
		}
		if record.Plan.Status != "EXECUTABLE" || record.Plan.ProjectIdentity != projectIdentity {
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
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			apply = apply || (event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "apply:service-install-04-haproxy")
			verify = verify || (event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && event.ActionID == "verify:service-install-04-haproxy")
			if event.EventType == "TASK_COMPLETED" && event.Status == "CHANGED" {
				changed++
			}
		}
		if !apply || !verify {
			t.Fatalf("cycle=%d missing HAProxy apply/verify success: apply=%t verify=%t", cycle, apply, verify)
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("repeat apply changed=%d", changed)
		}
		mirror, err := EventMirrorPath(filepath.Join(repo, ".runtime"), run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		if info, err := os.Stat(mirror); err != nil || info.Size() == 0 {
			t.Fatalf("cycle=%d mirror=%q stat=%v", cycle, mirror, err)
		}
		t.Logf("cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d mirror=%s", cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed, strings.ReplaceAll(mirror, "\\", "/"))
	}
}

// TestServiceInstall01PrepareCumulativeProject materializes only the first
// service's canonical Core/Ansible inputs. It deliberately has no Execution
// Node, credential, plan or target-contact path, so Wails can reopen the
// resulting managed project before lifecycle acceptance starts.
func TestServiceInstall01PrepareCumulativeProject(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_01_PREPARE") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_01_PREPARE=1 to prepare the cumulative QA project")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cacheRoot := os.Getenv("PLATFORM_SERVICE_INSTALL_01_BUNDLE_CACHE")
	if cacheRoot == "" {
		cacheRoot = filepath.Join(repo, "bundle")
	}
	bundle, err := (executionbundle.Cache{Root: cacheRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	project, projectID := configureKeepalivedProjectThroughGo(t, repo, bundle, cumulativeProjectRoot(t, repo))
	t.Logf("prepared cumulative project=%s projectId=%s", filepath.ToSlash(project), projectID)
}

// createKeepalivedProjectThroughGo creates the entire acceptance topology through
// the production local project/session/review/Save lifecycle. It deliberately
// does not hand-author inventory, host_vars, group_vars, or service desired state.
func cumulativeProjectRoot(t *testing.T, repository string) string {
	t.Helper()
	root := os.Getenv("PLATFORM_SERVICE_INSTALL_CUMULATIVE_PROJECT")
	if root == "" {
		root = filepath.Join(repository, ".runtime", "qa", "service-install-cumulative-project")
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		t.Fatal(err)
	}
	if info, err := os.Stat(abs); err != nil || !info.IsDir() {
		t.Fatal("SERVICE_INSTALL_CUMULATIVE_PROJECT_INVALID")
	}
	return abs
}

// configureKeepalivedProjectThroughGo continues the empty managed project
// created through the public Wails flow. It configures its first service only
// through the production typed Go edit/session/review/Save lifecycle.
func configureKeepalivedProjectThroughGo(t *testing.T, repository string, bundle executionbundle.Verified, root string) (string, string) {
	t.Helper()
	config, err := appconfig.Load(filepath.Join(repository, "config", "application.yml"))
	if err != nil {
		t.Fatal(err)
	}
	serverTypes := make([]string, len(config.ServerTypes))
	for index, serverType := range config.ServerTypes {
		serverTypes[index] = serverType.ID
	}
	lifecycle := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle.Root})
	opened, err := lifecycle.OpenProject(t.Context(), root)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" || opened.Classification != projectlifecycle.ClassificationEmpty {
		if err == nil && opened.Project != nil && opened.Classification == projectlifecycle.ClassificationManaged {
			view, viewErr := installer.ReadManagedProjectView(opened.Root)
			if viewErr == nil {
				if deployment, ok := view.Deployments["service-install-01-keepalived"]; len(view.Servers) == 3 && len(view.Deployments) == 1 && ok && deployment.DeploymentID == "service-install-01-keepalived" {
					return opened.Root, opened.Project.ID
				}
			}
		}
		t.Fatalf("open cumulative project=%#v err=%v", opened, err)
	}
	revision, err := installer.ProjectRevision(opened.Root)
	if err != nil {
		t.Fatal(err)
	}
	backend := installer.NewBackend(nil,
		installer.WithServerTypes(serverTypes),
		installer.WithProjectCatalogResolver(func(ctx context.Context, root string) (*projectlifecycle.ProjectCatalogView, error) {
			return lifecycle.ResolveProjectCatalog(ctx, root)
		}),
	)
	sessions := installer.NewEditSessionStore()
	session, err := sessions.Start(opened.Project.ID, opened.Root, opened.Classification, revision)
	if err != nil {
		t.Fatal(err)
	}
	commands := []installer.EditCommand{
		{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1", Address: "192.168.56.101"},
		{Operation: "CreateServer", HostID: "node2", ServerType: "infra", DesiredHostname: "node2", Address: "192.168.56.102"},
		{Operation: "CreateServer", HostID: "node3", ServerType: "infra", DesiredHostname: "node3", Address: "192.168.56.103"},
		{Operation: "CreateServiceDeployment", DeploymentID: "service-install-01-keepalived", ServiceType: "keepalived", Mode: "vrrp-unicast"},
		{Operation: "CreateEndpointGroup", EndpointGroupID: "service-install-01", EndpointGroup: map[string]any{"address": map[string]any{"domain": "service-install-01.scada.local", "wildcard": true}}},
		{Operation: "ReconcileHostScopedDeploymentPlacement", DeploymentID: "service-install-01-keepalived", Hosts: []installer.PlacementHost{{HostID: "node1", Priority: 150}, {HostID: "node2", Priority: 120}, {HostID: "node3", Priority: 100}}},
		{Operation: "ReconcileEndpointProvider", DeploymentID: "service-install-01-keepalived", EndpointGroupID: "service-install-01", VirtualRouterID: 61, VirtualAddresses: []installer.VirtualAddress{{Address: "192.168.56.121", Interface: "enp0s8"}}},
	}
	for _, command := range commands {
		if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
			t.Fatalf("append %s: %v", command.Operation, err)
		}
	}
	plan, err := sessions.ReviewStructural(t.Context(), backend, session.SessionID)
	if err != nil || plan == nil || !plan.SaveAllowed {
		t.Fatalf("review=%#v err=%v", plan, err)
	}
	if _, err := sessions.BeginCommit(session.SessionID, plan.PlanID); err != nil {
		t.Fatal(err)
	}
	committed := backend.CommitStructuralSave(t.Context(), plan.PlanID)
	if committed.Status != "COMMITTED" || !committed.Changed || committed.Managed == nil || !sessions.FinishCommit(session.SessionID, plan.PlanID, true) {
		t.Fatalf("commit=%#v", committed)
	}
	reopened, err := installer.ReadManagedProjectView(opened.Root)
	if err != nil || len(reopened.Servers) != 3 || len(reopened.HostPlacements) != 3 || len(reopened.Deployments) != 1 {
		t.Fatalf("reopen=%#v err=%v", reopened, err)
	}
	priorities := []int{150, 120, 100}
	for index, placement := range reopened.HostPlacements {
		if placement.Priority == nil || *placement.Priority != priorities[index] {
			t.Fatalf("placement[%d]=%#v", index, placement)
		}
	}
	return opened.Root, opened.Project.ID
}

// configureBindProjectThroughGo adds exactly one BIND deployment to the
// existing cumulative project. BIND is host-scoped: node1 is primary and
// node2/node3 are secondaries, so no synthetic member identifiers are used.
func configureBindProjectThroughGo(t *testing.T, repository string, bundle executionbundle.Verified, root string) (string, string) {
	t.Helper()
	config, err := appconfig.Load(filepath.Join(repository, "config", "application.yml"))
	if err != nil {
		t.Fatal(err)
	}
	serverTypes := make([]string, len(config.ServerTypes))
	for index, serverType := range config.ServerTypes {
		serverTypes[index] = serverType.ID
	}
	lifecycle := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle.Root})
	opened, err := lifecycle.OpenProject(t.Context(), root)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" || opened.Classification != projectlifecycle.ClassificationManaged {
		t.Fatalf("open cumulative project=%#v err=%v", opened, err)
	}
	view, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	if deployment, exists := view.Deployments["service-install-02-bind"]; exists {
		if len(view.Servers) != 3 || len(view.Deployments) != 2 || deployment.ServiceType != "bind" || deployment.Mode != "authoritative-primary-secondary" || len(view.HostPlacements) != 6 {
			t.Fatalf("existing cumulative BIND state=%#v", view)
		}
		return opened.Root, opened.Project.ID
	}
	if len(view.Servers) != 3 || len(view.Deployments) != 1 || view.Deployments["service-install-01-keepalived"].ServiceType != "keepalived" {
		t.Fatalf("unexpected cumulative base=%#v", view)
	}
	revision, err := installer.ProjectRevision(opened.Root)
	if err != nil {
		t.Fatal(err)
	}
	backend := installer.NewBackend(nil,
		installer.WithServerTypes(serverTypes),
		installer.WithProjectCatalogResolver(func(ctx context.Context, projectRoot string) (*projectlifecycle.ProjectCatalogView, error) {
			return lifecycle.ResolveProjectCatalog(ctx, projectRoot)
		}),
	)
	sessions := installer.NewEditSessionStore()
	session, err := sessions.Start(opened.Project.ID, opened.Root, opened.Classification, revision)
	if err != nil {
		t.Fatal(err)
	}
	commands := []installer.EditCommand{
		{Operation: "CreateServiceDeployment", DeploymentID: "service-install-02-bind", ServiceType: "bind", Mode: "authoritative-primary-secondary"},
		{Operation: "ReconcileHostScopedDeploymentPlacement", DeploymentID: "service-install-02-bind", Hosts: []installer.PlacementHost{{HostID: "node1", Roles: []string{"primary"}, Priority: 150}, {HostID: "node2", Roles: []string{"secondary"}, Priority: 120}, {HostID: "node3", Roles: []string{"secondary"}, Priority: 100}}},
		{Operation: "SetServiceConfigurationValue", DeploymentID: "service-install-02-bind", Scope: "DEPLOYMENT", Setting: "zone", Value: "scada.local"},
		{Operation: "SetServiceConfigurationValue", DeploymentID: "service-install-02-bind", Scope: "DEPLOYMENT", Setting: "defaultTtl", Value: 300},
	}
	for _, command := range commands {
		if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
			t.Fatalf("append %s: %v", command.Operation, err)
		}
	}
	plan, err := sessions.ReviewStructural(t.Context(), backend, session.SessionID)
	if err != nil || plan == nil || !plan.SaveAllowed {
		if plan != nil && plan.Finding != nil {
			t.Fatalf("review finding=%s field=%s message=%s err=%v", plan.Finding.Code, plan.Finding.Field, plan.Finding.SafeMessage, err)
		}
		t.Fatalf("review=%#v err=%v", plan, err)
	}
	if _, err := sessions.BeginCommit(session.SessionID, plan.PlanID); err != nil {
		t.Fatal(err)
	}
	committed := backend.CommitStructuralSave(t.Context(), plan.PlanID)
	if committed.Status != "COMMITTED" || !committed.Changed || committed.Managed == nil || !sessions.FinishCommit(session.SessionID, plan.PlanID, true) {
		t.Fatalf("commit=%#v", committed)
	}
	reopened, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	deployment, exists := reopened.Deployments["service-install-02-bind"]
	if !exists || len(reopened.Servers) != 3 || len(reopened.Deployments) != 2 || len(reopened.HostPlacements) != 6 || deployment.ServiceType != "bind" || deployment.Mode != "authoritative-primary-secondary" || len(deployment.Configuration) != 2 {
		t.Fatalf("reopen=%#v", reopened)
	}
	return opened.Root, opened.Project.ID
}

// configureDNSClientProjectThroughGo adds the one host-scoped DNS client
// deployment to the existing cumulative project. The service reference is a
// typed configuration intent; it does not parse or mutate Ansible files.
func configureDNSClientProjectThroughGo(t *testing.T, repository string, bundle executionbundle.Verified, root string) (string, string) {
	t.Helper()
	config, err := appconfig.Load(filepath.Join(repository, "config", "application.yml"))
	if err != nil {
		t.Fatal(err)
	}
	serverTypes := make([]string, len(config.ServerTypes))
	for index, serverType := range config.ServerTypes {
		serverTypes[index] = serverType.ID
	}
	lifecycle := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle.Root})
	opened, err := lifecycle.OpenProject(t.Context(), root)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" || opened.Classification != projectlifecycle.ClassificationManaged {
		t.Fatalf("open cumulative project=%#v err=%v", opened, err)
	}
	view, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	if deployment, exists := view.Deployments["service-install-03-dns-client"]; exists {
		if len(view.Servers) != 3 || len(view.Deployments) != 3 || deployment.ServiceType != "dns-client" || deployment.Mode != "host-resolver" || len(view.HostPlacements) != 9 || len(deployment.Configuration) != 1 {
			t.Fatalf("existing cumulative dns-client state=%#v", view)
		}
		return opened.Root, opened.Project.ID
	}
	if len(view.Servers) != 3 || len(view.Deployments) != 2 || view.Deployments["service-install-02-bind"].ServiceType != "bind" {
		t.Fatalf("unexpected cumulative base=%#v", view)
	}
	revision, err := installer.ProjectRevision(opened.Root)
	if err != nil {
		t.Fatal(err)
	}
	backend := installer.NewBackend(nil,
		installer.WithServerTypes(serverTypes),
		installer.WithProjectCatalogResolver(func(ctx context.Context, projectRoot string) (*projectlifecycle.ProjectCatalogView, error) {
			return lifecycle.ResolveProjectCatalog(ctx, projectRoot)
		}),
	)
	sessions := installer.NewEditSessionStore()
	session, err := sessions.Start(opened.Project.ID, opened.Root, opened.Classification, revision)
	if err != nil {
		t.Fatal(err)
	}
	commands := []installer.EditCommand{
		{Operation: "CreateServiceDeployment", DeploymentID: "service-install-03-dns-client", ServiceType: "dns-client", Mode: "host-resolver"},
		{Operation: "ReconcileHostScopedDeploymentPlacement", DeploymentID: "service-install-03-dns-client", Hosts: []installer.PlacementHost{{HostID: "node1", Priority: 150}, {HostID: "node2", Priority: 120}, {HostID: "node3", Priority: 100}}},
		{Operation: "SetServiceConfigurationValue", DeploymentID: "service-install-03-dns-client", Scope: "DEPLOYMENT", Setting: "dnsServerRef", Value: "service-install-02-bind"},
	}
	for _, command := range commands {
		if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
			t.Fatalf("append %s: %v", command.Operation, err)
		}
	}
	plan, err := sessions.ReviewStructural(t.Context(), backend, session.SessionID)
	if err != nil || plan == nil || !plan.SaveAllowed {
		if plan != nil && plan.Finding != nil {
			t.Fatalf("review finding=%s field=%s message=%s err=%v", plan.Finding.Code, plan.Finding.Field, plan.Finding.SafeMessage, err)
		}
		t.Fatalf("review=%#v err=%v", plan, err)
	}
	if _, err := sessions.BeginCommit(session.SessionID, plan.PlanID); err != nil {
		t.Fatal(err)
	}
	committed := backend.CommitStructuralSave(t.Context(), plan.PlanID)
	if committed.Status != "COMMITTED" || !committed.Changed || committed.Managed == nil || !sessions.FinishCommit(session.SessionID, plan.PlanID, true) {
		t.Fatalf("commit=%#v", committed)
	}
	reopened, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	deployment, exists := reopened.Deployments["service-install-03-dns-client"]
	if !exists || len(reopened.Servers) != 3 || len(reopened.Deployments) != 3 || len(reopened.HostPlacements) != 9 || deployment.ServiceType != "dns-client" || deployment.Mode != "host-resolver" || len(deployment.Configuration) != 1 {
		t.Fatalf("reopen=%#v", reopened)
	}
	return opened.Root, opened.Project.ID
}

// configureHAProxyProjectThroughGo extends the cumulative project with the
// complete, typed PKI prerequisite and one host-scoped HAProxy deployment.
// The runtime-only store password is represented solely by the closed
// reference; no password is stored in the portable project.
func configureHAProxyProjectThroughGo(t *testing.T, repository string, bundle executionbundle.Verified, root string) (string, string) {
	t.Helper()
	config, err := appconfig.Load(filepath.Join(repository, "config", "application.yml"))
	if err != nil {
		t.Fatal(err)
	}
	serverTypes := make([]string, len(config.ServerTypes))
	for index, serverType := range config.ServerTypes {
		serverTypes[index] = serverType.ID
	}
	lifecycle := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: bundle.Root})
	opened, err := lifecycle.OpenProject(t.Context(), root)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" || opened.Classification != projectlifecycle.ClassificationManaged {
		t.Fatalf("open cumulative project=%#v err=%v", opened, err)
	}
	view, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	if deployment, exists := view.Deployments["service-install-04-haproxy"]; exists {
		if len(view.Servers) != 3 || len(view.Deployments) != 4 || deployment.ServiceType != "haproxy" || deployment.Mode != "https-host-routing" || len(view.HostPlacements) != 12 || view.PKI.TLSProfiles["service-install-haproxy-tls"] == nil {
			t.Fatalf("existing cumulative haproxy state=%#v", view)
		}
		return opened.Root, opened.Project.ID
	}
	if len(view.Servers) != 3 || len(view.Deployments) != 3 || view.Deployments["service-install-03-dns-client"].ServiceType != "dns-client" {
		t.Fatalf("unexpected cumulative base=%#v", view)
	}
	revision, err := installer.ProjectRevision(opened.Root)
	if err != nil {
		t.Fatal(err)
	}
	backend := installer.NewBackend(nil,
		installer.WithServerTypes(serverTypes),
		installer.WithProjectCatalogResolver(func(ctx context.Context, projectRoot string) (*projectlifecycle.ProjectCatalogView, error) {
			return lifecycle.ResolveProjectCatalog(ctx, projectRoot)
		}),
	)
	sessions := installer.NewEditSessionStore()
	session, err := sessions.Start(opened.Project.ID, opened.Root, opened.Classification, revision)
	if err != nil {
		t.Fatal(err)
	}
	commands := []installer.EditCommand{
		{Operation: "CreateCertificateAuthority", EntityID: "service-install-ca", Entity: map[string]any{"mode": "MANAGED", "commonName": "Service Install QA CA"}},
		{Operation: "CreateCertificateProfile", EntityID: "service-install-server", Entity: map[string]any{"authorityRef": "service-install-ca", "keyAlgorithm": "RSA", "keySize": 2048, "usages": []any{"serverAuth", "clientAuth"}, "sanPolicy": map[string]any{"includeHostDns": true, "includeHostIp": true}}},
		{Operation: "CreateTLSProfile", EntityID: "service-install-haproxy-tls", Entity: map[string]any{"certificateProfileRef": "service-install-server", "scope": "DEPLOYMENT", "storePasswordSecretRef": "runtime:pki-store-password"}},
		{Operation: "CreateCertificateScope", EntityID: "service-install-haproxy-scope", Entity: map[string]any{"displayName": "Service Install HAProxy", "profile": "service-install-server", "scope": "DEPLOYMENT", "sources": map[string]any{"hosts": []any{"node1", "node2", "node3"}}}},
		{Operation: "CreateServiceDeployment", DeploymentID: "service-install-04-haproxy", ServiceType: "haproxy", Mode: "https-host-routing"},
		{Operation: "ReconcileHostScopedDeploymentPlacement", DeploymentID: "service-install-04-haproxy", Hosts: []installer.PlacementHost{{HostID: "node1", Priority: 150}, {HostID: "node2", Priority: 120}, {HostID: "node3", Priority: 100}}},
		{Operation: "SetServiceConfigurationValue", DeploymentID: "service-install-04-haproxy", Scope: "DEPLOYMENT", Setting: "tlsProfile", Value: "service-install-haproxy-tls"},
	}
	for _, command := range commands {
		if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
			t.Fatalf("append %s: %v", command.Operation, err)
		}
	}
	plan, err := sessions.ReviewStructural(t.Context(), backend, session.SessionID)
	if err != nil || plan == nil || !plan.SaveAllowed {
		if plan != nil && plan.Finding != nil {
			t.Fatalf("review finding=%s field=%s message=%s err=%v", plan.Finding.Code, plan.Finding.Field, plan.Finding.SafeMessage, err)
		}
		t.Fatalf("review=%#v err=%v", plan, err)
	}
	if _, err := sessions.BeginCommit(session.SessionID, plan.PlanID); err != nil {
		t.Fatal(err)
	}
	committed := backend.CommitStructuralSave(t.Context(), plan.PlanID)
	if committed.Status != "COMMITTED" || !committed.Changed || committed.Managed == nil || !sessions.FinishCommit(session.SessionID, plan.PlanID, true) {
		t.Fatalf("commit=%#v", committed)
	}
	reopened, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	deployment, exists := reopened.Deployments["service-install-04-haproxy"]
	tlsProfileConfigured := false
	for _, setting := range deployment.Configuration {
		tlsProfileConfigured = tlsProfileConfigured || (setting.Setting == "tlsProfile" && setting.OverridePresent && setting.Value == "service-install-haproxy-tls")
	}
	if !exists || len(reopened.Servers) != 3 || len(reopened.Deployments) != 4 || len(reopened.HostPlacements) != 12 || deployment.ServiceType != "haproxy" || deployment.Mode != "https-host-routing" || !tlsProfileConfigured || reopened.PKI.TLSProfiles["service-install-haproxy-tls"] == nil {
		t.Fatalf("reopen=%#v", reopened)
	}
	return opened.Root, opened.Project.ID
}

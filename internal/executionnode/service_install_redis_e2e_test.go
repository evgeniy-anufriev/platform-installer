package executionnode

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func TestServiceInstall07RedisLifecycle(t *testing.T) {
	if os.Getenv("PLATFORM_SERVICE_INSTALL_07_E2E") != "1" {
		t.Skip("set PLATFORM_SERVICE_INSTALL_07_E2E=1 for SERVICE-INSTALL-07 Redis acceptance")
	}
	address, user, identity, knownHosts := os.Getenv("PLATFORM_EXEC01A_ADDRESS"), os.Getenv("PLATFORM_EXEC01A_USER"), os.Getenv("PLATFORM_EXEC01A_IDENTITY"), os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	targetUser, targetPassword, targetSudoPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_USER"), os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_01_TARGET_SUDO_PASSWORD")
	pkiPassword, redisPassword, sentinelPassword := os.Getenv("PLATFORM_SERVICE_INSTALL_PKI_STORE_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_REDIS_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_REDIS_SENTINEL_PASSWORD")
	postgresAdmin, postgresMonitor := os.Getenv("PLATFORM_SERVICE_INSTALL_POSTGRES_ADMIN_PASSWORD"), os.Getenv("PLATFORM_SERVICE_INSTALL_POSTGRES_MONITOR_PASSWORD")
	postgresReplication := os.Getenv("PLATFORM_SERVICE_INSTALL_POSTGRES_REPLICATION_PASSWORD")
	if address == "" || user == "" || identity == "" || knownHosts == "" || targetUser == "" || targetPassword == "" || targetSudoPassword == "" || pkiPassword == "" || redisPassword == "" || sentinelPassword == "" || postgresAdmin == "" || postgresMonitor == "" || postgresReplication == "" {
		t.Fatal("SERVICE_INSTALL_07_E2E_PREREQUISITE_MISSING")
	}
	repository, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	bundle, err := (executionbundle.Cache{Root: filepath.Join(repository, "cache")}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	node := Node{ID: "service-install-07-node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	service := NewExecutionService(transport, transport)
	service.ConfigureTargetCredentialLease(func(request TargetCredentialLeaseRequest, use func(TargetCredentialLeasePayload) error) error {
		if !request.RequiresPKIStorePassword || len(request.RuntimeSecretRequirements) < 1 || len(request.RuntimeSecretRequirements) > 6 {
			return fmt.Errorf("REDIS_RUNTIME_SECRET_REQUEST_INVALID")
		}
		available := map[string]string{
			"redis-password": redisPassword, "redis-sentinel-password": sentinelPassword,
			"postgresql-admin-password": postgresAdmin, "postgresql-monitor-password": postgresMonitor,
			"postgresql-replication-password": postgresReplication,
		}
		values := make(map[string]string, len(request.RuntimeSecretRequirements))
		for _, requirement := range request.RuntimeSecretRequirements {
			value, ok := available[requirement]
			if !ok || value == "" {
				return fmt.Errorf("REDIS_RUNTIME_SECRET_SET_INVALID")
			}
			values[requirement] = value
		}
		return use(TargetCredentialLeasePayload{Username: targetUser, Password: targetPassword, SudoPassword: targetSudoPassword, PKIStorePassword: pkiPassword, RuntimeSecretValues: values})
	})

	ctx, cancel := context.WithTimeout(context.Background(), 240*time.Minute)
	defer cancel()
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	observer, err := NewRunObserver(transport, filepath.Join(repository, ".runtime"))
	if err != nil {
		t.Fatal(err)
	}

	scenario := os.Getenv("PLATFORM_SERVICE_INSTALL_07_SCENARIO")
	if scenario != "" && scenario != "ha33" {
		t.Fatal("SERVICE_INSTALL_07_SCENARIO_INVALID")
	}
	if scenario == "" {
		standaloneRoot := qaServiceInstall07Root(t, repository, "PLATFORM_SERVICE_INSTALL_07_STANDALONE_PROJECT", "service-install-07-redis-standalone")
		standalone, standaloneID := configureRedisProjectThroughGo(t, repository, bundle, standaloneRoot, "standalone", "service-install-07-redis-standalone", []qaRedisHost{{ID: "redis-standalone-host", Address: "192.168.56.103"}}, []installer.PlacementMember{{MemberID: "redis-standalone", HostID: "redis-standalone-host", Roles: []string{"redis"}}}, "redis-standalone-tls", 6379)
		runRedisInstallCycles(t, ctx, service, observer, node, standalone, standaloneID, release, 2, []string{"pki-store-password", "redis-password"}, "", 0)
		// The cumulative project retains the default single-host topology.
		ha31Root := cumulativeProjectRoot(t, repository)
		ha31, ha31ID := configureRedisProjectThroughGo(t, repository, bundle, ha31Root, "sentinel-ha", "service-install-07-redis-ha-31", nil, []installer.PlacementMember{
			{MemberID: "redis-ha31-a", HostID: "node1", Roles: []string{"redis", "sentinel"}},
			{MemberID: "redis-ha31-b", HostID: "node1", Roles: []string{"redis", "sentinel"}},
			{MemberID: "redis-ha31-c", HostID: "node1", Roles: []string{"redis", "sentinel"}},
		}, "service-install-07-redis-ha-31-tls", 6379)
		runRedisInstallCycles(t, ctx, service, observer, node, ha31, ha31ID, release, 2, []string{"pki-store-password", "postgresql-admin-password", "postgresql-monitor-password", "postgresql-replication-password", "redis-password", "redis-sentinel-password"}, "redis-ha31-a", 26379)
	}

	ha33Root := qaServiceInstall07Root(t, repository, "PLATFORM_SERVICE_INSTALL_07_HA_33_PROJECT", "service-install-07-redis-ha-33")
	ha33, ha33ID := configureRedisProjectThroughGo(t, repository, bundle, ha33Root, "sentinel-ha", "service-install-07-redis-ha-33", []qaRedisHost{
		{ID: "redis-ha33-node1", Address: "192.168.56.101"},
		{ID: "redis-ha33-node2", Address: "192.168.56.102"},
		{ID: "redis-ha33-node3", Address: "192.168.56.103"},
	}, []installer.PlacementMember{
		{MemberID: "redis-ha33-a", HostID: "redis-ha33-node1", Roles: []string{"redis", "sentinel"}},
		{MemberID: "redis-ha33-b", HostID: "redis-ha33-node2", Roles: []string{"redis", "sentinel"}},
		{MemberID: "redis-ha33-c", HostID: "redis-ha33-node3", Roles: []string{"redis", "sentinel"}},
	}, "redis-ha33-tls", 6382)
	runRedisInstallCycles(t, ctx, service, observer, node, ha33, ha33ID, release, 2, []string{"pki-store-password", "redis-password", "redis-sentinel-password"}, "", 0)
}

type qaRedisHost struct {
	ID      string
	Address string
}

func qaServiceInstall07Root(t *testing.T, repository, environment, name string) string {
	t.Helper()
	root := os.Getenv(environment)
	if root == "" {
		root = filepath.Join(t.TempDir(), name+"-project")
	}
	abs, err := filepath.Abs(root)
	if err != nil {
		t.Fatal(err)
	}
	return abs
}

func configureRedisProjectThroughGo(t *testing.T, repository string, bundle executionbundle.Verified, root, mode, deploymentID string, hosts []qaRedisHost, members []installer.PlacementMember, tlsProfile string, redisPort int) (string, string) {
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
	if _, err := os.Stat(filepath.Join(root, "project.yml")); os.IsNotExist(err) {
		if err := os.MkdirAll(filepath.Dir(root), 0o700); err != nil {
			t.Fatal(err)
		}
		if _, err := lifecycle.CreateProject(t.Context(), projectlifecycle.CreateProjectRequest{ProjectRoot: root, DisplayName: filepath.Base(root), CompatibilitySourceID: projectlifecycle.DefaultCompatibilitySourceID}); err != nil {
			t.Fatalf("create Redis QA project: %v", err)
		}
	}
	opened, err := lifecycle.OpenProject(t.Context(), root)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" {
		t.Fatalf("open Redis project=%#v err=%v", opened, err)
	}
	var managedView *installer.ManagedProjectView
	existingDeployment := false
	if opened.Classification == projectlifecycle.ClassificationManaged {
		view, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
		if err != nil {
			t.Fatalf("read Redis managed view: %v", err)
		}
		managedView = view
		if deployment, exists := view.Deployments[deploymentID]; exists {
			if deployment.ServiceType != "redis" || deployment.Mode != mode {
				t.Fatalf("existing Redis project state invalid: deployment=%#v", deployment)
			}
			existingDeployment = true
		}
	} else if opened.Classification != projectlifecycle.ClassificationEmpty {
		t.Fatalf("Redis QA project classification unsupported: %s", opened.Classification)
	}
	if existingDeployment && len(hosts) > 0 {
		if len(managedView.Servers) != len(hosts) {
			t.Fatal("existing isolated Redis QA server count mismatch")
		}
		for _, host := range hosts {
			server, exists := managedView.Servers[host.ID]
			if !exists || server.Address != host.Address || server.DesiredHostname != host.ID || server.Type != "infra" {
				t.Fatal("existing isolated Redis QA server identity mismatch")
			}
		}
		return opened.Root, opened.Project.ID
	}
	revision, err := installer.ProjectRevision(opened.Root)
	if err != nil {
		t.Fatal(err)
	}
	backend := installer.NewBackend(nil, installer.WithServerTypes(serverTypes), installer.WithProjectCatalogResolver(func(ctx context.Context, projectRoot string) (*projectlifecycle.ProjectCatalogView, error) {
		return lifecycle.ResolveProjectCatalog(ctx, projectRoot)
	}))
	sessions := installer.NewEditSessionStore()
	session, err := sessions.Start(opened.Project.ID, opened.Root, opened.Classification, revision)
	if err != nil {
		t.Fatal(err)
	}
	commands := make([]installer.EditCommand, 0, len(hosts)+8)
	for _, host := range hosts {
		commands = append(commands, installer.EditCommand{Operation: "CreateServer", HostID: host.ID, ServerType: "infra", DesiredHostname: host.ID, Address: host.Address})
	}
	if len(hosts) > 0 {
		hostIDs := make([]any, 0, len(hosts))
		for _, host := range hosts {
			hostIDs = append(hostIDs, host.ID)
		}
		commands = append(commands,
			installer.EditCommand{Operation: "CreateCertificateAuthority", EntityID: "redis-qa-ca", Entity: map[string]any{"mode": "MANAGED", "commonName": "Redis QA CA"}},
			installer.EditCommand{Operation: "CreateCertificateProfile", EntityID: "redis-qa-server", Entity: map[string]any{"authorityRef": "redis-qa-ca", "keyAlgorithm": "RSA", "keySize": 2048, "usages": []any{"serverAuth", "clientAuth"}, "sanPolicy": map[string]any{"includeHostDns": true, "includeHostIp": true}}},
			installer.EditCommand{Operation: "CreateTLSProfile", EntityID: tlsProfile, Entity: map[string]any{"certificateProfileRef": "redis-qa-server", "scope": "DEPLOYMENT", "storePasswordSecretRef": "runtime:pki-store-password"}},
			installer.EditCommand{Operation: "CreateCertificateScope", EntityID: "redis-qa-scope", Entity: map[string]any{"displayName": "Redis QA", "profile": "redis-qa-server", "scope": "DEPLOYMENT", "sources": map[string]any{"hosts": hostIDs}}},
		)
	} else if mode == "sentinel-ha" {
		if managedView == nil || managedView.PKI.Authorities["service-install-ca"] == nil || len(managedView.Servers) != 3 {
			t.Fatalf("Redis cumulative PKI/server prerequisites are missing")
		}
		hostIDs := make([]string, 0, len(managedView.Servers))
		for hostID := range managedView.Servers {
			hostIDs = append(hostIDs, hostID)
		}
		sort.Strings(hostIDs)
		profileID := deploymentID + "-profile"
		scopeID := deploymentID + "-scope"
		if _, exists := managedView.PKI.Profiles[profileID]; !exists {
			commands = append(commands, installer.EditCommand{Operation: "CreateCertificateProfile", EntityID: profileID, Entity: map[string]any{
				"authorityRef": "service-install-ca", "keyAlgorithm": "RSA", "keySize": 2048,
				"usages":    []any{"serverAuth", "clientAuth"},
				"sanPolicy": map[string]any{"includeHostDns": true, "includeHostIp": true},
			}})
		}
		if _, exists := managedView.PKI.Scopes[scopeID]; !exists {
			hostRefs := make([]any, len(hostIDs))
			for index, hostID := range hostIDs {
				hostRefs[index] = hostID
			}
			commands = append(commands, installer.EditCommand{Operation: "CreateCertificateScope", EntityID: scopeID, Entity: map[string]any{
				"displayName": "Redis Sentinel QA", "profile": profileID, "scope": "DEPLOYMENT",
				"sources": map[string]any{"hosts": hostRefs},
			}})
		}
		if _, exists := managedView.PKI.TLSProfiles[tlsProfile]; !exists {
			commands = append(commands, installer.EditCommand{Operation: "CreateTLSProfile", EntityID: tlsProfile, Entity: map[string]any{
				"certificateProfileRef": profileID, "scope": "DEPLOYMENT", "storePasswordSecretRef": "runtime:pki-store-password",
			}})
		}
	}
	if !existingDeployment {
		commands = append(commands, installer.EditCommand{Operation: "CreateServiceDeployment", DeploymentID: deploymentID, ServiceType: "redis", Mode: mode})
	}
	commands = append(commands,
		installer.EditCommand{Operation: "ReconcileDeploymentPlacement", DeploymentID: deploymentID, Members: members},
		installer.EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: deploymentID, Scope: "DEPLOYMENT", Setting: "tlsProfile", Value: tlsProfile},
		installer.EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: deploymentID, Scope: "DEPLOYMENT", Setting: "redisCredential", Value: map[string]any{"passwordSecretRef": "runtime:redis-password"}},
	)
	if mode == "sentinel-ha" {
		commands = append(commands, installer.EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: deploymentID, Scope: "DEPLOYMENT", Setting: "sentinelCredential", Value: map[string]any{"passwordSecretRef": "runtime:redis-sentinel-password"}})
	}
	if redisPort != 6379 {
		commands = append(commands, installer.EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: deploymentID, Scope: "DEPLOYMENT", Setting: "redisPort", Value: redisPort})
	}
	if redisPort != 6379 {
		commands = append(commands, installer.EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: deploymentID, Scope: "DEPLOYMENT", Setting: "sentinelPort", Value: 26379 + redisPort - 6379})
	}
	for _, command := range commands {
		if _, err := sessions.Append(session.SessionID, command, backend); err != nil {
			t.Fatalf("append Redis %s: %v", command.Operation, err)
		}
	}
	review, err := sessions.ReviewStructural(t.Context(), backend, session.SessionID)
	if err == nil && review != nil && review.Status == "NO_CHANGE" {
		// The cumulative QA project may already contain this exact final state
		// from an earlier interrupted acceptance attempt. Reuse the authoritative
		// saved revision instead of treating the correct no-op as a failed Save.
		return opened.Root, opened.Project.ID
	}
	if err != nil || review == nil || !review.SaveAllowed {
		if review != nil && review.Finding != nil {
			t.Fatalf("Redis save finding=%s field=%s err=%v", review.Finding.Code, review.Finding.Field, err)
		}
		t.Fatalf("Redis structural review=%#v err=%v", review, err)
	}
	if _, err := sessions.BeginCommit(session.SessionID, review.PlanID); err != nil {
		t.Fatal(err)
	}
	committed := backend.CommitStructuralSave(t.Context(), review.PlanID)
	if committed.Status != "COMMITTED" || !committed.Changed || !sessions.FinishCommit(session.SessionID, review.PlanID, true) {
		t.Fatalf("Redis save commit=%#v", committed)
	}
	reopened, err := installer.ReadManagedProjectViewWithCatalog(opened.Root, opened.Catalog)
	if err != nil {
		t.Fatal(err)
	}
	if deployment, exists := reopened.Deployments[deploymentID]; !exists || deployment.ServiceType != "redis" || deployment.Mode != mode {
		t.Fatalf("Redis reopen deployment=%#v exists=%t", deployment, exists)
	}
	return opened.Root, opened.Project.ID
}

func runRedisInstallCycles(t *testing.T, ctx context.Context, service *ExecutionService, observer *RunObserver, node Node, project, projectID string, release map[string]any, cycles int, expectedRequirements []string, failoverSentinel string, failoverPort int) {
	t.Helper()
	var failoverMaster string
	for cycle := 1; cycle <= cycles; cycle++ {
		started := time.Now()
		plan, err := service.CreatePlan(ctx, node, project, release)
		if err != nil {
			t.Fatalf("Redis cycle=%d plan: %v", cycle, err)
		}
		if plan.Plan.Status != "EXECUTABLE" || plan.Plan.ProjectIdentity != projectID {
			codes := make([]string, 0, len(plan.Plan.Findings))
			for _, finding := range plan.Plan.Findings {
				codes = append(codes, finding.Code)
			}
			t.Fatalf("Redis cycle=%d plan blocked or identity mismatch: status=%s identity=%s expected=%s findings=%v", cycle, plan.Plan.Status, plan.Plan.ProjectIdentity, projectID, codes)
		}
		actualRequirements := make(map[string]struct{}, len(plan.Plan.RequiredCredentials))
		for _, requirement := range plan.Plan.RequiredCredentials {
			actualRequirements[requirement.RequirementRef] = struct{}{}
		}
		if len(actualRequirements) != len(expectedRequirements) {
			t.Fatalf("Redis cycle=%d credential descriptor count=%d want=%d", cycle, len(actualRequirements), len(expectedRequirements))
		}
		for _, requirement := range expectedRequirements {
			if _, ok := actualRequirements[requirement]; !ok {
				t.Fatalf("Redis cycle=%d missing safe credential descriptor %s", cycle, requirement)
			}
		}
		if err := service.ApprovePlan(plan.ID, plan.Plan.Acknowledgements); err != nil {
			t.Fatal(err)
		}
		run, err := service.Start(ctx, node, plan.ID)
		if err != nil {
			t.Fatalf("Redis cycle=%d start: %v", cycle, err)
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
					t.Fatalf("Redis cycle=%d observer: %v", cycle, observeErr)
				}
			case <-ctx.Done():
				t.Fatalf("Redis cycle=%d observer timeout", cycle)
			}
		}
		current, _, err := service.Sync(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("Redis cycle=%d terminal=%#v err=%v", cycle, current, err)
		}
		events, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		apply, verify, changed := false, false, 0
		for _, event := range events {
			apply = apply || (event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && strings.HasPrefix(event.ActionID, "apply:"))
			verify = verify || (event.EventType == "ACTION_COMPLETED" && event.Status == "SUCCESS" && strings.HasPrefix(event.ActionID, "verify:"))
			if event.EventType == "TASK_COMPLETED" && event.Status == "CHANGED" {
				changed++
			}
		}
		if !apply || !verify {
			t.Fatalf("Redis cycle=%d missing apply/verify success: apply=%t verify=%t", cycle, apply, verify)
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("Redis repeat apply changed=%d", changed)
		}
		if cycle == 1 && changed == 0 {
			t.Fatalf("Redis first apply unexpectedly changed=0")
		}
		t.Logf("Redis project=%s cycle=%d runId=%s terminal=%s duration=%s events=%d changed=%d", projectID, cycle, run.RunID, current.State, time.Since(started).Round(time.Second), len(events), changed)
		if cycle == 1 && failoverSentinel != "" {
			before := redisSentinelMaster(ctx, t, node, failoverSentinel, failoverPort, "GET-MASTER-ADDR-BY-NAME")
			if err := redisSentinelCommand(ctx, node, failoverSentinel, failoverPort, "FAILOVER"); err != nil {
				t.Fatalf("Redis controlled Sentinel failover failed: %v", err)
			}
			deadline := time.Now().Add(2 * time.Minute)
			for time.Now().Before(deadline) {
				failoverMaster = redisSentinelMaster(ctx, t, node, failoverSentinel, failoverPort, "GET-MASTER-ADDR-BY-NAME")
				if failoverMaster != "" && failoverMaster != before {
					break
				}
				time.Sleep(5 * time.Second)
			}
			if failoverMaster == "" || failoverMaster == before {
				t.Fatalf("Redis Sentinel did not elect a different master; previous=%s", before)
			}
			t.Logf("Redis controlled failover previousMaster=%s currentMaster=%s", before, failoverMaster)
		} else if cycle == 2 && failoverSentinel != "" {
			currentMaster := redisSentinelMaster(ctx, t, node, failoverSentinel, failoverPort, "GET-MASTER-ADDR-BY-NAME")
			if currentMaster != failoverMaster {
				t.Fatalf("Redis repeat apply changed Sentinel master: afterFailover=%s afterRepeat=%s", failoverMaster, currentMaster)
			}
		}
	}
}

func redisSentinelMaster(ctx context.Context, t *testing.T, node Node, memberID string, port int, operation string) string {
	t.Helper()
	output := runRedisSentinelCLI(ctx, t, node, memberID, port, operation, "redis-ha31-a")
	return strings.TrimSpace(output)
}

func redisSentinelCommand(ctx context.Context, node Node, memberID string, port int, operation string) error {
	_, err := runRedisSentinelCLIWithError(ctx, node, memberID, port, operation, "redis-ha31-a")
	return err
}

func runRedisSentinelCLI(ctx context.Context, t *testing.T, node Node, memberID string, port int, operation, masterName string) string {
	t.Helper()
	output, err := runRedisSentinelCLIWithError(ctx, node, memberID, port, operation, masterName)
	if err != nil {
		t.Fatalf("Redis Sentinel %s query failed", operation)
	}
	return output
}

func runRedisSentinelCLIWithError(ctx context.Context, node Node, memberID string, port int, operation, masterName string) (string, error) {
	if operation != "FAILOVER" && operation != "GET-MASTER-ADDR-BY-NAME" {
		return "", fmt.Errorf("REDIS_QA_SENTINEL_OPERATION_INVALID")
	}
	remotePython := `import json, os, re, subprocess, sys
from pathlib import Path
configuration, pki, address, port, operation, master = sys.argv[1:]
text = Path(configuration).read_text(encoding="utf-8")
match = re.search(r"(?m)^requirepass (.+)$", text)
if not match:
    raise SystemExit("REDIS_QA_SENTINEL_AUTH_UNAVAILABLE")
password = json.loads(match.group(1))
env = os.environ.copy()
env["REDISCLI_AUTH"] = password
args = ["redis-cli", "--raw", "--tls", "--cacert", str(Path(pki) / "ca-chain.pem"), "--cert", str(Path(pki) / "certificate.pem"), "--key", str(Path(pki) / "private-key.pem"), "-h", address, "-p", port, "--user", "default", "SENTINEL", operation, master]
result = subprocess.run(args, text=True, capture_output=True, env=env)
if result.returncode:
    raise SystemExit("REDIS_QA_SENTINEL_COMMAND_FAILED")
lines = result.stdout.splitlines()
if operation == "GET-MASTER-ADDR-BY-NAME":
    if len(lines) != 2:
        raise SystemExit("REDIS_QA_SENTINEL_MASTER_UNAVAILABLE")
    print(lines[0] + ":" + lines[1])
else:
    print(result.stdout.strip())
`
	remoteCommand := fmt.Sprintf("sudo -n python3 - %s %s %s %d %s %s", shellQuote("/etc/platform/redis/"+memberID+"/sentinel.conf"), shellQuote("/etc/platform/redis/"+memberID+"/pki"), shellQuote(node.Address), port, shellQuote(operation), shellQuote(masterName))
	args := []string{"-i", mustIdentity(node), "-o", "IdentitiesOnly=yes", "-o", "UserKnownHostsFile=" + node.HostKey.KnownHosts, "-o", "StrictHostKeyChecking=yes", "-T", node.User + "@" + node.Address, remoteCommand}
	command := exec.CommandContext(ctx, "ssh", args...)
	command.Stdin = strings.NewReader(remotePython)
	output, err := command.Output()
	if err != nil {
		return "", fmt.Errorf("REDIS_QA_SENTINEL_COMMAND_FAILED")
	}
	return strings.TrimSpace(string(output)), nil
}

func mustIdentity(node Node) string {
	identity, err := (e2eIdentity{path: os.Getenv("PLATFORM_EXEC01A_IDENTITY")}).IdentityFile(node.CredentialRef)
	if err != nil {
		panic("REDIS_QA_IDENTITY_UNAVAILABLE")
	}
	return identity
}

func shellQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "'\\''") + "'"
}

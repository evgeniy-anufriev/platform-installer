package executionnode

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/executionbundle"
)

type e2eIdentity struct{ path string }

func (i e2eIdentity) IdentityFile(string) (string, error) { return i.path, nil }

type e2eRunner struct {
	delegate osRunner
	calls    []recordedCommand
}

func TestUIBE04EProductionKafkaLifecycleE2E(t *testing.T) {
	if os.Getenv("PLATFORM_UI_BE04E_E2E") != "1" {
		t.Skip("set PLATFORM_UI_BE04E_E2E=1 for the real UI-BE-04E lifecycle acceptance")
	}
	address, user, identity, knownHosts, project := os.Getenv("PLATFORM_EXEC01A_ADDRESS"), os.Getenv("PLATFORM_EXEC01A_USER"), os.Getenv("PLATFORM_EXEC01A_IDENTITY"), os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS"), os.Getenv("PLATFORM_EXEC01A_KAFKA_PROJECT")
	if address == "" || user == "" || identity == "" || knownHosts == "" || project == "" {
		t.Fatal("UI_BE_04E_E2E_PREREQUISITE_MISSING")
	}
	bundleRoot, err := filepath.Abs(filepath.Join("..", "..", "cache"))
	if err != nil {
		t.Fatal(err)
	}
	bundle, err := (executionbundle.Cache{Root: bundleRoot}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	artifact := filepath.ToSlash(filepath.Join("runtime", "artifacts", "kafka", "kafka_2.13-4.3.1-ui-be-04e-6.tgz"))
	node := Node{ID: "node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	targets := []Node{node, {ID: "node2", Address: "192.168.56.102", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey}, {ID: "node3", Address: "192.168.56.103", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey}}
	runner := &e2eRunner{}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}, Runner: runner}
	builder := transport
	client := transport
	service := NewExecutionService(builder, client)
	service.ConfigureServiceExecution(transport, transport)
	runtimeRelease := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	run := func() ExecutionRun {
		record, createErr := service.CreateServicePlan(context.Background(), node, ServicePlanRequest{Service: "kafka", Operation: "apply", Target: node, ArtifactTargets: targets, BundleCandidates: []artifactsource.Candidate{{ID: "kafka-4.3.1", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64", Artifacts: []artifactsource.Artifact{{Ref: artifact, SHA256: "sha256:f118328b2d053497350d5befd82c08db7ffd710327ff52943dd5caaa1b25db21", Type: "archive"}}}}, PKISecretFiles: map[string]string{"runtime:pki-store-password": "/var/tmp/postgres-01b/pki-password"}}, project, runtimeRelease)
		if createErr != nil {
			t.Fatalf("%v calls=%+v", createErr, runner.calls)
		}
		if approveErr := service.ApprovePlan(record.ID, record.Plan.Acknowledgements); approveErr != nil {
			t.Fatal(approveErr)
		}
		started, startErr := service.StartService(context.Background(), node, record.ID)
		if startErr != nil {
			t.Fatal(startErr)
		}
		for deadline := time.Now().Add(20 * time.Minute); time.Now().Before(deadline); {
			current, _, syncErr := service.Sync(context.Background(), node, started.RunID)
			if syncErr != nil {
				t.Fatal(syncErr)
			}
			if current.State == "SUCCEEDED" || current.State == "FAILED" || current.State == "CANCELLED" || current.State == "INTERRUPTED" {
				return current
			}
			time.Sleep(2 * time.Second)
		}
		t.Fatal("UI_BE_04E_EXECUTION_TIMEOUT")
		return ExecutionRun{}
	}
	first := run()
	if first.State != "SUCCEEDED" {
		t.Fatalf("first run state=%s", first.State)
	}
	second := run()
	if second.State != "SUCCEEDED" {
		t.Fatalf("repeat run state=%s", second.State)
	}
}

func (r *e2eRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	output, err := r.delegate.Run(ctx, name, args, input)
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(output)})
	return output, err
}

func (r *e2eRunner) playbookOutput(playbook string) string {
	for index := len(r.calls) - 1; index >= 0; index-- {
		if r.calls[index].name == "ssh" && strings.Contains(strings.Join(r.calls[index].args, " "), playbook) {
			return r.calls[index].input
		}
	}
	return ""
}

func TestEXEC01AProductionKafkaE2E(t *testing.T) {
	if os.Getenv("PLATFORM_EXEC01A_E2E") != "1" {
		t.Skip("set PLATFORM_EXEC01A_E2E=1 for the real RED OS acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	project := os.Getenv("PLATFORM_EXEC01A_KAFKA_PROJECT")
	if address == "" || user == "" || identity == "" || knownHosts == "" || project == "" {
		t.Fatal("EXEC01A_E2E_PREREQUISITE_MISSING")
	}
	node := Node{ID: "node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	runner := &e2eRunner{}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}, Runner: runner}
	service := NewServiceExecutionService(transport, transport)
	request := ServiceExecutionRequest{
		Service: "kafka", Operation: "apply", ProjectRoot: project, Target: node,
		ArtifactTargets: []Node{
			node,
			{ID: "node2", Address: "192.168.56.102", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey},
			{ID: "node3", Address: "192.168.56.103", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey},
		},
		PKISecretFiles: map[string]string{"runtime:pki-store-password": "/var/tmp/postgres-01b/pki-password"},
		Requirements: []artifactsource.Requirement{
			{ID: "kafka-java", Name: "java-21-openjdk-headless", OS: "redos", Architecture: "x86_64"},
			{ID: "kafka-binary", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64"},
		},
		BundleCandidates: []artifactsource.Candidate{{
			ID: "kafka-4.3.1", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64",
			Artifacts: []artifactsource.Artifact{{Ref: "runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", SHA256: "sha256:f118328b2d053497350d5befd82c08db7ffd710327ff52943dd5caaa1b25db21", Type: "archive"}},
		}},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	apply, err := service.Execute(ctx, request)
	if err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/kafka/playbooks/apply.yml"))
	}
	if apply.Projection["kafka-binary"].Source != artifactsource.OfflineBundle || apply.Projection["kafka-java"].Source != artifactsource.Repository {
		t.Fatalf("unexpected projection: %+v", apply.Projection)
	}
	if len(apply.Probes) != 6 {
		t.Fatalf("unexpected probes: %+v", apply.Probes)
	}
	for _, target := range []string{"node1", "node2", "node3"} {
		if apply.TargetProjections[target]["kafka-java"].Source != artifactsource.Repository || apply.TargetProjections[target]["kafka-binary"].Source != artifactsource.OfflineBundle {
			t.Fatalf("unexpected target projection for %s: %+v", target, apply.TargetProjections[target])
		}
	}
	request.Operation = "verify"
	if _, err := service.Execute(ctx, request); err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/kafka/playbooks/verify.yml"))
	}
	request.Operation = "apply"
	if _, err := service.Execute(ctx, request); err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/kafka/playbooks/apply.yml"))
	}
	repeat := runner.playbookOutput("services/kafka/playbooks/apply.yml")
	if repeat == "" || !strings.Contains(repeat, "changed=0") || !strings.Contains(repeat, "failed=0") {
		t.Fatalf("repeat apply was not idempotent:\n%s", repeat)
	}
}

func TestEXEC01AProductionKeepalivedE2E(t *testing.T) {
	if os.Getenv("PLATFORM_EXEC01A_E2E") != "1" {
		t.Skip("set PLATFORM_EXEC01A_E2E=1 for the real RED OS acceptance")
	}
	address := os.Getenv("PLATFORM_EXEC01A_ADDRESS")
	user := os.Getenv("PLATFORM_EXEC01A_USER")
	identity := os.Getenv("PLATFORM_EXEC01A_IDENTITY")
	knownHosts := os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS")
	project := os.Getenv("PLATFORM_EXEC01A_KEEPALIVED_PROJECT")
	if address == "" || user == "" || identity == "" || knownHosts == "" || project == "" {
		t.Fatal("EXEC01A_E2E_PREREQUISITE_MISSING")
	}
	node := Node{ID: "node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	runner := &e2eRunner{}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}, Runner: runner}
	service := NewServiceExecutionService(transport, transport)
	request := ServiceExecutionRequest{
		Service: "keepalived", Operation: "apply", ProjectRoot: project, Target: node,
		ArtifactTargets: []Node{
			node,
			{ID: "node2", Address: "192.168.56.102", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey},
			{ID: "node3", Address: "192.168.56.103", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey},
		},
		Requirements: []artifactsource.Requirement{{ID: "keepalived", Name: "keepalived", Version: "2.4.3", OS: "redos", Architecture: "x86_64"}},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	apply, err := service.Execute(ctx, request)
	if err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/keepalived/playbooks/apply.yml"))
	}
	if len(apply.Probes) != 3 || apply.Projection["keepalived"].Source != artifactsource.Repository {
		t.Fatalf("unexpected source resolution: probes=%+v projection=%+v", apply.Probes, apply.Projection)
	}
	for _, probe := range apply.Probes {
		if probe.Status != artifactsource.AvailableCompatible || apply.TargetProjections[probe.TargetNode]["keepalived"].Source != artifactsource.Repository {
			t.Fatalf("unexpected target resolution: probes=%+v projections=%+v", apply.Probes, apply.TargetProjections)
		}
	}
	if strings.Contains(runner.playbookOutput("services/keepalived/playbooks/apply.yml"), "platform.core.artifact_delivery") {
		t.Fatal("repository-first Keepalived invoked artifact_delivery")
	}
	request.Operation = "verify"
	if _, err := service.Execute(ctx, request); err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/keepalived/playbooks/verify.yml"))
	}
	request.Operation = "apply"
	if _, err := service.Execute(ctx, request); err != nil {
		t.Fatalf("%v\n%s", err, runner.playbookOutput("services/keepalived/playbooks/apply.yml"))
	}
	repeat := runner.playbookOutput("services/keepalived/playbooks/apply.yml")
	if repeat == "" || !strings.Contains(repeat, "changed=0") || !strings.Contains(repeat, "failed=0") {
		t.Fatalf("repeat apply was not idempotent:\n%s", repeat)
	}
}

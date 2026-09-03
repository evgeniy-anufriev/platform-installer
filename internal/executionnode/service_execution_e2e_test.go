package executionnode

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/artifactsource"
)

type e2eIdentity struct{ path string }

func (i e2eIdentity) IdentityFile(string) (string, error) { return i.path, nil }

type e2eRunner struct {
	delegate osRunner
	calls    []recordedCommand
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
	if len(apply.Probes) != 2 || apply.Probes[1].Status != artifactsource.NotFound {
		t.Fatalf("unexpected probes: %+v", apply.Probes)
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

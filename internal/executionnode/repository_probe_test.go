package executionnode

import (
	"context"
	"strings"
	"testing"

	"platform-installer/internal/artifactsource"
)

type probeRunner struct {
	output string
	calls  []recordedCommand
}

type countingProbe struct {
	result artifactsource.RepositoryProbeResult
	calls  int
}

func (p *countingProbe) ProbeRepository(context.Context, artifactsource.Requirement) (artifactsource.RepositoryProbeResult, error) {
	p.calls++
	return p.result, nil
}

type candidateProvider struct {
	candidate artifactsource.Candidate
	ok        bool
}

func (p candidateProvider) FindCompatible(artifactsource.Requirement) (artifactsource.Candidate, bool, error) {
	return p.candidate, p.ok, nil
}

func (r *probeRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name, append([]string(nil), args...), string(input)})
	return []byte(r.output), nil
}

func TestProbeRepositoryIsTargetScopedAndReadOnly(t *testing.T) {
	runner := &probeRunner{output: "haproxy|3.2.13|x86_64\n"}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	result, err := transport.ProbeRepository(context.Background(), testNode(), artifactsource.Requirement{Name: "haproxy", Version: "3.2.x", OS: "redos", Architecture: "x86_64"})
	if err != nil || result.Status != artifactsource.AvailableCompatible || len(result.Candidates) != 1 {
		t.Fatalf("%+v %v", result, err)
	}
	command := strings.Join(runner.calls[0].args, " ")
	if !strings.Contains(command, "sh -s -- haproxy") || !strings.Contains(runner.calls[0].input, "dnf -q repoquery") || strings.Contains(runner.calls[0].input, " install ") || strings.Contains(runner.calls[0].input, "--refresh") {
		t.Fatalf("unsafe probe command: %s / %s", command, runner.calls[0].input)
	}
}

func TestProbeRepositoryRejectsUntrustedPackageIdentity(t *testing.T) {
	runner := &probeRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	result, err := transport.ProbeRepository(context.Background(), testNode(), artifactsource.Requirement{Name: "../escape", OS: "redos", Architecture: "x86_64"})
	if err == nil || result.Reason != "REQUIREMENT_INVALID" || len(runner.calls) != 0 {
		t.Fatalf("%+v %v calls=%d", result, err, len(runner.calls))
	}
}

func TestResolveRequirementsWithTargetProbeBuildsAutomaticProjectionOnce(t *testing.T) {
	requirement := artifactsource.Requirement{ID: "kafka-binary", Name: "kafka", Version: "4.3.x", OS: "redos", Architecture: "x86_64"}
	probe := &countingProbe{result: artifactsource.RepositoryProbeResult{
		TargetNode: "node-1", Requirement: requirement, Status: artifactsource.NotFound, Reason: "REPOSITORY_NOT_FOUND",
	}}
	bundle := candidateProvider{candidate: artifactsource.Candidate{
		ID: "kafka-431", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64",
		Artifacts: []artifactsource.Artifact{{Ref: "runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", SHA256: "sha256:" + strings.Repeat("a", 64), Size: 12, Type: "archive"}},
	}, ok: true}
	projection, probes, err := ResolveRequirementsWithTargetProbe(context.Background(), Node{ID: "node-1"}, []artifactsource.Requirement{requirement}, probe, bundle)
	if err != nil || probe.calls != 1 || len(probes) != 1 {
		t.Fatalf("unexpected probe wiring: projection=%+v probes=%+v calls=%d err=%v", projection, probes, probe.calls, err)
	}
	if projection[requirement.ID].Source != artifactsource.OfflineBundle || projection[requirement.ID].TargetNode != "node-1" {
		t.Fatalf("unexpected automatic projection: %+v", projection)
	}
}

package executionnode

import (
	"context"
	"testing"

	"platform-installer/internal/artifactsource"
)

type serviceProbe struct {
	result artifactsource.RepositoryProbeResult
	calls  int
}

func (p *serviceProbe) ProbeRepository(context.Context, Node, artifactsource.Requirement) (artifactsource.RepositoryProbeResult, error) {
	p.calls++
	return p.result, nil
}

type serviceRuntime struct{ calls int }

func (r *serviceRuntime) ExecuteService(context.Context, ServiceExecutionRequest, map[string]map[string]artifactsource.Result) (bool, error) {
	r.calls++
	return true, nil
}

func TestServiceExecutionProjectsEveryArtifactTargetOnce(t *testing.T) {
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{Status: artifactsource.AvailableCompatible, Candidates: []artifactsource.Candidate{{Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64"}}}}
	runtime := &serviceRuntime{}
	request := serviceRequest()
	request.ArtifactTargets = []Node{{ID: "node1"}, {ID: "node2"}, {ID: "node3"}}
	result, err := NewServiceExecutionService(probe, runtime).Execute(context.Background(), request)
	if err != nil || probe.calls != 3 || runtime.calls != 1 || len(result.TargetProjections) != 3 {
		t.Fatalf("result=%+v probe=%d runtime=%d err=%v", result, probe.calls, runtime.calls, err)
	}
	for _, nodeID := range []string{"node1", "node2", "node3"} {
		resolved := result.TargetProjections[nodeID]["kafka-binary"]
		if resolved.Source != artifactsource.Repository || resolved.TargetNode != nodeID {
			t.Fatalf("target %s projection=%+v", nodeID, resolved)
		}
	}
}

func serviceRequest() ServiceExecutionRequest {
	return ServiceExecutionRequest{
		Service: "kafka", ProjectRoot: "project", Target: testNode(),
		Requirements:     []artifactsource.Requirement{{ID: "kafka-binary", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64"}},
		BundleCandidates: []artifactsource.Candidate{{ID: "kafka-4.3.1", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64", Artifacts: []artifactsource.Artifact{{Ref: "runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", SHA256: "sha256:test", Size: 1, Type: "archive"}}}},
	}
}

func TestServiceExecutionAutomaticallyProjectsOfflineSource(t *testing.T) {
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{TargetNode: "node1", Status: artifactsource.NotFound}}
	runtime := &serviceRuntime{}
	result, err := NewServiceExecutionService(probe, runtime).Execute(context.Background(), serviceRequest())
	if err != nil || probe.calls != 1 || runtime.calls != 1 || result.Applied != true {
		t.Fatalf("result=%+v probe=%d runtime=%d err=%v", result, probe.calls, runtime.calls, err)
	}
	if result.Projection["kafka-binary"].Source != artifactsource.OfflineBundle {
		t.Fatalf("projection=%+v", result.Projection)
	}
}

func TestServiceExecutionBlocksBeforeRuntime(t *testing.T) {
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{TargetNode: "node1", Status: artifactsource.NotFound}}
	runtime := &serviceRuntime{}
	request := serviceRequest()
	request.BundleCandidates = nil
	result, err := NewServiceExecutionService(probe, runtime).Execute(context.Background(), request)
	if err == nil || err.Error() != "SERVICE_EXECUTION_BLOCKED" || probe.calls != 1 || runtime.calls != 0 {
		t.Fatalf("result=%+v probe=%d runtime=%d err=%v", result, probe.calls, runtime.calls, err)
	}
}

func TestServiceExecutionUsesRepositoryWithoutDeliveryDecision(t *testing.T) {
	probe := &serviceProbe{result: artifactsource.RepositoryProbeResult{TargetNode: "node1", Status: artifactsource.AvailableCompatible, Candidates: []artifactsource.Candidate{{Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64"}}}}
	runtime := &serviceRuntime{}
	request := serviceRequest()
	request.Requirements[0].Name = "kafka"
	result, err := NewServiceExecutionService(probe, runtime).Execute(context.Background(), request)
	if err != nil || result.Projection["kafka-binary"].Source != artifactsource.Repository || runtime.calls != 1 {
		t.Fatalf("result=%+v runtime=%d err=%v", result, runtime.calls, err)
	}
}

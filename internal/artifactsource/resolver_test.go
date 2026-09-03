package artifactsource

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

type provider struct {
	candidate Candidate
	ok        bool
	err       error
}

func (p provider) FindCompatible(Requirement) (Candidate, bool, error) {
	return p.candidate, p.ok, p.err
}

var req = Requirement{ID: "kafka-runtime", Name: "kafka", Version: "4.3.x", OS: "redos", Architecture: "x86_64"}
var good = Candidate{ID: "kafka-431", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64"}
var offlineGood = Candidate{ID: "kafka-431", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64", Artifacts: []Artifact{{Ref: "runtime/artifacts/kafka/kafka.tgz", SHA256: "sha256:" + strings.Repeat("a", 64), Size: 12, Type: "archive"}}}

func TestResolveRepositoryWinsWhenBothCompatible(t *testing.T) {
	result, err := Resolve(req, provider{candidate: good, ok: true}, provider{candidate: good, ok: true})
	if err != nil || result.Source != Repository {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveFallsBackForIncompatibleRepository(t *testing.T) {
	result, err := Resolve(req, provider{candidate: Candidate{Name: "kafka", Version: "5.0.0", OS: "redos", Architecture: "x86_64"}, ok: true}, provider{candidate: good, ok: true})
	if err != nil || result.Source != OfflineBundle {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveFallsBackWhenRepositoryUnavailable(t *testing.T) {
	result, err := Resolve(req, provider{err: errors.New("unavailable")}, provider{candidate: good, ok: true})
	if err != nil || result.Source != OfflineBundle || result.Reason != "REPOSITORY_UNAVAILABLE" {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveBlocksWhenBothMissing(t *testing.T) {
	result, err := Resolve(req, provider{}, provider{})
	if err != nil || result.Source != Blocked {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveRepositoryCompatibleBundleMissing(t *testing.T) {
	result, err := Resolve(req, provider{candidate: good, ok: true}, provider{})
	if err != nil || result.Source != Repository {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveBlocksIncompatibleCandidates(t *testing.T) {
	bad := Candidate{Name: "kafka", Version: "4.2.0", OS: "redos", Architecture: "x86_64"}
	result, err := Resolve(req, provider{candidate: bad, ok: true}, provider{candidate: bad, ok: true})
	if err != nil || result.Source != Blocked {
		t.Fatalf("%+v %v", result, err)
	}
}
func TestResolveIsNodeScoped(t *testing.T) {
	first, _ := Resolve(req, provider{candidate: good, ok: true}, provider{})
	second, _ := Resolve(req, provider{}, provider{candidate: good, ok: true})
	if first.Source != Repository || second.Source != OfflineBundle {
		t.Fatalf("%+v %+v", first, second)
	}
}

func TestResolveForNodeProducesCoreContract(t *testing.T) {
	result, err := ResolveForNode("node-2", req, provider{candidate: good, ok: true}, provider{})
	if err != nil || result.TargetNode != "node-2" || result.Kind != "ResolvedArtifactSource" {
		t.Fatalf("%+v %v", result, err)
	}
	encoded, err := json.Marshal(result)
	if err != nil || !strings.Contains(string(encoded), `"source":"REPOSITORY"`) || !strings.Contains(string(encoded), `"targetNode":"node-2"`) {
		t.Fatalf("%s %v", encoded, err)
	}
}

func TestResolveCarriesVerifiedOfflineArtifactMetadata(t *testing.T) {
	result, err := Resolve(req, provider{}, provider{candidate: offlineGood, ok: true})
	if err != nil || result.Source != OfflineBundle || len(result.Artifacts) != 1 || result.Artifacts[0].Ref != offlineGood.Artifacts[0].Ref {
		t.Fatalf("%+v %v", result, err)
	}
}

func TestRuntimeProjectionPreservesPerNodeDecisions(t *testing.T) {
	repository, _ := ResolveForNode("node-1", req, provider{candidate: good, ok: true}, provider{})
	offline, _ := ResolveForNode("node-2", req, provider{}, provider{candidate: offlineGood, ok: true})
	first := RuntimeProjection("node-1", []Result{repository, offline})
	second := RuntimeProjection("node-2", []Result{repository, offline})
	if first[req.ID].Source != Repository || second[req.ID].Source != OfflineBundle {
		t.Fatalf("projection collapsed per-node decisions: first=%+v second=%+v", first, second)
	}
}

package executionnode

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/executionbundle"
)

// This opt-in acceptance uses the established three-node fixture. It never
// creates a competing Kafka deployment or resets existing storage.
func TestEXECOBS01ProductionKafkaObserverE2E(t *testing.T) {
	if os.Getenv("PLATFORM_EXEC_OBS01_E2E") != "1" {
		t.Skip("set PLATFORM_EXEC_OBS01_E2E=1 for production Kafka observer acceptance")
	}
	address, user, identity, knownHosts, project := os.Getenv("PLATFORM_EXEC01A_ADDRESS"), os.Getenv("PLATFORM_EXEC01A_USER"), os.Getenv("PLATFORM_EXEC01A_IDENTITY"), os.Getenv("PLATFORM_EXEC01A_KNOWN_HOSTS"), os.Getenv("PLATFORM_EXEC01A_KAFKA_PROJECT")
	if address == "" || user == "" || identity == "" || knownHosts == "" || project == "" {
		t.Fatal("EXEC_OBS01_E2E_PREREQUISITE_MISSING")
	}
	repo, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	bundle, err := (executionbundle.Cache{Root: filepath.Join(repo, "cache")}).Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0.3", Architecture: "x86_64"})
	if err != nil {
		t.Fatal(err)
	}
	node := Node{ID: "node1", Address: address, User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: HostKeyPolicy{State: "TRUSTED", KnownHosts: knownHosts, Fingerprint: "operator-approved"}}
	targets := []Node{node, {ID: "node2", Address: "192.168.56.102", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey}, {ID: "node3", Address: "192.168.56.103", User: user, Port: 22, CredentialRef: "runtime:ssh", HostKey: node.HostKey}}
	transport := OpenSSHTransport{Identity: e2eIdentity{path: identity}}
	service := NewExecutionService(transport, transport)
	service.ConfigureServiceExecution(transport, transport)
	release := map[string]any{"bundleDigest": bundle.Digest, "coreVersion": bundle.Manifest.CoreVersion, "catalogDigest": bundle.Manifest.CatalogDigest, "planningProtocol": "v1alpha1"}
	request := ServicePlanRequest{Service: "kafka", Operation: "apply", Target: node, ArtifactTargets: targets, BundleCandidates: []artifactsource.Candidate{{ID: "kafka-4.3.1", Name: "kafka", Version: "4.3.1", OS: "redos", Architecture: "x86_64", Artifacts: []artifactsource.Artifact{{Ref: "runtime/artifacts/kafka/kafka_2.13-4.3.1-ui-be-04e-6.tgz", SHA256: "sha256:f118328b2d053497350d5befd82c08db7ffd710327ff52943dd5caaa1b25db21", Type: "archive"}}}}, PKISecretFiles: map[string]string{"runtime:pki-store-password": "/var/tmp/postgres-01b/pki-password"}}
	ctx, cancel := context.WithTimeout(context.Background(), 28*time.Minute)
	defer cancel()
	for cycle := 1; cycle <= 2; cycle++ {
		began := time.Now()
		var run ExecutionRun
		if cycle == 1 && os.Getenv("PLATFORM_EXEC_OBS01_RESUME_RUN") != "" {
			run, err = transport.GetExecution(ctx, node, os.Getenv("PLATFORM_EXEC_OBS01_RESUME_RUN"))
			if err == nil && (run.State != "RUNNING" || run.ProjectIdentity != "kafka-real-multihost") {
				t.Fatal("resume requires the active established Kafka fixture run; historical replay cannot prove live acceptance")
			}
		} else {
			planned, planErr := service.CreateServicePlan(ctx, node, request, project, release)
			if planErr != nil {
				t.Fatal(planErr)
			}
			if err := service.ApprovePlan(planned.ID, planned.Plan.Acknowledgements); err != nil {
				t.Fatal(err)
			}
			run, err = service.StartService(ctx, node, planned.ID)
		}
		if err != nil {
			t.Fatal(err)
		}
		runtimeRoot := filepath.Join(repo, ".runtime")
		mirrorPath, _ := EventMirrorPath(runtimeRoot, run.RunID)
		t.Logf("cycle=%d runId=%s mirror=%s", cycle, run.RunID, mirrorPath)
		observer, err := NewRunObserver(transport, runtimeRoot)
		if err != nil {
			t.Fatal(err)
		}
		sub, err := observer.Observe(ctx, node, run.RunID)
		if err != nil {
			t.Fatal(err)
		}
		defer sub.Close()
		observed := []ExecutionEvent{}
		restarted := false
		for sub.Events != nil || sub.Errors != nil {
			select {
			case <-ctx.Done():
				t.Fatal("EXEC_OBS01_E2E_TIMEOUT")
			case e, ok := <-sub.Events:
				if !ok {
					sub.Events = nil
					continue
				}
				observed = append(observed, e)
				if e.EventType == "ACTION_STARTED" || e.EventType == "ACTION_COMPLETED" || e.EventType == "RUN_COMPLETED" {
					t.Logf("cycle=%d sequence=%d type=%s action=%s status=%s elapsed=%s", cycle, e.Sequence, e.EventType, e.ActionID, e.Status, time.Since(began).Round(time.Second))
				}
				if cycle == 1 && !restarted && e.EventType == "TASK_COMPLETED" && e.Sequence > run.Sequence {
					before, err := transport.GetExecution(ctx, node, run.RunID)
					if err != nil || before.State != "RUNNING" {
						t.Fatalf("disconnect requires active run: %+v %v", before, err)
					}
					info, err := os.Stat(mirrorPath)
					if err != nil || info.Size() == 0 {
						t.Fatal("live mirror missing")
					}
					t.Logf("live mirror sequence=%d bytes=%d; disconnecting observer", e.Sequence, info.Size())
					sub.Close()
					// Detach the client while Ansible continues under its controller.
					select {
					case <-time.After(5 * time.Second):
					case <-ctx.Done():
						t.Fatal(ctx.Err())
					}
					advanced := false
					for deadline := time.Now().Add(45 * time.Second); time.Now().Before(deadline); {
						after, err := transport.GetExecution(ctx, node, run.RunID)
						if err != nil {
							t.Fatal(err)
						}
						if after.Sequence > before.Sequence {
							t.Logf("remote continued while detached: sequence %d -> %d state=%s", before.Sequence, after.Sequence, after.State)
							advanced = true
							break
						}
						select {
						case <-time.After(time.Second):
						case <-ctx.Done():
							t.Fatal(ctx.Err())
						}
					}
					if !advanced {
						t.Fatal("no remote journal growth while observer detached")
					}
					observer, err = NewRunObserver(transport, runtimeRoot)
					if err != nil {
						t.Fatal(err)
					}
					sub, err = observer.SubscribeAfter(ctx, node, run.RunID, e.Sequence, 256)
					if err != nil {
						t.Fatal(err)
					}
					defer sub.Close()
					restarted = true
					t.Logf("observer restarted from subscriber checkpoint=%d", e.Sequence)
				}
			case err, ok := <-sub.Errors:
				if !ok {
					sub.Errors = nil
					continue
				}
				t.Fatalf("observer error: %v", err)
			}
		}
		current, err := transport.GetExecution(ctx, node, run.RunID)
		if err != nil || current.State != "SUCCEEDED" {
			t.Fatalf("terminal=%+v error=%v", current, err)
		}
		remote, err := observer.Replay(ctx, node, run.RunID, 0)
		if err != nil {
			t.Fatal(err)
		}
		if !equalEventStreams(observed, remote) {
			t.Fatalf("subscriber differs from remote: subscriber=%d remote=%d", len(observed), len(remote))
		}
		file, err := os.Open(mirrorPath)
		if err != nil {
			t.Fatal(err)
		}
		scanner := bufio.NewScanner(file)
		scanner.Buffer(make([]byte, 4096), maxMirroredEventBytes+1)
		mirrored := []ExecutionEvent{}
		for scanner.Scan() {
			var e ExecutionEvent
			if err := json.Unmarshal(scanner.Bytes(), &e); err != nil {
				t.Fatal(err)
			}
			mirrored = append(mirrored, e)
		}
		scanErr := scanner.Err()
		file.Close()
		if scanErr != nil || !equalEventStreams(mirrored, remote) {
			t.Fatalf("mirror differs from remote: mirror=%d remote=%d error=%v", len(mirrored), len(remote), scanErr)
		}
		tasks, terminal, changed := 0, 0, 0
		actions := map[string]int{}
		completedActions := map[string]bool{}
		durations := map[string]bool{}
		hostsByTask := map[string]map[string]bool{}
		for index, e := range remote {
			if e.Sequence != index+1 {
				t.Fatal("non-contiguous sequence")
			}
			if e.EventType == "RUN_COMPLETED" || e.EventType == "DIAGNOSTIC" && e.Status == "SUCCESS" && e.Sequence == current.Sequence {
				terminal++
			}
			if strings.HasPrefix(e.EventType, "TASK_") {
				tasks++
				actions[e.ActionID]++
			}
			if e.EventType == "ACTION_COMPLETED" && e.Status == "SUCCESS" {
				completedActions[e.ActionID] = true
			}
			if e.EventType == "DIAGNOSTIC" && e.Error != nil && strings.HasPrefix(e.Error.Code, "TASK_EVENT_STREAM_") {
				t.Fatal("normal Kafka acceptance requires complete task stream: " + e.Error.Code)
			}
			if e.EventType == "TASK_COMPLETED" && e.Task != nil {
				if e.ElapsedMillis != nil && *e.ElapsedMillis >= 0 {
					durations[e.ActionID] = true
				}
				if hostsByTask[e.Task.UUID] == nil {
					hostsByTask[e.Task.UUID] = map[string]bool{}
				}
				hostsByTask[e.Task.UUID][e.Host] = true
				if e.Status == "CHANGED" {
					changed++
					t.Logf("changed action=%s host=%s task=%s", e.ActionID, e.Host, e.Task.Name)
				}
			}
		}
		for _, action := range []string{"pki:apply", "apply:kafka-main", "verify:kafka-main"} {
			if actions[action] == 0 || !completedActions[action] || !durations[action] {
				t.Fatalf("missing successful measured task stream for %s", action)
			}
		}
		if cycle == 1 && !restarted {
			t.Fatal("live disconnect/restart was not exercised")
		}
		if cycle == 2 && changed != 0 {
			t.Fatalf("repeat apply changed=%d; expected 0", changed)
		}
		multi := false
		for _, hosts := range hostsByTask {
			if hosts["node1"] && hosts["node2"] && hosts["node3"] {
				multi = true
			}
		}
		if tasks == 0 || terminal != 1 || len(actions) < 3 || !multi {
			t.Fatalf("tasks=%d terminal=%d actions=%v multiHost=%v", tasks, terminal, actions, multi)
		}
		info, _ := os.Stat(mirrorPath)
		firstTimestamp, _ := time.Parse(time.RFC3339, remote[0].Timestamp)
		lastTimestamp, _ := time.Parse(time.RFC3339, remote[len(remote)-1].Timestamp)
		t.Logf("cycle=%d runId=%s terminal=SUCCEEDED runDuration=%s observationDuration=%s events=%d taskEvents=%d bytes=%d changedTasks=%d actions=%v mirror/subscriber/remote=IDENTICAL", cycle, run.RunID, lastTimestamp.Sub(firstTimestamp), time.Since(began).Round(time.Millisecond), len(remote), tasks, info.Size(), changed, actions)
	}
}

func equalEventStreams(left, right []ExecutionEvent) bool {
	a, errA := json.Marshal(left)
	b, errB := json.Marshal(right)
	return errA == nil && errB == nil && bytes.Equal(a, b)
}

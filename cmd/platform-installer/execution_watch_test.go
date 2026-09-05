package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
)

func testWatchOptions(t *testing.T) watchOptions {
	return watchOptions{runID: "installer-123", runtimeRoot: t.TempDir(), address: "192.0.2.1", user: "automation", identity: "PRIVATE-IDENTITY", knownHosts: "PRIVATE-HOSTS", fingerprint: "PRIVATE-FINGERPRINT", port: 22, after: 9}
}

func TestWatchTerminalAndErrors(t *testing.T) {
	for _, tc := range []struct {
		name, state string
		observerErr error
		resultErr   error
		want        int
	}{
		{"success", "SUCCEEDED", nil, nil, 0},
		{"failed", "FAILED", nil, nil, 1},
		{"remote cancelled", "CANCELLED", nil, nil, 1},
		{"interrupted", "INTERRUPTED", nil, nil, 1},
		{"nonterminal", "RUNNING", nil, nil, 3},
		{"mirror failure", "SUCCEEDED", &executionnode.ObserverError{Code: executionnode.ObserverMirrorFailure}, nil, 3},
		{"mirror and remote failure", "FAILED", &executionnode.ObserverError{Code: executionnode.ObserverMirrorFailure}, nil, 3},
		{"transport recovered", "SUCCEEDED", &executionnode.ObserverError{Code: executionnode.ObserverTransportFailure}, nil, 0},
		{"result error", "", nil, errors.New("PRIVATE-result"), 3},
		{"unknown observer error", "SUCCEEDED", errors.New("PRIVATE-observer"), nil, 3},
	} {
		t.Run(tc.name, func(t *testing.T) {
			options := testWatchOptions(t)
			var out, diagnostics bytes.Buffer
			closed := false
			event := executionnode.ExecutionEvent{APIVersion: "platform.installer/event/v1alpha1", Kind: "ExecutionEvent", RunID: options.runID, Sequence: 10, EventType: "TASK_COMPLETED", Status: "CHANGED", Host: "node1", Task: &executionnode.ExecutionEventTask{UUID: "task-1"}, Redaction: executionnode.ExecutionRedaction{Applied: true}}
			factory := func(watchOptions) (watchBackend, error) {
				// Identity must be available even if backend construction/SSH stalls.
				var identity struct{ RunID, NodeID, MirrorPath string }
				if err := json.Unmarshal(diagnostics.Bytes(), &identity); err != nil || identity.RunID != options.runID || identity.NodeID != "external-192.0.2.1" || !strings.HasSuffix(identity.MirrorPath, "events.jsonl") {
					t.Fatalf("identity missing: %s", diagnostics.String())
				}
				return watchBackend{
					subscribe: func(ctx context.Context, node executionnode.Node, run string, after int) (watchStream, error) {
						if _, deadline := ctx.Deadline(); deadline {
							t.Fatal("watch has preparation timeout")
						}
						if node.ID != identity.NodeID || run != options.runID || after != 9 {
							t.Fatal("incorrect subscription")
						}
						events := make(chan executionnode.ExecutionEvent, 1)
						events <- event
						close(events)
						errs := make(chan error, 1)
						if tc.observerErr != nil {
							errs <- tc.observerErr
						}
						close(errs)
						return watchStream{events, errs, func() { closed = true }}, nil
					},
					getRun: func(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error) {
						return executionnode.ExecutionRun{RunID: options.runID, State: tc.state}, tc.resultErr
					},
				}, nil
			}
			if code := executionWatch(context.Background(), options, &out, &diagnostics, factory); code != tc.want {
				t.Fatalf("code %d want %d: %s", code, tc.want, diagnostics.String())
			}
			if !closed {
				t.Fatal("subscription not detached")
			}
			var decoded executionnode.ExecutionEvent
			if err := json.Unmarshal(out.Bytes(), &decoded); err != nil || decoded.Task == nil || decoded.Task.UUID != "task-1" || decoded.Sequence != 10 {
				t.Fatalf("typed JSON: %s", out.String())
			}
			if strings.Contains(diagnostics.String(), "PRIVATE") {
				t.Fatal("private data leaked")
			}
		})
	}
}

func TestWatchInvalidInput(t *testing.T) {
	for _, mutate := range []func(*watchOptions){
		func(o *watchOptions) { o.runID = "" }, func(o *watchOptions) { o.runID = "../escape" },
		func(o *watchOptions) { o.after = -1 }, func(o *watchOptions) { o.port = 65536 },
		func(o *watchOptions) { o.identity = "" }, func(o *watchOptions) { o.runtimeRoot = "" },
		func(o *watchOptions) { o.nodeID = "bad\nidentity" },
	} {
		options := testWatchOptions(t)
		mutate(&options)
		if code := executionWatch(context.Background(), options, io.Discard, io.Discard, func(watchOptions) (watchBackend, error) {
			t.Fatal("invalid input reached backend")
			return watchBackend{}, nil
		}); code != 2 {
			t.Fatalf("code %d", code)
		}
	}
}

func TestWatchRejectsUnsafeUsernameBeforeBackend(t *testing.T) {
	for _, user := range []string{"", "-root", "-oProxyCommand=command", "user name", " user", "user\tname", "user\nname", "user\x00", "user@host", "user/name", "user\\name", "user:name", "user;command", "user$name", ".user", "юзер"} {
		t.Run(user, func(t *testing.T) {
			options := testWatchOptions(t)
			options.user = user
			var out, diagnostics bytes.Buffer
			code := executionWatch(context.Background(), options, &out, &diagnostics, func(watchOptions) (watchBackend, error) {
				t.Fatal("unsafe username reached backend")
				return watchBackend{}, nil
			})
			if code != 2 || out.Len() != 0 || diagnostics.String() != "EXECUTION_WATCH_INPUT_INVALID\n" {
				t.Fatalf("code=%d stdout=%q diagnostics=%q", code, out.String(), diagnostics.String())
			}
		})
	}
}

func TestWatchOrdinaryUsernameSyntax(t *testing.T) {
	for _, user := range []string{"root", "platform-automation", "User01", "_service", "service.account", "machine$", "123user"} {
		if !safeWatchUsername(user) {
			t.Errorf("ordinary username rejected: %q", user)
		}
	}
}

func TestWatchCancellationDetaches(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	closed := false
	code := executionWatch(ctx, testWatchOptions(t), io.Discard, io.Discard, func(watchOptions) (watchBackend, error) {
		return watchBackend{subscribe: func(context.Context, executionnode.Node, string, int) (watchStream, error) {
			cancel()
			return watchStream{make(chan executionnode.ExecutionEvent), make(chan error), func() { closed = true }}, nil
		}, getRun: func(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error) {
			t.Fatal("query after cancellation")
			return executionnode.ExecutionRun{}, nil
		}}, nil
	})
	if code != 130 || !closed {
		t.Fatalf("code=%d detached=%v", code, closed)
	}
}

type failedWatchWriter struct{}

func (failedWatchWriter) Write([]byte) (int, error) { return 0, errors.New("PRIVATE-write") }

func TestWatchSetupAndOutputFailures(t *testing.T) {
	for _, stage := range []string{"identity", "factory", "subscribe", "stdout"} {
		t.Run(stage, func(t *testing.T) {
			var diagnostics bytes.Buffer
			var stderr io.Writer = &diagnostics
			if stage == "identity" {
				stderr = failedWatchWriter{}
			}
			code := executionWatch(context.Background(), testWatchOptions(t), failedWatchWriter{}, stderr, func(watchOptions) (watchBackend, error) {
				if stage == "identity" {
					t.Fatal("backend before identity")
				}
				if stage == "factory" {
					return watchBackend{}, errors.New("PRIVATE-factory")
				}
				return watchBackend{subscribe: func(context.Context, executionnode.Node, string, int) (watchStream, error) {
					if stage == "subscribe" {
						return watchStream{}, errors.New("PRIVATE-subscribe")
					}
					events := make(chan executionnode.ExecutionEvent, 1)
					events <- executionnode.ExecutionEvent{}
					return watchStream{events, nil, func() {}}, nil
				}}, nil
			})
			if code != 3 || strings.Contains(diagnostics.String(), "PRIVATE") {
				t.Fatalf("code=%d diagnostics=%s", code, diagnostics.String())
			}
		})
	}
}

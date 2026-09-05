package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
	"unicode"

	"platform-installer/internal/executionnode"
)

type watchOptions struct {
	runID, nodeID, runtimeRoot                       string
	address, user, identity, knownHosts, fingerprint string
	port                                             uint
	after                                            int
}

type watchStream struct {
	events <-chan executionnode.ExecutionEvent
	errors <-chan error
	close  func()
}

// Only observation operations are exposed: detaching cannot cancel a remote run.
type watchBackend struct {
	subscribe func(context.Context, executionnode.Node, string, int) (watchStream, error)
	getRun    func(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error)
}

func newWatchBackend(options watchOptions) (watchBackend, error) {
	transport := executionnode.OpenSSHTransport{Identity: fileIdentity{options.identity}}
	observer, err := executionnode.NewRunObserver(transport, options.runtimeRoot)
	if err != nil {
		return watchBackend{}, err
	}
	return watchBackend{
		subscribe: func(ctx context.Context, node executionnode.Node, runID string, after int) (watchStream, error) {
			sub, err := observer.SubscribeAfter(ctx, node, runID, after, 256)
			if err != nil {
				return watchStream{}, err
			}
			return watchStream{sub.Events, sub.Errors, sub.Close}, nil
		},
		getRun: transport.GetExecution,
	}, nil
}

func executionWatch(ctx context.Context, options watchOptions, stdout, stderr io.Writer, factory func(watchOptions) (watchBackend, error)) int {
	if options.nodeID == "" {
		options.nodeID = "external-" + options.address
	}
	path, err := executionnode.EventMirrorPath(options.runtimeRoot, options.runID)
	if err != nil || options.runtimeRoot == "" || options.after < 0 || options.port == 0 || options.port > 65535 ||
		!safeWatchIdentity(options.nodeID) || !safeWatchIdentity(options.address) || !safeWatchUsername(options.user) || options.identity == "" || options.knownHosts == "" || options.fingerprint == "" {
		fmt.Fprintln(stderr, "EXECUTION_WATCH_INPUT_INVALID")
		return 2
	}
	// Printed before opening a mirror or contacting SSH. This is the intended
	// local derived mirror path; subsequent errors explicitly report unavailability.
	if err := json.NewEncoder(stderr).Encode(struct {
		RunID      string `json:"runId"`
		NodeID     string `json:"nodeId"`
		MirrorPath string `json:"mirrorPath"`
	}{options.runID, options.nodeID, path}); err != nil {
		return 3
	}
	backend, err := factory(options)
	if err != nil {
		fmt.Fprintln(stderr, "EXECUTION_WATCH_OBSERVER_FAILED")
		return 3
	}
	stream, err := backend.subscribe(ctx, executionnode.Node{ID: options.nodeID, Address: options.address, User: options.user, Port: uint16(options.port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: options.knownHosts, Fingerprint: options.fingerprint}}, options.runID, options.after)
	if err != nil {
		if ctx.Err() != nil {
			return 130
		}
		fmt.Fprintln(stderr, "EXECUTION_WATCH_OBSERVER_FAILED")
		return 3
	}
	defer stream.close()
	encoder := json.NewEncoder(stdout)
	degraded := false
	for stream.events != nil || stream.errors != nil {
		if ctx.Err() != nil {
			return 130
		}
		select {
		case <-ctx.Done():
			return 130
		case event, ok := <-stream.events:
			if !ok {
				stream.events = nil
				continue
			}
			if err := encoder.Encode(event); err != nil {
				fmt.Fprintln(stderr, "EXECUTION_WATCH_OUTPUT_FAILED")
				return 3
			}
		case err, ok := <-stream.errors:
			if !ok {
				stream.errors = nil
				continue
			}
			var observed *executionnode.ObserverError
			if errors.As(err, &observed) && observed.Code == executionnode.ObserverTransportFailure {
				fmt.Fprintln(stderr, "EXECUTION_OBSERVER_TRANSPORT_FAILURE: reconnecting")
				continue
			}
			// Do not print arbitrary errors: they may contain transport credentials.
			fmt.Fprintln(stderr, "EXECUTION_WATCH_OBSERVER_DEGRADED: local stream may be incomplete")
			degraded = true
		}
	}
	if ctx.Err() != nil {
		return 130
	}
	// A checkpoint may exclude RUN_COMPLETED. Query the authoritative result
	// after the observer drains, rather than inferring success from channel close.
	run, err := backend.getRun(ctx, executionnode.Node{ID: options.nodeID, Address: options.address, User: options.user, Port: uint16(options.port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: options.knownHosts, Fingerprint: options.fingerprint}}, options.runID)
	if ctx.Err() != nil {
		return 130
	}
	if err != nil || run.RunID != options.runID {
		fmt.Fprintln(stderr, "EXECUTION_WATCH_RESULT_UNAVAILABLE")
		return 3
	}
	code := 3
	switch run.State {
	case "SUCCEEDED":
		code = 0
	case "FAILED", "CANCELLED", "INTERRUPTED":
		code = 1
	default:
		fmt.Fprintln(stderr, "EXECUTION_WATCH_TERMINAL_RESULT_UNAVAILABLE")
		return 3
	}
	fmt.Fprintln(stderr, "remoteOutcome="+run.State)
	if degraded {
		return 3
	}
	return code
}

func safeWatchIdentity(value string) bool {
	return value != "" && len(value) <= 256 && !strings.ContainsAny(value, "@/\\") && strings.IndexFunc(value, func(r rune) bool { return unicode.IsControl(r) || unicode.IsSpace(r) }) < 0
}

// Restrict the SSH destination's user component to ordinary account syntax.
// In particular, user@address must never begin with an SSH option prefix.
func safeWatchUsername(value string) bool {
	if value == "" || len(value) > 256 {
		return false
	}
	for i, c := range value {
		if c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '_' {
			continue
		}
		if i > 0 && (c == '-' || c == '.' || c == '$' && i == len(value)-1) {
			continue
		}
		return false
	}
	return true
}

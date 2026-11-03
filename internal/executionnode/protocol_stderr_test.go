package executionnode

import (
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
)

// A real subprocess exercises the production OS runner on Windows and Linux,
// including independent stdout/stderr pipes. It never opens an SSH connection.
func TestProtocolStderrProcess(t *testing.T) {
	if os.Getenv("PLATFORM_INSTALLER_PROTOCOL_STDERR_TEST") != "1" {
		return
	}
	stage := os.Args[len(os.Args)-1]
	fmt.Fprintln(os.Stderr, "synthetic PAM/SSH notice; private-stderr-canary")
	switch stage {
	case "release":
		fmt.Println("/var/lib/platform-installer/runtime/releases/" + strings.Repeat("a", 64))
	case "state":
		fmt.Println("BUNDLE_DIGEST=sha256:" + strings.Repeat("b", 64))
	case "stdout-overflow":
		fmt.Print(strings.Repeat("x", 20000))
	case "stderr-overflow":
		fmt.Fprint(os.Stderr, strings.Repeat("x", 20000))
	case "failed":
		fmt.Print(`{"status":"READY"}`)
		os.Exit(1)
	default:
		fmt.Print(`{"status":"READY"}`)
	}
	os.Exit(0)
}

type protocolStderrRunner struct {
	executable string
	stage      string
}

func (r protocolStderrRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	return r.RunBounded(ctx, name, args, input, 65536)
}

func (r protocolStderrRunner) RunBounded(ctx context.Context, _ string, args []string, input []byte, limit int) ([]byte, error) {
	stage := r.stage
	if stage == "" {
		switch command := strings.Join(args, " "); {
		case strings.Contains(command, "readlink"):
			stage = "release"
		case strings.Contains(command, " cat "):
			stage = "state"
		default:
			stage = "protocol"
		}
	}
	return (osRunner{}).RunBounded(ctx, r.executable,
		[]string{"-test.run=^TestProtocolStderrProcess$", "--", stage}, input, limit)
}

func protocolStderrFixture(t *testing.T) protocolStderrRunner {
	t.Helper()
	t.Setenv("PLATFORM_INSTALLER_PROTOCOL_STDERR_TEST", "1")
	executable, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	return protocolStderrRunner{executable: executable}
}

func TestRuntimeProtocolAcceptsSuccessfulSSHNoticesOnlyOnStderr(t *testing.T) {
	runner := protocolStderrFixture(t)
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	response, err := transport.runtimeProtocol(context.Background(), testNode(), map[string]any{"operation": "GetCapabilities"})
	if err != nil || response["status"] != "READY" {
		t.Fatalf("successful stderr notice corrupted release/state/JSON: response=%v err=%v", response, err)
	}
}

func TestBoundedProtocolStreamsStillRejectProcessFailureAndOverflow(t *testing.T) {
	runner := protocolStderrFixture(t)
	for _, stage := range []string{"failed", "stdout-overflow", "stderr-overflow"} {
		t.Run(stage, func(t *testing.T) {
			runner.stage = stage
			output, err := runner.RunBounded(context.Background(), "fixture", nil, nil, 1024)
			if err == nil || len(output) > 1024 || strings.Contains(string(output), "private-stderr-canary") {
				t.Fatalf("failed/overflowing command was accepted or private stderr escaped: bytes=%d err=%v", len(output), err)
			}
			if stage != "failed" && err.Error() != "EXECUTION_NODE_OUTPUT_LIMIT" {
				t.Fatal("missing output limit error")
			}
		})
	}
}

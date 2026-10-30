package executionnode

import (
	"context"
	"errors"
	"fmt"
	"platform-installer/internal/executionbundle"
	"strings"
	"testing"
	"time"
)

type preparationFailureRunner struct{}

func (preparationFailureRunner) Run(context.Context, string, []string, []byte) ([]byte, error) {
	return []byte("private output"), errors.New("private transport error")
}

func TestPreparationRetainsDeadlineAcrossTransportRedaction(t *testing.T) {
	ctx, cancel := context.WithDeadline(context.Background(), time.Now().Add(-time.Second))
	defer cancel()
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: preparationFailureRunner{}}
	_, err := transport.ActivateStagedRuntime(ctx, testNode(), "/var/tmp/platform-installer-bootstrap-"+strings.Repeat("a", 32), executionbundle.Verified{Digest: "sha256:" + strings.Repeat("b", 64)})
	var failure *RuntimePreparationError
	if !errors.As(err, &failure) || failure.Finding.Code != "EXECUTION_RUNTIME_PREPARATION_TIMEOUT" || !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("deadline lost: %v", err)
	}
}

func TestPreparationQuotesAllEightRemoteArgumentsWithMultiplePlatforms(t *testing.T) {
	for _, password := range []bool{false, true} {
		runner := &recordingRunner{}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		if password {
			transport.SudoPassword = func(ctx context.Context, consume func([]byte) error) error { return consume([]byte("TEST_SUDO_VALUE")) }
		}
		bundle := executionbundle.Verified{Digest: "sha256:" + strings.Repeat("b", 64), Manifest: executionbundle.Manifest{
			BundleVersion: "test", Platforms: []executionbundle.Platform{{OS: "redos", Version: "8.0", Architecture: "x86_64"}, {OS: "redos", Version: "8.0.3", Architecture: "x86_64"}},
			Components: []executionbundle.Component{{Path: runtimeBootstrapComponent}},
		}}
		_, err := transport.ActivateStagedRuntime(context.Background(), testNode(), "/var/tmp/platform-installer-bootstrap-"+strings.Repeat("a", 32), bundle)
		if err != nil {
			t.Fatal(err)
		}
		if len(runner.calls) != 2 {
			t.Fatalf("expected bootstrap and activation, got %d calls", len(runner.calls))
		}
		for _, call := range runner.calls {
			if len(call.args) < 2 || call.args[len(call.args)-2] != "'redos:8.0:x86_64 redos:8.0.3:x86_64'" || call.args[len(call.args)-1] != "'1'" {
				t.Fatalf("remote argument framing lost for sudo password=%t", password)
			}
			if strings.Contains(strings.Join(call.args, " "), "TEST_SUDO_VALUE") {
				t.Fatal("sudo value in argv")
			}
		}
	}
}

func TestPreparationReasonUsesClosedOutputTokensOnly(t *testing.T) {
	for _, output := range []string{"private password=SECRET", "EXECUTION_BOOTSTRAP_NOT_A_REAL_REASON", "prefix EXECUTION_BOOTSTRAP_RPM_INVALID secret"} {
		err := runtimePreparationFailure("bootstrap", []byte(output), errors.New("PRIVATE ERROR"))
		var typed *RuntimePreparationError
		if !errors.As(err, &typed) || typed.Finding.Code != "EXECUTION_BOOTSTRAP_COMMAND_FAILED" || strings.Contains(typed.Finding.SafeMessage, "SECRET") {
			t.Fatal("unsafe bootstrap failure")
		}
	}
	err := runtimePreparationFailure("bootstrap", []byte("private\nEXECUTION_BOOTSTRAP_REPOSITORY_DOWNLOAD_FAILED\nEXECUTION_BOOTSTRAP_COMMAND_FAILED\n"), errors.New("private"))
	if err.Error() != "EXECUTION_BOOTSTRAP_REPOSITORY_DOWNLOAD_FAILED" {
		t.Fatal(err)
	}
}

func TestServicePreviewAcceptsKnownAdditiveCapabilitiesOnly(t *testing.T) {
	c := map[string]any{"supportedOperations": []any{"BuildServiceConfigurationPreview"}, "serviceConfigurationPreview": map[string]any{"protocol": "BuildServiceConfigurationPreview/v1alpha1", "maxResponseBytes": float64(1024 * 1024)}}
	for version := 5; version <= 11; version++ {
		c["apiVersion"] = fmt.Sprintf("platform.installer/execution-capabilities/v1alpha%d", version)
		if !serviceConfigurationPreviewSupported(c) {
			t.Fatalf("capabilities v%d rejected", version)
		}
	}
	c["apiVersion"] = "platform.installer/execution-capabilities/v1alpha12"
	if serviceConfigurationPreviewSupported(c) {
		t.Fatal("unknown future capability accepted")
	}
	c["apiVersion"] = "platform.installer/execution-capabilities/v1alpha11"
	c["serviceConfigurationPreview"].(map[string]any)["protocol"] = "unexpected"
	if serviceConfigurationPreviewSupported(c) {
		t.Fatal("invalid protocol accepted")
	}
}

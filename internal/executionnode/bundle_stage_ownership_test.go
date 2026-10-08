package executionnode

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
)

func TestBundleStageIsPrivateFreshAndArchiveInsideClaimedDirectory(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte("fixture"), 0600); err != nil {
		t.Fatal(err)
	}
	runner := &recordingRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	bundle := executionbundle.Verified{Root: root, Digest: "sha256:" + strings.Repeat("a", 64)}
	first, err := transport.StageVerifiedBundle(context.Background(), testNode(), bundle)
	if err != nil {
		t.Fatal(err)
	}
	second, err := transport.StageVerifiedBundle(context.Background(), testNode(), bundle)
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatal("bundle attempts share staging ownership")
	}
	claim := runner.calls[0].input
	if !strings.Contains(claim, "mkdir -m 0700") || !strings.Contains(claim, "stat -c %a /var/tmp") || strings.Contains(claim, "sudo") || strings.Contains(claim, "rm -rf") || strings.Contains(claim, "chmod") || strings.Contains(claim, "chown") {
		t.Fatal("stage must claim a fresh private directory without changing shared permissions")
	}
	if runner.calls[1].name != "scp" || !strings.HasSuffix(runner.calls[1].args[len(runner.calls[1].args)-1], first+"/bundle.tar") {
		t.Fatal("archive written outside owned staging directory")
	}
}

func TestReadinessBlocksPreparationWithoutNoninteractiveSudo(t *testing.T) {
	transport := &fakeTransport{inspection: Inspection{State: PreparationRequired, OS: "redos", OSVersion: "8.0.3", Architecture: "x86_64", FreeBytes: 100}}
	inspection, err := NewService(transport).InspectExecutionNode(context.Background(), testNode())
	if err != nil || inspection.State != Broken || len(inspection.Findings) != 1 || inspection.Findings[0].Code != "EXECUTION_NODE_ELEVATION_REQUIRED" {
		t.Fatalf("%+v %v", inspection, err)
	}
	if got := preparationSteps(requiredState(transport.inspection, executionbundle.Verified{})); len(got) != 1 || got[0].Action != "BLOCKED" || got[0].Mutates {
		t.Fatalf("preparation allowed without sudo: %+v", got)
	}
}

func TestInvalidBundleStageCannotActivateOrCleanOutsideNamespace(t *testing.T) {
	runner := &recordingRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	for _, stage := range []string{"/var/tmp/platform-installer/bootstrap/old", "/var/tmp/platform-installer-bootstrap-../etc", "/var/tmp/platform-installer-bootstrap-" + strings.Repeat("A", 32), "/var/tmp/platform-installer-bootstrap-" + strings.Repeat("a", 32) + "/child"} {
		if _, err := transport.ActivateStagedRuntime(context.Background(), testNode(), stage, executionbundle.Verified{}); err == nil {
			t.Fatal("invalid activation path accepted")
		}
		if err := transport.DiscardStagedRuntime(context.Background(), testNode(), stage); err == nil {
			t.Fatal("invalid cleanup path accepted")
		}
	}
	if len(runner.calls) != 0 {
		t.Fatal("invalid path reached remote command")
	}
}

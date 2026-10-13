package executionnode

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
)

type bootstrapCancelRunner struct {
	calls  []recordedCommand
	cancel context.CancelFunc
}

func (r *bootstrapCancelRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name, args, string(input)})
	if len(r.calls) == 1 {
		r.cancel()
	}
	return nil, nil
}

func TestCancelledBootstrapNeverDispatchesActivation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	runner := &bootstrapCancelRunner{cancel: cancel}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.ActivateStagedRuntime(ctx, testNode(), "/var/tmp/platform-installer-bootstrap-"+strings.Repeat("a", 32), executionbundle.Verified{Digest: "sha256:" + strings.Repeat("b", 64)})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("err=%v", err)
	}
	for _, call := range runner.calls {
		if strings.Contains(call.input, "switching=1") {
			t.Fatal("cancelled request activated runtime")
		}
	}
}

type noTarRunner struct{ recordingRunner }

func (r *noTarRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	result, err := r.recordingRunner.Run(ctx, name, args, input)
	if strings.Contains(string(input), "TAR=1") {
		return []byte("TAR=0\n"), nil
	}
	return result, err
}

func TestBundleWithoutTarUsesExistingDirectoryTransfer(t *testing.T) {
	root := t.TempDir()
	for _, dir := range []string{"ansible-core", "catalog", "contracts", "runtime", "services"} {
		if err := os.Mkdir(filepath.Join(root, dir), 0700); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte("fixture"), 0600); err != nil {
		t.Fatal(err)
	}
	runner := &noTarRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.StageVerifiedBundle(context.Background(), testNode(), executionbundle.Verified{Root: root})
	if err != nil {
		t.Fatal(err)
	}
	copies := 0
	for _, call := range runner.calls {
		if call.name == "scp" {
			copies++
			if strings.Contains(strings.Join(call.args, " "), "bundle.tar") {
				t.Fatal("tar archive used without tar")
			}
		}
	}
	if copies != 6 {
		t.Fatalf("directory/manifest copies=%d", copies)
	}
}

func TestPreparationDisclosesRuntimePackageStep(t *testing.T) {
	for _, step := range preparationSteps(Unprepared) {
		if step.ID == "ensure-runtime-packages" {
			return
		}
	}
	t.Fatal("runtime package installation absent from preparation plan")
}

func TestNativeRuntimeActivationPreservesReleaseAndSerializesAttempts(t *testing.T) {
	if runtime.GOOS != "linux" || os.Geteuid() != 0 {
		t.Skip("requires Linux root in isolated QA workspace")
	}
	root := t.TempDir()
	base := filepath.Join(root, "varlib", "platform-installer")
	managed := filepath.Join(base, "runtime")
	stage := filepath.Join(root, "stage-"+strings.Repeat("a", 32))
	old := filepath.Join(managed, "releases", strings.Repeat("b", 64))
	for _, dir := range []string{stage, old, filepath.Join(managed, "state"), filepath.Join(root, "bin")} {
		if err := os.MkdirAll(dir, 0750); err != nil {
			t.Fatal(err)
		}
	}
	active := []byte("previous active metadata\n")
	if err := os.WriteFile(filepath.Join(old, "sentinel"), []byte("previous release"), 0640); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(managed, "state", "active"), active, 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(old, filepath.Join(managed, "current")); err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{runtimeBootstrapComponent: []byte("#!/bin/sh\nexit 0\n"), "ansible-core/playbooks/execution-capabilities.yml": []byte("fixture"), "ansible-core/tools/execution_lifecycle.py": []byte("fixture")}
	bundle := executionbundle.Verified{Manifest: executionbundle.Manifest{BundleVersion: "test", CoreVersion: "0.1.0", BootstrapProtocol: "v1alpha1", Platforms: []executionbundle.Platform{{OS: "redos", Version: "8", Architecture: "x86_64"}}}}
	for relative, data := range files {
		target := filepath.Join(stage, filepath.FromSlash(relative))
		if err := os.MkdirAll(filepath.Dir(target), 0750); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(target, data, 0640); err != nil {
			t.Fatal(err)
		}
		sum := sha256.Sum256(data)
		bundle.Manifest.Components = append(bundle.Manifest.Components, executionbundle.Component{Path: relative, Size: int64(len(data)), SHA256: "sha256:" + hex.EncodeToString(sum[:])})
	}
	manifest := []byte("fixture manifest")
	sum := sha256.Sum256(manifest)
	bundle.Digest = "sha256:" + hex.EncodeToString(sum[:])
	if err := os.WriteFile(filepath.Join(stage, "manifest.yaml"), manifest, 0640); err != nil {
		t.Fatal(err)
	}
	for name, script := range map[string]string{"python3": "#!/bin/sh\nexit 0\n", "ansible-playbook": "#!/bin/sh\n[ \"${CAP_FAIL:-0}\" = 0 ]\n"} {
		if err := os.WriteFile(filepath.Join(root, "bin", name), []byte(script), 0700); err != nil {
			t.Fatal(err)
		}
	}
	bootstrap, activation := runtimePreparationScripts(bundle)
	adapt := func(script string) string {
		script = strings.ReplaceAll(script, "/var/lib/platform-installer", base)
		return strings.ReplaceAll(script, "/var/tmp/platform-installer-bootstrap-", filepath.Join(root, "stage-"))
	}
	args := []string{stage, managed, bundle.Digest, "test", "0.1.0", "v1alpha1", "redos:8:x86_64", "1"}
	run := func(script string, fail bool) error {
		command := exec.Command("sh", append([]string{"-s", "--"}, args...)...)
		command.Stdin = strings.NewReader(adapt(script))
		command.Env = append(os.Environ(), "PATH="+filepath.Join(root, "bin")+":"+os.Getenv("PATH"))
		if fail {
			command.Env = append(command.Env, "CAP_FAIL=1")
		}
		output, err := command.CombinedOutput()
		if err != nil {
			t.Logf("bounded fixture result: %s", output)
		}
		return err
	}
	if err := run(bootstrap, false); err != nil {
		t.Fatal(err)
	}
	if err := run(activation, true); err == nil {
		t.Fatal("failed capabilities accepted")
	}
	current, err := os.Readlink(filepath.Join(managed, "current"))
	if err != nil || current != old {
		t.Fatal("failed candidate switched current")
	}
	observed, _ := os.ReadFile(filepath.Join(managed, "state", "active"))
	if string(observed) != string(active) {
		t.Fatal("failed candidate replaced metadata")
	}
	if err := run(bootstrap, false); err != nil {
		t.Fatal(err)
	}
	if err := run(activation, false); err != nil {
		t.Fatal(err)
	}
	current, _ = os.Readlink(filepath.Join(managed, "current"))
	committed, _ := os.ReadFile(filepath.Join(managed, "state", "active"))
	contents, _ := os.ReadFile(filepath.Join(current, runtimeBootstrapComponent))
	if err := run(bootstrap, false); err != nil {
		t.Fatal(err)
	}
	if err := run(activation, true); err == nil {
		t.Fatal("same-digest failing handshake accepted")
	}
	now, _ := os.Readlink(filepath.Join(managed, "current"))
	metadata, _ := os.ReadFile(filepath.Join(managed, "state", "active"))
	bytes, _ := os.ReadFile(filepath.Join(current, runtimeBootstrapComponent))
	if now != current || string(metadata) != string(committed) || string(bytes) != string(contents) {
		t.Fatal("same digest retry damaged active runtime")
	}
	lock := exec.Command("flock", "-x", filepath.Join(managed, "state", "prepare.lock"), "sh", "-c", "echo LOCKED; read answer")
	stdin, err := lock.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	pipe, err := lock.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err = lock.Start(); err != nil {
		t.Fatal(err)
	}
	buffer := make([]byte, 7)
	if _, err = pipe.Read(buffer); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = stdin.Close(); _ = lock.Wait() }()
	if err := run(bootstrap, false); err == nil {
		t.Fatal("overlapping preparation ignored lock")
	}
	now, _ = os.Readlink(filepath.Join(managed, "current"))
	if now != current {
		t.Fatal("overlapping preparation switched current")
	}
}

package executionnode

import (
	"context"
	"crypto/sha256"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestProjectTransferIdentityMatchesArchiveAndChangesWithAssets(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	asset := filepath.Join(root, "inventory", "custom.txt")
	if err := os.WriteFile(asset, []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	slot, digest, err := projectTransferIdentity(root)
	if err != nil {
		t.Fatal(err)
	}
	archive, err := createProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archive)
	data, err := os.ReadFile(archive)
	if err != nil {
		t.Fatal(err)
	}
	if got := fmt.Sprintf("sha256:%x", sha256.Sum256(data)); got != digest {
		t.Fatalf("fingerprint mismatch: %s != %s", got, digest)
	}
	if err := os.WriteFile(asset, []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	nextSlot, next, err := projectTransferIdentity(root)
	if err != nil || nextSlot != slot || next == digest {
		t.Fatalf("asset change not detected: %v", err)
	}
}

type cacheHitRunner struct{ protocolRunner }

func (r *cacheHitRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), "project-archives") {
		r.calls = append(r.calls, recordedCommand{name: name, args: args, input: string(input)})
		return []byte("HIT"), nil
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}

func TestProjectTransferCacheHitSendsNoArchive(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	runner := &cacheHitRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	if err := transport.stagePlanProject(context.Background(), testNode(), root, "installer-123", "snapshot"); err != nil {
		t.Fatal(err)
	}
	if len(runner.calls) != 1 || runner.calls[0].name != "ssh" {
		t.Fatal("cache hit uploaded or recreated an archive")
	}
}

func TestProjectTransferRejectsChangedArchiveBeforeUpload(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	slot, digest, err := projectTransferIdentity(root)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "inventory", "new.yml"), []byte("all: {}"), 0600); err != nil {
		t.Fatal(err)
	}
	archive, err := createProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archive)
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err = transport.stageProjectArchive(context.Background(), testNode(), archive, "installer-123", "snapshot", "", slot, digest)
	if err == nil || err.Error() != "PROJECT_REVISION_CHANGED" || len(runner.calls) != 0 {
		t.Fatalf("changed source uploaded: %v", err)
	}
}

// Runs the actual fixed shell program in an isolated filesystem on Linux.
// No installation run, service or real Core request is involved.
func TestNativeProjectTransferCache(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("native Linux shell QA")
	}
	if _, err := exec.LookPath("flock"); err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "inventory", "hosts.yml"), []byte("all: {}\n"), 0600); err != nil {
		t.Fatal(err)
	}
	slot, digest, err := projectTransferIdentity(root)
	if err != nil {
		t.Fatal(err)
	}
	archive, err := createProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archive)
	state := filepath.ToSlash(filepath.Join(t.TempDir(), "execution"))
	script := strings.ReplaceAll(projectArchiveCacheScript, "/var/lib/platform-installer/execution", state)
	invoke := func(action, run string) string {
		t.Helper()
		cmd := exec.Command("sh", "-s", "--", slot, digest, action, run, "snapshot", archive)
		cmd.Stdin = strings.NewReader(script)
		out, err := cmd.CombinedOutput()
		if err != nil {
			t.Fatalf("cache %s: %v: %s", action, err, out)
		}
		return strings.TrimSpace(string(out))
	}
	if invoke("lookup", "installer-100") != "MISS" {
		t.Fatal("cold hit")
	}
	invoke("publish", "installer-100")
	for _, run := range []string{"installer-101", "installer-102"} {
		if invoke("lookup", run) != "HIT" {
			t.Fatal("repeat miss")
		}
		data, err := os.ReadFile(filepath.Join(state, "runs", run, "project", "inventory", "hosts.yml"))
		if err != nil || string(data) != "all: {}\n" {
			t.Fatal("extracted source differs")
		}
		if _, err := os.Stat(filepath.Join(state, "runs", run, ".snapshot-owner.json")); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(state, "project-archives", slot, "project.tar"), []byte("corrupt"), 0600); err != nil {
		t.Fatal(err)
	}
	if invoke("lookup", "installer-103") != "MISS" {
		t.Fatal("corrupt archive reused")
	}
	invoke("publish", "installer-103")
	if invoke("lookup", "installer-103") != "HIT" {
		t.Fatal("repair upload not reused")
	}
	completed := make(chan error, 4)
	for i := 0; i < 4; i++ {
		go func(i int) {
			cmd := exec.Command("sh", "-s", "--", slot, digest, "lookup", fmt.Sprintf("installer-%d", 200+i), "snapshot", archive)
			cmd.Stdin = strings.NewReader(script)
			out, err := cmd.CombinedOutput()
			if err == nil && strings.TrimSpace(string(out)) != "HIT" {
				err = fmt.Errorf("concurrent lookup missed")
			}
			completed <- err
		}(i)
	}
	for i := 0; i < 4; i++ {
		if err := <-completed; err != nil {
			t.Fatal(err)
		}
	}
}

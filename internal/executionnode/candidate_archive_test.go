package executionnode

import (
	"archive/tar"
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"testing"
)

func writeCandidateFixture(t *testing.T, root string) {
	t.Helper()
	files := map[string]string{
		"project.yml":         "metadata: {id: project-1}\n",
		"ansible.cfg":         managedCandidateAnsibleConfig,
		"inventory/hosts.yml": "all: {hosts: {node1: {ansible_host: 192.0.2.10}}}\n",
	}
	for logical, content := range files {
		path := filepath.Join(root, filepath.FromSlash(logical))
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}
}

func TestCandidateArchiveIncludesOnlyCanonicalDocuments(t *testing.T) {
	root := t.TempDir()
	writeCandidateFixture(t, root)
	for logical, content := range map[string]string{
		"inventory/group_vars/all/platform-installer.yml": "platform_desired_state: {}\n",
		"inventory/host_vars/node1/override.json":         "{}\n",
		"inventory/group_vars/all/private.pem":            "must-not-cross-boundary\n",
		"notes.txt":                                       "must-not-cross-boundary\n",
	} {
		path := filepath.Join(root, filepath.FromSlash(logical))
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}

	archivePath, err := createCandidateProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archivePath)
	archive, err := os.Open(archivePath)
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	reader := tar.NewReader(archive)
	var names []string
	for {
		header, nextErr := reader.Next()
		if errors.Is(nextErr, io.EOF) {
			break
		}
		if nextErr != nil {
			t.Fatal(nextErr)
		}
		if header.Typeflag != tar.TypeReg || header.Linkname != "" {
			t.Fatalf("unsafe tar header: %#v", header)
		}
		names = append(names, header.Name)
	}
	want := []string{"ansible.cfg", "inventory/group_vars/all/platform-installer.yml", "inventory/host_vars/node1/override.json", "inventory/hosts.yml", "project.yml"}
	if !slices.Equal(names, want) {
		t.Fatalf("archive names=%v want=%v", names, want)
	}
}

func TestServiceProjectArchiveExcludesStandaloneVaultCustody(t *testing.T) {
	root := t.TempDir()
	writeCandidateFixture(t, root)
	secret := filepath.Join(root, "secrets", "vault-standalone", "root-token")
	if err := os.MkdirAll(filepath.Dir(secret), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(secret, []byte("vault-token-must-not-be-archived"), 0o600); err != nil {
		t.Fatal(err)
	}
	archivePath, err := createProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archivePath)
	archive, err := os.ReadFile(archivePath)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(archive, []byte("vault-token-must-not-be-archived")) || bytes.Contains(archive, []byte("secrets/")) {
		t.Fatal("standalone Vault custody crossed the project archive boundary")
	}
}

func TestCandidateArchiveRejectsUnsafeConfigAndHardlink(t *testing.T) {
	t.Run("config", func(t *testing.T) {
		root := t.TempDir()
		writeCandidateFixture(t, root)
		if err := os.WriteFile(filepath.Join(root, "ansible.cfg"), []byte("[defaults]\nstrategy_plugins = ./plugins\n"), 0o600); err != nil {
			t.Fatal(err)
		}
		if _, err := createCandidateProjectArchive(root); err == nil || !strings.Contains(err.Error(), "ANSIBLE_CONFIG") {
			t.Fatalf("unsafe config error=%v", err)
		}
	})

	t.Run("hardlink", func(t *testing.T) {
		root := t.TempDir()
		writeCandidateFixture(t, root)
		target := filepath.Join(root, "inventory", "group_vars", "linked.yml")
		if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.Link(filepath.Join(root, "project.yml"), target); err != nil {
			t.Skipf("hardlinks unsupported: %v", err)
		}
		if _, err := createCandidateProjectArchive(root); err == nil || !strings.Contains(err.Error(), "HARDLINK") && !strings.Contains(err.Error(), "FILE_UNSAFE") {
			t.Fatalf("hardlink error=%v", err)
		}
	})
}

func TestCandidateArchiveRejectsCaseCollision(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows filesystem fixture is case-insensitive")
	}
	root := t.TempDir()
	writeCandidateFixture(t, root)
	for _, logical := range []string{"inventory/group_vars/all/value.yml", "inventory/group_vars/ALL/value.yml"} {
		path := filepath.Join(root, filepath.FromSlash(logical))
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("{}\n"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := createCandidateProjectArchive(root); err == nil || !strings.Contains(err.Error(), "COLLISION") {
		t.Fatalf("collision error=%v", err)
	}
}

func TestCandidateArchiveLimitsDoNotChangeProductionArchiveSemantics(t *testing.T) {
	root := t.TempDir()
	writeCandidateFixture(t, root)
	large := filepath.Join(root, "inventory", "group_vars", "all", "large.yml")
	if err := os.MkdirAll(filepath.Dir(large), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(large, bytes.Repeat([]byte("x"), 4*1024*1024+1), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := createCandidateProjectArchive(root); err == nil || !strings.Contains(err.Error(), "LIMIT_EXCEEDED") {
		t.Fatalf("candidate archive did not enforce its file limit: %v", err)
	}
	archivePath, err := createProjectArchive(root)
	if err != nil {
		t.Fatalf("candidate-only limit changed the production archive path: %v", err)
	}
	os.Remove(archivePath)
}

func TestCandidatePathLimitDoesNotChangeProductionArchiveSemantics(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("Windows path policy cannot materialize the long-path regression fixture")
	}
	root := t.TempDir()
	writeCandidateFixture(t, root)
	segment := strings.Repeat("a", 180)
	longPath := filepath.Join(root, "inventory", "group_vars", "all", segment, segment, segment, "value.yml")
	if err := os.MkdirAll(filepath.Dir(longPath), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(longPath, []byte("value: true\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := createCandidateProjectArchive(root); err == nil || !strings.Contains(err.Error(), "PATH_INVALID") {
		t.Fatalf("candidate archive did not enforce its logical path limit: %v", err)
	}
	archivePath, err := createProjectArchive(root)
	if err != nil {
		t.Fatalf("candidate-only path limit changed the production archive path: %v", err)
	}
	os.Remove(archivePath)
}

type partialCandidateStageRunner struct {
	protocolRunner
	failAt string
}

func (r *partialCandidateStageRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if r.failAt == "scp" && name == "scp" {
		r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
		return nil, errors.New("scp failed")
	}
	if len(input) == 0 {
		return r.protocolRunner.Run(ctx, name, args, input)
	}
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
	command := string(input)
	if strings.Contains(command, `"operation":"GetCapabilities"`) {
		return []byte(`{"supportedOperations":["BuildProjectSnapshot"],"projectSnapshotRequestVersions":["platform.installer/project-snapshot-request/v1alpha1"]}`), nil
	}
	if strings.Contains(command, "--cleanup-snapshot-run-id") || strings.Contains(command, "rm -rf -- \"$temporary\"") {
		return nil, nil
	}
	if r.failAt == "mkdir" && strings.Contains(command, "mkdir -- \"$1\"") {
		return nil, errors.New("mkdir failed")
	}
	if r.failAt == "extract" && strings.Contains(command, "--stage-candidate-archive") {
		return nil, errors.New("extract failed")
	}
	return []byte(`{"run":{"state":"RUNNING"}}`), nil
}

func (r *partialCandidateStageRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

func TestCandidateStageFailureCleansTemporaryAndRunLocations(t *testing.T) {
	for _, failAt := range []string{"mkdir", "scp", "extract"} {
		t.Run(failAt, func(t *testing.T) {
			root := t.TempDir()
			writeCandidateFixture(t, root)
			runner := &partialCandidateStageRunner{failAt: failAt}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			_, err := transport.BuildCandidateProjectSnapshot(context.Background(), testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}, CandidateProjectSnapshotRequest{
				ProjectIdentity: "project-1", CandidateProjectRevision: "sha256:" + strings.Repeat("a", 64),
				ArtifactLockDigest: "sha256:" + strings.Repeat("b", 64), CatalogLockDigest: "sha256:" + strings.Repeat("c", 64),
			})
			if err == nil {
				t.Fatal("stage failure was not returned")
			}
			if failAt == "mkdir" {
				if runnerCalledUploadCleanup(runner.calls) || runnerCalledCleanup(runner.calls) {
					t.Fatalf("failed ownership claim cleaned another staging location: %#v", runner.calls)
				}
			} else if !runnerCalledUploadCleanup(runner.calls) || runnerCalledCleanup(runner.calls) {
				t.Fatalf("failure cleanup was not limited to the owned upload after %s: %#v", failAt, runner.calls)
			}
		})
	}
}

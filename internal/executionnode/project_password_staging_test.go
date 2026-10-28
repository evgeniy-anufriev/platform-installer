package executionnode

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/sshpassword"
)

type rejectProjectPEM struct{}

func (rejectProjectPEM) IdentityFile(string) (string, error) {
	return "", errors.New("PEM lookup forbidden in password mode")
}

func TestPasswordProjectStagingDoesNotRequirePEM(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: rejectProjectPEM{}, Runner: runner, Password: func(context.Context, func([]byte) error) error { return nil }}
	if err := transport.stagePlanProject(context.Background(), testNode(), root, "installer-123", "snapshot"); err != nil {
		t.Fatal(err)
	}
	for _, call := range runner.calls {
		for _, arg := range call.args {
			if arg == "-i" {
				t.Fatal("password upload retained PEM argument")
			}
		}
	}
	if len(runner.calls) != 5 || runner.calls[2].name != "scp" {
		t.Fatal("project was not uploaded/extracted")
	}
}

func TestProjectUploadFailureCleansOnlyClaimedNamespaceAndRetainsScope(t *testing.T) {
	for _, purpose := range []string{"snapshot", "candidate"} {
		for _, failure := range []string{"mkdir", "scp"} {
			t.Run(purpose+"/"+failure, func(t *testing.T) {
				root := t.TempDir()
				if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
					t.Fatal(err)
				}
				runner := &partialCandidateStageRunner{failAt: failure}
				var scopes []string
				transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner, ContextCommandGuard: func(ctx context.Context) (func(), error) {
					scopes = append(scopes, sshpassword.OperationScope(ctx).RunID)
					return func() {}, nil
				}}
				ctx := sshpassword.WithScope(context.Background(), sshpassword.Scope{RunID: "installer-123"})
				archive, err := createProjectArchive(root)
				if err != nil {
					t.Fatal(err)
				}
				defer os.Remove(archive)
				_, err = transport.stageProjectArchive(ctx, testNode(), archive, "installer-123", purpose, "")
				var typed *ExecutionError
				if !errors.As(err, &typed) || typed.Code != "PROJECT_TRANSFER_FAILED" {
					t.Fatalf("misclassified transfer failure: %v", err)
				}
				cleanup := false
				for _, call := range runner.calls {
					if strings.Contains(call.input, `rm -rf -- "$temporary"`) {
						cleanup = true
						if call.args[len(call.args)-1] != projectUploadPath("installer-123", purpose) {
							t.Fatal("cleanup guessed another namespace")
						}
					}
				}
				if cleanup != (failure != "mkdir") {
					t.Fatal("cleanup did not respect claim ownership")
				}
				for _, scope := range scopes {
					if scope != "installer-123" {
						t.Fatal("cleanup lost run scope")
					}
				}
			})
		}
	}
}

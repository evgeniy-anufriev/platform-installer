package executionnode

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSudoFramingKeepsPasswordOutOfArgsAndWipesInput(t *testing.T) {
	transport := OpenSSHTransport{SudoPassword: func(_ context.Context, use func([]byte) error) error { return use([]byte("synthetic-sudo")) }}
	var borrowed []byte
	for _, program := range []string{"sudo", "sh"} {
		args := []string{"-n", "cat"}
		input := []byte("{\"qa\":true}\n")
		if program == "sh" {
			args = []string{"-s"}
			input = []byte("set -eu\nsudo -n id -u\n")
		}
		_, err := transport.withSudoInput(context.Background(), program, args, input, func(_ string, args []string, framed []byte) ([]byte, error) {
			if strings.Contains(strings.Join(args, " "), "synthetic-sudo") {
				t.Fatal("password in args")
			}
			if !bytes.HasSuffix(framed, input) {
				t.Fatal("original stdin changed")
			}
			if bytes.Count(framed, []byte("synthetic-sudo\n")) != 1 {
				t.Fatal("framing duplicated")
			}
			borrowed = framed
			return nil, errors.New("injected")
		})
		if err == nil {
			t.Fatal("failure lost")
		}
		if !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
			t.Fatal("framed secret not wiped")
		}
	}
	_, err := transport.withSudoInput(context.Background(), "sh", []string{"-s"}, []byte(serverInformationScript), func(_ string, _ []string, input []byte) ([]byte, error) {
		if !bytes.Equal(input, []byte(serverInformationScript)) {
			t.Fatal("informational command elevated")
		}
		return nil, nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

type sudoQAIdentity string

func (p sudoQAIdentity) IdentityFile(string) (string, error) { return string(p), nil }

// Opt-in read-only sudo checks plus an isolated temporary staging claim. Never
// activates a runtime or changes accounts/policies. Synthetic sudo input works
// with the established passwordless automation identity; UI admin QA is separate.
func TestREDOSSudoAndPrivateStaging(t *testing.T) {
	key := os.Getenv("PLATFORM_INSTALLER_SUDO_QA_KEY")
	if key == "" {
		t.Skip("explicit RED OS QA opt-in required")
	}
	home, err := os.UserHomeDir()
	if err != nil {
		t.Fatal(err)
	}
	transport := OpenSSHTransport{Identity: sudoQAIdentity(key), SudoPassword: func(_ context.Context, use func([]byte) error) error { return use([]byte("synthetic-only")) }}
	node := Node{Address: "192.168.56.101", Port: 22, User: "platform-automation", HostKey: HostKeyPolicy{KnownHosts: filepath.Join(home, ".ssh", "known_hosts")}}
	ctx := context.Background()
	for _, command := range []struct {
		program     string
		args        []string
		input, want string
	}{
		{"sh", []string{"-s"}, "set -eu\nprintf 'ROOT=%s\\n' \"$(sudo -n id -u)\"\nprintf '{\"qa\":\"preserved\"}\\n' | sudo -n cat\nsudo -n id -u\n", "ROOT=0\n{\"qa\":\"preserved\"}\n0\n"},
		{"sudo", []string{"-n", "cat"}, "{\"qa\":\"verbatim\"}\n", "{\"qa\":\"verbatim\"}\n"},
	} {
		out, err := transport.ssh(ctx, node, command.program, command.args, []byte(command.input))
		if err != nil {
			t.Fatal(err)
		}
		if string(out) != command.want {
			t.Fatal("sudo command substitution/pipeline/protocol stdin differs")
		}
	}
	stage := "/var/tmp/platform-installer-bootstrap-" + strings.Repeat("b", 32)
	if _, err := transport.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(prepareBundleStageScript)); err != nil {
		t.Fatal(err)
	}
	defer transport.DiscardStagedRuntime(ctx, node, stage)
	if _, err := transport.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(prepareBundleStageScript)); err == nil {
		t.Fatal("existing stage accepted")
	}
	out, err := transport.ssh(ctx, node, "stat", []string{"-c", "%a", stage}, nil)
	if err != nil || string(out) != "700\n" {
		t.Fatal("stage not private")
	}
	t.Log("RED OS sudo substitutions/pipeline/protocol stdin and private exclusive stage PASS")
}

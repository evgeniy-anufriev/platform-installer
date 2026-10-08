package executionnode

import (
	"context"
	"errors"
	"strings"
	"testing"
)

type informationRunner struct {
	args     []string
	input    string
	fail     bool
	deadline bool
}

func (r *informationRunner) Run(context.Context, string, []string, []byte) ([]byte, error) {
	return nil, errors.New("unexpected unbounded command")
}
func (r *informationRunner) RunSeparatedBounded(ctx context.Context, name string, args []string, input []byte, stdoutLimit, stderrLimit int) ([]byte, []byte, error) {
	r.args = args
	r.input = string(input)
	_, r.deadline = ctx.Deadline()
	if name != "ssh" || stdoutLimit != 16384 || stderrLimit != 1024 {
		return nil, nil, errors.New("unexpected bounds")
	}
	if r.fail {
		return nil, []byte("sensitive remote error"), errors.New("sensitive process error")
	}
	return []byte("HOSTNAME=node1\nOS=RED OS\nVERSION=8\nARCH=x86_64\nCPU=8\nMEMORY_KIB=16777216\nTIME=2026-10-08T16:00:00Z\n"), nil, nil
}

func TestServerInformationUsesIsolatedBoundedGuardedSSH(t *testing.T) {
	runner := &informationRunner{}
	held, released := 0, 0
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner, IsolatedHostKeyTrust: true, CommandGuard: func() (func(), error) { held++; return func() { released++ }, nil }}
	if _, err := transport.ReadServerInformation(context.Background(), testNode()); err != nil {
		t.Fatal(err)
	}
	args := strings.Join(runner.args, " ")
	for _, expected := range []string{"-F none", "GlobalKnownHostsFile=none", "KnownHostsCommand=none", "BatchMode=yes", "IdentitiesOnly=yes", "StrictHostKeyChecking=yes"} {
		if !strings.Contains(args, expected) {
			t.Fatal("missing isolated SSH option", expected)
		}
	}
	if held != 1 || released != 1 || !runner.deadline || strings.Contains(runner.input, "sudo") || strings.Contains(runner.input, ". /etc/os-release") {
		t.Fatal("unsafe informational check")
	}
	runner.fail = true
	if _, err := transport.ReadServerInformation(context.Background(), testNode()); err == nil || strings.Contains(err.Error(), "sensitive") {
		t.Fatal("raw failure leaked")
	}
}

func TestServerInformationClosedProjection(t *testing.T) {
	valid := "HOSTNAME=node1\nOS=\"RED OS\"\nVERSION=\"8\"\nARCH=x86_64\nCPU=8\nMEMORY_KIB=16777216\nTIME=2026-10-08T16:00:00Z\n"
	info, err := parseServerInformation([]byte(valid))
	if err != nil || info.CPUCount != 8 || info.MemoryBytes != 16<<30 || info.OS != "RED OS" || info.CheckedAt == "" {
		t.Fatal("valid facts rejected")
	}
	for name, input := range map[string]string{
		"duplicate": valid + "CPU=9\n", "unknown": valid + "SECRET=value\n", "oversized": strings.Repeat("x", 16385),
		"missing": strings.ReplaceAll(valid, "CPU=8\n", ""), "negative": strings.ReplaceAll(valid, "CPU=8", "CPU=-1"),
		"invalid-time":    strings.ReplaceAll(valid, "2026-10-08T16:00:00Z", "invalid"),
		"memory-overflow": strings.ReplaceAll(valid, "16777216", "9223372036854775807"),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := parseServerInformation([]byte(input)); err == nil {
				t.Fatal("unsafe facts accepted")
			}
		})
	}
}

package sshpassword

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

const syntheticPassword = "test-only-ssh-password"

func TestMain(m *testing.M) {
	if len(os.Args) > 1 && os.Args[1] == "--sshpassword-command" {
		// This child stands in for OpenSSH, which starts the packaged helper.
		if strings.Contains(strings.Join(os.Environ(), "\n"), syntheticPassword) {
			os.Exit(2)
		}
		wrong := strings.Repeat("0", 64)
		if _, err := helperResponse(os.Getenv(prefix+"ENDPOINT"), wrong); err == nil {
			os.Exit(3)
		}
		cmd := exec.Command(os.Getenv("SSH_ASKPASS"), "password prompt")
		response, err := cmd.Output()
		if err != nil || !bytes.Equal(response, []byte(syntheticPassword+"\n")) {
			os.Exit(4)
		}
		if _, err := helperResponse(os.Getenv(prefix+"ENDPOINT"), os.Getenv(prefix+"TOKEN")); err == nil {
			os.Exit(5)
		}
		fmt.Print("authenticated")
		os.Exit(0)
	}
	if len(os.Args) > 1 && os.Args[1] == "--sshpassword-wait" {
		time.Sleep(30 * time.Second)
		os.Exit(0)
	}
	Dispatch()
	os.Exit(m.Run())
}

func TestAskpassCapabilityIsBoundedAndOneUse(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	executable, _ := os.Executable()
	command := exec.CommandContext(ctx, executable, "--sshpassword-command")
	var output bytes.Buffer
	command.Stdout = &output
	value := []byte(syntheticPassword)
	provider := func(_ context.Context, use func([]byte) error) error {
		defer func() {
			for i := range value {
				value[i] = 0
			}
		}()
		return use(value)
	}
	if err := Run(ctx, command, provider); err != nil {
		t.Fatalf("askpass handshake failed: %v", err)
	}
	if output.String() != "authenticated" {
		t.Fatal("unexpected helper command result")
	}
	if strings.Contains(strings.Join(command.Args, " ")+strings.Join(command.Env, "\n"), syntheticPassword) {
		t.Fatal("password leaked into argv/environment")
	}
	if !bytes.Equal(value, make([]byte, len(value))) {
		t.Fatal("provider copy not cleared")
	}
}

func TestAskpassCancellationAndUnsupportedBytes(t *testing.T) {
	executable, _ := os.Executable()
	for _, password := range [][]byte{nil, []byte("bad\nvalue"), []byte("bad\rvalue"), []byte("bad\x00value"), bytes.Repeat([]byte{'a'}, maxPassword+1)} {
		command := exec.Command(executable, "--sshpassword-command")
		err := Run(context.Background(), command, func(_ context.Context, use func([]byte) error) error { return use(password) })
		if err == nil || err.Error() != "SSH_PASSWORD_FORMAT_UNSUPPORTED" {
			t.Fatal("unsupported password accepted")
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	command := exec.CommandContext(ctx, executable, "--sshpassword-wait")
	begin := time.Now()
	err := Run(ctx, command, func(_ context.Context, use func([]byte) error) error { return use([]byte(syntheticPassword)) })
	if err == nil || !errors.Is(ctx.Err(), context.DeadlineExceeded) || time.Since(begin) > 3*time.Second {
		t.Fatal("command/listener cancellation failed")
	}
}

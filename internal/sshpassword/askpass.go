// Package sshpassword supplies command-scoped OpenSSH ASKPASS without storing
// passwords in files, command arguments or process environment.
package sshpassword

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"io"
	"net"
	"os"
	"os/exec"
	"strings"
	"time"
)

const prefix = "PLATFORM_INSTALLER_SSH_"
const maxPassword = 32768

type Provider func(context.Context, func([]byte) error) error
type scopeKey struct{}
type Scope struct{ PlanID, RunID string }

func WithScope(ctx context.Context, scope Scope) context.Context {
	return context.WithValue(ctx, scopeKey{}, scope)
}
func OperationScope(ctx context.Context) Scope {
	value, _ := ctx.Value(scopeKey{}).(Scope)
	return value
}

func validPassword(value []byte) bool {
	if len(value) == 0 || len(value) > maxPassword {
		return false
	}
	for _, b := range value {
		if b == 0 || b == '\r' || b == '\n' {
			return false
		}
	}
	return true
}

// Run owns listener, connections and the helper capability until the child
// finishes. The provider wipes the password when this synchronous call returns.
func Run(ctx context.Context, command *exec.Cmd, provider Provider) error {
	return provider(ctx, func(password []byte) error {
		if !validPassword(password) {
			return errors.New("SSH_PASSWORD_FORMAT_UNSUPPORTED")
		}
		executable, err := os.Executable()
		if err != nil {
			return errors.New("SSH_PASSWORD_HELPER_UNAVAILABLE")
		}
		listener, err := net.Listen("tcp4", "127.0.0.1:0")
		if err != nil {
			return errors.New("SSH_PASSWORD_HELPER_UNAVAILABLE")
		}
		defer listener.Close()
		var random [32]byte
		if _, err = rand.Read(random[:]); err != nil {
			return errors.New("SSH_PASSWORD_HELPER_UNAVAILABLE")
		}
		token := hex.EncodeToString(random[:])
		done := make(chan struct{})
		go func() {
			defer close(done)
			defer listener.Close()
			for attempt := 0; attempt < 4; attempt++ {
				connection, err := listener.Accept()
				if err != nil {
					return
				}
				_ = connection.SetDeadline(time.Now().Add(2 * time.Second))
				var supplied [64]byte
				_, err = io.ReadFull(connection, supplied[:])
				if err == nil && subtle.ConstantTimeCompare(supplied[:], []byte(token)) == 1 {
					_, _ = connection.Write(password)
					_, _ = connection.Write([]byte{'\n'})
					_ = connection.Close()
					return
				}
				_ = connection.Close()
			}
		}()
		// Remove inherited helper capabilities and SSH overrides before setting the
		// capability for this one child. Its value is never the SSH password.
		environment := command.Env
		if environment == nil {
			environment = os.Environ()
		}
		command.Env = nil
		for _, entry := range environment {
			name, _, _ := strings.Cut(entry, "=")
			name = strings.ToUpper(name)
			if !strings.HasPrefix(name, prefix) && name != "SSH_ASKPASS" && name != "SSH_ASKPASS_REQUIRE" {
				command.Env = append(command.Env, entry)
			}
		}
		command.Env = append(command.Env, "SSH_ASKPASS="+executable, "SSH_ASKPASS_REQUIRE=force", prefix+"ASKPASS=1", prefix+"ENDPOINT="+listener.Addr().String(), prefix+"TOKEN="+token)
		err = command.Run()
		_ = listener.Close()
		<-done
		return err
	})
}

// Dispatch runs before flags or UI initialization. A helper invocation has no
// application bindings and prints only the one authenticated ASKPASS response.
func Dispatch() bool {
	if os.Getenv(prefix+"ASKPASS") != "1" {
		return false
	}
	response, err := helperResponse(os.Getenv(prefix+"ENDPOINT"), os.Getenv(prefix+"TOKEN"))
	if err == nil {
		_, err = os.Stdout.Write(response)
	}
	for i := range response {
		response[i] = 0
	}
	if err != nil {
		os.Exit(1)
	}
	os.Exit(0)
	return true
}

func helperResponse(endpoint, token string) ([]byte, error) {
	fail := errors.New("SSH_PASSWORD_HELPER_UNAVAILABLE")
	host, port, err := net.SplitHostPort(endpoint)
	if err != nil || host != "127.0.0.1" || port == "" || len(token) != 64 {
		return nil, fail
	}
	if decoded, err := hex.DecodeString(token); err != nil || len(decoded) != 32 {
		return nil, fail
	}
	connection, err := net.DialTimeout("tcp4", endpoint, 2*time.Second)
	if err != nil {
		return nil, fail
	}
	defer connection.Close()
	_ = connection.SetDeadline(time.Now().Add(2 * time.Second))
	if _, err = io.WriteString(connection, token); err != nil {
		return nil, fail
	}
	response, err := io.ReadAll(io.LimitReader(connection, maxPassword+2))
	if err != nil || len(response) < 2 || response[len(response)-1] != '\n' || !validPassword(response[:len(response)-1]) {
		for i := range response {
			response[i] = 0
		}
		return nil, fail
	}
	return response, nil
}

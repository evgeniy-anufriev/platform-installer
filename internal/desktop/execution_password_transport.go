package desktop

import (
	"context"
	"crypto/sha256"
	"errors"
	"os"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
	"platform-installer/internal/sshpassword"
)

func sameTransportIdentity(a, b runtimesecret.ExecutionIdentity) bool {
	return a.Mode == b.Mode && a.Generation == b.Generation && a.Username == b.Username && a.Path == b.Path && a.Digest == b.Digest
}

func (a *App) executionTransport(identity runtimesecret.ExecutionIdentity, binding runtimesecret.Binding, known string, file os.FileInfo, digest [sha256.Size]byte) executionnode.OpenSSHTransport {
	guard := func(ctx context.Context) (func(), error) {
		var current runtimesecret.ExecutionIdentity
		var err error
		if identity.Mode == runtimesecret.SSHPassword {
			scope := sshpassword.OperationScope(ctx)
			current, err = a.secrets.CurrentExecutionIdentityForOperation(binding, scope.PlanID, scope.RunID)
		} else {
			current, err = a.secrets.CurrentExecutionIdentity(binding)
		}
		if err != nil || !sameTransportIdentity(current, identity) {
			return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
		}
		releaseKey := func() {}
		if identity.Mode != runtimesecret.SSHPassword {
			releaseKey, err = holdVerifiedBindingFile(identity.Path, identity.FileInfo, identity.Digest, 1<<20)
			if err != nil {
				return nil, err
			}
		}
		releaseHost, err := holdVerifiedBindingFile(known, file, digest, maxSessionKnownHostsBytes)
		if err != nil {
			releaseKey()
			return nil, err
		}
		return func() { releaseHost(); releaseKey() }, nil
	}
	transport := executionnode.OpenSSHTransport{Identity: desktopIdentity{identity.Path}, ContextCommandGuard: guard, IsolatedHostKeyTrust: true}
	transport.CommandGuard = func() (func(), error) { return guard(context.Background()) }
	if identity.Mode == runtimesecret.SSHPassword {
		transport.Password = func(ctx context.Context, use func([]byte) error) error {
			scope := sshpassword.OperationScope(ctx)
			return a.secrets.WithExecutionPassword(binding, identity, scope.PlanID, scope.RunID, use)
		}
	}
	if a.secrets.HasExecutionSudoPassword(binding, identity) {
		transport.SudoPassword = func(ctx context.Context, use func([]byte) error) error {
			scope := sshpassword.OperationScope(ctx)
			return a.secrets.WithExecutionSudoPassword(binding, identity, scope.PlanID, scope.RunID, use)
		}
	}
	return transport
}

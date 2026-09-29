package executionnode

import (
	"context"
	"errors"
	"regexp"
	"strings"
)

const remoteAcquisitionWorkspacePrefix = "/var/tmp/platform-installer-acquisition-"

var remoteAcquisitionWorkspacePattern = regexp.MustCompile(`^/var/tmp/platform-installer-acquisition-[A-Za-z0-9]{10}$`)

func createRemoteAcquisitionWorkspace(ctx context.Context, transport OpenSSHTransport, node Node) (string, error) {
	script := "set -eu\nroot=$(mktemp -d /var/tmp/platform-installer-acquisition-XXXXXXXXXX)\nchmod 700 \"$root\"\nprintf '%s\\n' \"$root\"\n"
	output, err := transport.ssh(ctx, node, "sh", []string{"-s"}, []byte(script))
	if err != nil {
		return "", err
	}
	root := strings.TrimSuffix(string(output), "\n")
	if strings.ContainsAny(root, "\r\n") || !remoteAcquisitionWorkspacePattern.MatchString(root) {
		return "", errors.New("EXECUTION_ACQUISITION_WORKSPACE_INVALID")
	}
	return root, nil
}

func cleanupRemoteAcquisitionWorkspace(transport OpenSSHTransport, node Node, root string) {
	if !remoteAcquisitionWorkspacePattern.MatchString(root) {
		return
	}
	script := "set -eu\nroot=$1\ncase \"$root\" in /var/tmp/platform-installer-acquisition-??????????) ;; *) exit 64;; esac\ntest -d \"$root\" && test ! -L \"$root\"\nrm -rf -- \"$root\"\n"
	_, _ = transport.ssh(context.Background(), node, "sh", []string{"-s", "--", root}, []byte(script))
}

func validateRemoteAcquisitionWorkspace(root string) error {
	if !remoteAcquisitionWorkspacePattern.MatchString(root) {
		return errors.New("EXECUTION_ACQUISITION_WORKSPACE_INVALID")
	}
	return nil
}

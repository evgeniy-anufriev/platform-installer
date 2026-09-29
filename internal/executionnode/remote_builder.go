package executionnode

import (
	"archive/tar"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// BuildOnExecutionNode runs the existing Python bundle builder on the trusted
// Linux execution node. The workstation never needs Python or Ansible.
func (t OpenSSHTransport) BuildOnExecutionNode(ctx context.Context, node Node, runtimeInput, bundleVersion, coreVersion string) (string, error) {
	if t.RepositoryRoot == "" || runtimeInput == "" || bundleVersion == "" {
		return "", errors.New("EXECUTION_BUNDLE_REMOTE_BUILD_INPUT_INVALID")
	}
	root, err := os.MkdirTemp("", "platform-installer-remote-build-")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(root)
	inputArchive := filepath.Join(root, "input.tar")
	if err := createSourceArchive(t.RepositoryRoot, runtimeInput, inputArchive); err != nil {
		return "", err
	}
	remoteRoot, err := createRemoteAcquisitionWorkspace(ctx, t, node)
	if err != nil {
		return "", err
	}
	defer cleanupRemoteAcquisitionWorkspace(t, node, remoteRoot)
	if err := validateRemoteAcquisitionWorkspace(remoteRoot); err != nil {
		return "", err
	}
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remoteRoot}, []byte("set -eu\nroot=$1\ncase \"$root\" in /var/tmp/platform-installer-acquisition-??????????) ;; *) exit 64;; esac\ntest -d \"$root\" && test ! -L \"$root\"\nmkdir -m 700 -- \"$root/source\"\n")); err != nil {
		return "", err
	}
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return "", err
	}
	args := append(t.scpBase(node, identity), "-O", "--", inputArchive, t.destination(node, remoteRoot+"/input.tar"))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return "", err
	}
	buildScript := "set -eu\nroot=$1; bundle_version=$2; core_version=${3:-0.1.0}\ncase \"$root\" in /var/tmp/platform-installer-acquisition-??????????) ;; *) exit 64;; esac\ntest -d \"$root\" && test ! -L \"$root\"\ntar -xf \"$root/input.tar\" -C \"$root/source\"\nchmod -R u+rwX \"$root/source\"\ncommand -v python3 >/dev/null 2>&1\npython3 \"$root/source/ansible-core/tools/build_execution_runtime_bundle.py\" --output \"$root/bundle\" --runtime-input \"$root/source/runtime-input\" --bundle-version \"$bundle_version\" --core-version \"$core_version\"\ntar -cf \"$root/result.tar\" -C \"$root\" bundle\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remoteRoot, bundleVersion, coreVersion}, []byte(buildScript)); err != nil {
		return "", fmt.Errorf("EXECUTION_BUNDLE_REMOTE_BUILD_FAILED: %w", err)
	}
	resultArchive := filepath.Join(root, "result.tar")
	args = append(t.scpBase(node, identity), "-O", "--", t.destination(node, remoteRoot+"/result.tar"), resultArchive)
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return "", errors.New("EXECUTION_BUNDLE_REMOTE_TRANSFER_FAILED")
	}
	outputRoot, err := os.MkdirTemp("", "platform-installer-remote-bundle-")
	if err != nil {
		return "", err
	}
	if err := extractTar(resultArchive, outputRoot); err != nil {
		_ = os.RemoveAll(outputRoot)
		return "", err
	}
	return filepath.Join(outputRoot, "bundle"), nil
}

func createSourceArchive(repositoryRoot, runtimeInput, output string) error {
	file, err := os.Create(output)
	if err != nil {
		return err
	}
	archive := tar.NewWriter(file)
	closeArchive := func() error {
		if err := archive.Close(); err != nil {
			_ = file.Close()
			return err
		}
		return file.Close()
	}
	for _, source := range []struct{ name, path string }{
		{"ansible-core", filepath.Join(repositoryRoot, "ansible-core")},
		{"services", filepath.Join(repositoryRoot, "services")},
		{"examples", filepath.Join(repositoryRoot, "examples")},
		{"contracts", filepath.Join(repositoryRoot, "contracts")},
		{"runtime-input", runtimeInput},
	} {
		if err := addTreeToTar(archive, source.path, source.name); err != nil {
			_ = file.Close()
			return err
		}
	}
	return closeArchive()
}

func addTreeToTar(archive *tar.Writer, source, prefix string) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		name := filepath.ToSlash(prefix)
		if relative != "." {
			name += "/" + filepath.ToSlash(relative)
		}
		if entry.Type()&os.ModeSymlink != 0 || !entry.IsDir() && !entry.Type().IsRegular() {
			return errors.New("EXECUTION_BUNDLE_SOURCE_UNSAFE")
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = name
		if err := archive.WriteHeader(header); err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		input, err := os.Open(path)
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(archive, input)
		_ = input.Close()
		return copyErr
	})
}

func extractTar(source, destination string) error {
	file, err := os.Open(source)
	if err != nil {
		return err
	}
	defer file.Close()
	archive := tar.NewReader(file)
	for {
		header, err := archive.Next()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		name := header.Name
		if header.FileInfo().IsDir() {
			name = strings.TrimSuffix(name, "/")
		}
		if name == "" || filepath.IsAbs(name) || filepath.ToSlash(filepath.Clean(name)) != name || strings.HasPrefix(name, "../") || strings.Contains(name, "/../") || header.Typeflag == tar.TypeSymlink || header.Typeflag == tar.TypeLink {
			return errors.New("EXECUTION_BUNDLE_REMOTE_ARCHIVE_UNSAFE")
		}
		target := filepath.Join(destination, filepath.FromSlash(name))
		if !containedLocal(destination, target) {
			return errors.New("EXECUTION_BUNDLE_REMOTE_ARCHIVE_PATH_INVALID")
		}
		if header.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o700); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
			return err
		}
		output, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(output, archive)
		closeErr := output.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
	}
}

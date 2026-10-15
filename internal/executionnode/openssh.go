package executionnode

// This adapter is deliberately semantic: all remote paths and shell programs
// are fixed here, while credentials stay behind a runtime-only resolver.

import (
	"archive/tar"
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"reflect"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/commandwindow"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/installer"
	"platform-installer/internal/sshpassword"
)

type IdentityResolver interface {
	IdentityFile(credentialRef string) (string, error)
}

type commandRunner interface {
	Run(context.Context, string, []string, []byte) ([]byte, error)
}

type boundedCommandRunner interface {
	RunBounded(context.Context, string, []string, []byte, int) ([]byte, error)
}

type separatedCommandRunner interface {
	RunSeparatedBounded(context.Context, string, []string, []byte, int, int) ([]byte, []byte, error)
}

type osRunner struct{ password sshpassword.Provider }

func (r osRunner) execute(ctx context.Context, command *exec.Cmd) error {
	if r.password != nil {
		return sshpassword.Run(ctx, command, r.password)
	}
	return command.Run()
}

func (r osRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	command := exec.CommandContext(ctx, name, args...)
	commandwindow.Configure(command)
	command.Stdin = bytes.NewReader(input)
	var output bytes.Buffer
	command.Stdout, command.Stderr = &output, &output
	err := r.execute(ctx, command)
	return output.Bytes(), err
}

func (r osRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	command := exec.CommandContext(ctx, name, args...)
	commandwindow.Configure(command)
	command.Stdin = bytes.NewReader(input)
	output := &boundedOutput{limit: limit}
	command.Stdout = output
	command.Stderr = output
	err := r.execute(ctx, command)
	if output.overflow {
		return output.Bytes(), errors.New("EXECUTION_NODE_OUTPUT_LIMIT")
	}
	return output.Bytes(), err
}

func (r osRunner) RunSeparatedBounded(ctx context.Context, name string, args []string, input []byte, stdoutLimit, stderrLimit int) ([]byte, []byte, error) {
	command := exec.CommandContext(ctx, name, args...)
	commandwindow.Configure(command)
	command.Stdin = bytes.NewReader(input)
	stdout := &boundedOutput{limit: stdoutLimit}
	stderr := &boundedOutput{limit: stderrLimit}
	command.Stdout, command.Stderr = stdout, stderr
	err := r.execute(ctx, command)
	if stdout.overflow || stderr.overflow {
		return stdout.Bytes(), nil, errors.New("EXECUTION_NODE_OUTPUT_LIMIT")
	}
	return stdout.Bytes(), stderr.Bytes(), err
}

type boundedOutput struct {
	bytes.Buffer
	limit    int
	overflow bool
}

func (b *boundedOutput) Write(value []byte) (int, error) {
	original := len(value)
	remaining := b.limit - b.Len()
	if remaining > 0 {
		if remaining < len(value) {
			_, _ = b.Buffer.Write(value[:remaining])
		} else {
			_, _ = b.Buffer.Write(value)
		}
	}
	if original > remaining {
		b.overflow = true
	}
	return original, nil
}

// OpenSSHTransport is the one product transport for the pre-Core boundary.
// It never accepts a caller-defined remote command or destination.
type OpenSSHTransport struct {
	Identity IdentityResolver
	Runner   commandRunner
	// CommandGuard holds the UI-approved identity and host-key files stable
	// across each SSH/SCP child process. Nil preserves the legacy flag path.
	CommandGuard         func() (func(), error)
	ContextCommandGuard  func(context.Context) (func(), error)
	Password             sshpassword.Provider
	SudoPassword         sshpassword.Provider
	IsolatedHostKeyTrust bool
	RepositoryRoot       string
	RuntimeRoot          string
	StageRoot            string
}

func (t OpenSSHTransport) InspectExecutionNode(ctx context.Context, node Node) (Inspection, error) {
	root := t.runtimeRoot()
	script := "set -eu\nroot=$1\ncase \"$root\" in /var/lib/platform-installer/runtime) ;; *) exit 64;; esac\n. /etc/os-release\nruntime=''; bundle=''; digest=''; core=''; protocol=''; ansible='no'; capabilities='no'\nif sudo -n test -r \"$root/state/active\" && sudo -n test -L \"$root/current\"; then\n  runtime='yes'\n  bundle=$(sudo -n awk -F= '$1 == \"BUNDLE_VERSION\" {print $2}' \"$root/state/active\")\n  digest=$(sudo -n awk -F= '$1 == \"BUNDLE_DIGEST\" {print $2}' \"$root/state/active\")\n  core=$(sudo -n awk -F= '$1 == \"CORE_VERSION\" {print $2}' \"$root/state/active\")\n  protocol=$(sudo -n awk -F= '$1 == \"PROTOCOL\" {print $2}' \"$root/state/active\")\n  ansible=$(sudo -n awk -F= '$1 == \"ANSIBLE\" {print $2}' \"$root/state/active\")\n  capabilities=$(sudo -n awk -F= '$1 == \"CAPABILITIES\" {print $2}' \"$root/state/active\")\nfi\nprintf '%s\\n' \"OS=$ID\" \"VERSION=$VERSION_ID\" \"ARCH=$(uname -m)\" \"ELEVATION=$(sudo -n true >/dev/null 2>&1 && echo yes || echo no)\" \"FREE=$(df -Pk /var/tmp | awk 'NR==2 {print $4 * 1024}')\" \"RUNTIME=$runtime\" \"BUNDLE_VERSION=$bundle\" \"BUNDLE_DIGEST=$digest\" \"CORE_VERSION=$core\" \"PROTOCOL=$protocol\" \"ANSIBLE=$ansible\" \"CAPABILITIES=$capabilities\"\n"
	output, err := t.ssh(ctx, node, "sh", []string{"-s", "--", root}, []byte(script))
	if err != nil {
		return Inspection{State: Unreachable}, err
	}
	values := parseFacts(string(output))
	runtime := Runtime{BundleVersion: values["BUNDLE_VERSION"], BundleDigest: values["BUNDLE_DIGEST"], CoreVersion: values["CORE_VERSION"], Protocol: values["PROTOCOL"], Ansible: values["ANSIBLE"] == "yes", Capabilities: values["CAPABILITIES"] == "yes"}
	state := PreparationRequired
	if values["RUNTIME"] == "yes" {
		state = Ready
	}
	return Inspection{State: state, OS: values["OS"], OSVersion: values["VERSION"], Architecture: values["ARCH"], Elevation: values["ELEVATION"] == "yes", FreeBytes: parseInt64(values["FREE"]), Runtime: runtime}, nil
}

// ReconcileWorkspaceOwnership keeps the fixed candidate staging path writable
// by the SSH identity used for this preparation. The shared workspace parent
// remains root-owned and traversable; private, payload and /var/lib runtime
// trees are outside the ownership change.
func (t OpenSSHTransport) ReconcileWorkspaceOwnership(ctx context.Context, node Node) (bool, error) {
	output, err := t.ssh(ctx, node, "sh", []string{"-s"}, []byte(reconcileWorkspaceOwnershipScript))
	if err != nil {
		return false, err
	}
	switch parseFacts(string(output))["CHANGED"] {
	case "yes":
		return true, nil
	case "no":
		return false, nil
	default:
		return false, errors.New("EXECUTION_WORKSPACE_RECONCILIATION_INVALID")
	}
}

const reconcileWorkspaceOwnershipScript = `set -eu
base=/var/tmp/platform-installer
workspace=$base/execution-plan
[ -d /var/tmp ] && [ ! -L /var/tmp ] || exit 64
[ "$(stat -c %u /var/tmp)" = 0 ] && [ "$(stat -c %a /var/tmp)" = 1777 ] || exit 64
uid=$(id -u)
gid=$(id -g)
changed=no
if sudo -n test -L "$base"; then exit 64; fi
if ! sudo -n test -e "$base"; then
  sudo -n install -d -o root -g root -m 0711 -- "$base"
  changed=yes
fi
sudo -n test -d "$base" && sudo -n test ! -L "$base" || exit 64
base_owner=$(sudo -n stat -c %u -- "$base")
base_mode=$(sudo -n stat -c %a -- "$base")
if [ "$base_owner" != 0 ] || [ "$base_mode" != 711 ]; then
  sudo -n chown root:root -- "$base"
  sudo -n chmod 0711 -- "$base"
  changed=yes
fi
if sudo -n test -L "$workspace"; then exit 64; fi
if ! sudo -n test -e "$workspace"; then
  sudo -n install -d -o "$uid" -g "$gid" -m 0700 -- "$workspace"
  changed=yes
fi
sudo -n test -d "$workspace" && sudo -n test ! -L "$workspace" || exit 64
unsafe=$(sudo -n find "$workspace" -xdev \( -type l -o \( ! -type d -a ! -type f \) \) -print -quit)
[ -z "$unsafe" ] || exit 65
owner=$(sudo -n stat -c %u -- "$workspace")
if [ "$owner" != "$uid" ]; then
  entries=$(sudo -n find "$workspace" -mindepth 1 -maxdepth 1 -print -quit)
  [ -z "$entries" ] || exit 65
  sudo -n chown -- "$uid:$gid" -- "$workspace"
  changed=yes
fi
workspace_mode=$(sudo -n stat -c %a -- "$workspace")
if [ "$workspace_mode" != 700 ]; then
  sudo -n chmod 0700 -- "$workspace"
  changed=yes
fi
[ "$(sudo -n stat -c %u -- "$workspace")" = "$uid" ] || exit 66
printf 'CHANGED=%s\n' "$changed"
`

func (t OpenSSHTransport) InspectAcquisitionSource(ctx context.Context, node Node) (AcquisitionEnvironment, error) {
	inspection, err := t.InspectExecutionNode(ctx, node)
	if err != nil {
		return AcquisitionEnvironment{}, err
	}
	if inspection.OS != "redos" {
		return AcquisitionEnvironment{}, errors.New("EXECUTION_ACQUISITION_OS_UNSUPPORTED")
	}
	return AcquisitionEnvironment{OS: inspection.OS, Version: inspection.OSVersion, Architecture: inspection.Architecture, RepositorySource: "configured-dnf", Trusted: true}, nil
}

func (t OpenSSHTransport) AcquireRuntimeClosure(ctx context.Context, node Node, environment AcquisitionEnvironment, destination string) error {
	if environment.OS != "redos" || environment.Architecture != "x86_64" || environment.RepositorySource != "configured-dnf" || destination == "" {
		return errors.New("EXECUTION_ACQUISITION_INPUT_INVALID")
	}
	absolute, err := filepath.Abs(destination)
	if err != nil {
		return errors.New("EXECUTION_ACQUISITION_DESTINATION_INVALID")
	}
	target := filepath.Join(absolute, "packages", environment.OS, environment.Version, environment.Architecture)
	if !containedLocal(absolute, target) {
		return errors.New("EXECUTION_ACQUISITION_DESTINATION_INVALID")
	}
	if err := os.MkdirAll(target, 0o700); err != nil {
		return err
	}
	remote, err := createRemoteAcquisitionWorkspace(ctx, t, node)
	if err != nil {
		return errors.New("EXECUTION_RUNTIME_CLOSURE_FAILED")
	}
	defer cleanupRemoteAcquisitionWorkspace(t, node, remote)
	script := "set -eu\nroot=$1\n" + `case "$root" in /var/tmp/platform-installer-acquisition-??????????) ;; *) exit 64;; esac` + "\ntest -d \"$root\" && test ! -L \"$root\"\nsudo -n dnf -q download --resolve --alldeps --destdir \"$root\" -- python3 ansible-core openssl ca-certificates tar gzip\nrpm=$(find \"$root\" -maxdepth 1 -type f -name '*.rpm' -print -quit)\ntest -n \"$rpm\"\ncd \"$root\"\nsudo -n tar -cf closure.tar -- *.rpm\nsudo -n chmod 0644 closure.tar\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte(script)); err != nil {
		return errors.New("EXECUTION_RUNTIME_CLOSURE_FAILED")
	}
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return err
	}
	archive, err := os.CreateTemp(absolute, ".runtime-closure-*.tar")
	if err != nil {
		return err
	}
	archivePath := archive.Name()
	if err := archive.Close(); err != nil {
		_ = os.Remove(archivePath)
		return err
	}
	defer os.Remove(archivePath)
	args := append(t.scpBase(node, identity), "-O", "--", t.destination(node, remote+"/closure.tar"), archivePath)
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return fmt.Errorf("EXECUTION_RUNTIME_TRANSFER_FAILED: %w", err)
	}
	if err := extractTar(archivePath, target); err != nil {
		return fmt.Errorf("EXECUTION_RUNTIME_TRANSFER_FAILED: %w", err)
	}
	if err := os.MkdirAll(filepath.Join(absolute, "python"), 0o700); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(absolute, "python", "runtime-source.txt"), []byte("python3 from configured dnf closure\n"), 0o600)
}

func (t OpenSSHTransport) StageVerifiedBundle(ctx context.Context, node Node, bundle executionbundle.Verified) (string, error) {
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return "", err
	}
	stage := t.stageRoot() + "-" + hex.EncodeToString(nonce[:])
	if !validBundleStage(stage) {
		return "", errors.New("EXECUTION_BUNDLE_STAGE_INVALID")
	}
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(prepareBundleStageScript)); err != nil {
		return "", err
	}
	complete := false
	defer func() {
		if !complete {
			cleanupCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 30*time.Second)
			defer cancel()
			_ = t.DiscardStagedRuntime(cleanupCtx, node, stage)
		}
	}()
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return "", err
	}
	probe, err := t.ssh(ctx, node, "sh", []string{"-s"}, []byte("if command -v tar >/dev/null 2>&1; then printf 'TAR=1\\n'; else printf 'TAR=0\\n'; fi\n"))
	if err != nil {
		return "", err
	}
	if strings.TrimSpace(string(probe)) == "TAR=0" {
		if err := t.transferBundle(ctx, node, identity, stage, bundle.Root); err != nil {
			return "", err
		}
		if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(remoteChecks(bundle))); err != nil {
			return "", err
		}
		complete = true
		return stage, nil
	}
	if strings.TrimSpace(string(probe)) != "TAR=1" {
		return "", errors.New("EXECUTION_BUNDLE_TRANSFER_PREREQUISITE_INVALID")
	}
	archivePath, err := createBundleArchive(bundle)
	if err != nil {
		return "", err
	}
	defer os.Remove(archivePath)
	archiveRemote := path.Join(stage, "bundle.tar")
	args := append(t.scpBase(node, identity), "-O", "--", archivePath, t.destination(node, archiveRemote))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return "", err
	}
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage, archiveRemote}, []byte("set -eu\nstage=$1; archive=$2\ncase \"$stage\" in /var/tmp/platform-installer-bootstrap-*) ;; *) exit 64;; esac\n[ \"$archive\" = \"$stage/bundle.tar\" ] || exit 64\ntar -xf \"$archive\" -C \"$stage\"\nrm -f -- \"$archive\"\nmkdir -p -- \"$stage/runtime/packages\" \"$stage/runtime/python\"\n")); err != nil {
		return "", err
	}
	script := remoteChecks(bundle)
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(script)); err != nil {
		return "", err
	}
	complete = true
	return stage, nil
}

// Root-owned sticky /var/tmp protects the private stage from other SSH users.
// Exclusive unprivileged mkdir claims only this attempt, without chown or repair.
const prepareBundleStageScript = `set -eu
stage=$1
case "$stage" in /var/tmp/platform-installer-bootstrap-*) ;; *) exit 64;; esac
suffix=${stage#/var/tmp/platform-installer-bootstrap-}
case "$suffix" in ''|*[!0-9a-f]*) exit 64;; esac
[ "${#suffix}" = 32 ] || exit 64
[ -d /var/tmp ] && [ ! -L /var/tmp ] || exit 64
[ "$(stat -c %u /var/tmp)" = 0 ] && [ "$(stat -c %a /var/tmp)" = 1777 ] || exit 64
umask 077
mkdir -m 0700 -- "$stage"
`

func createBundleArchive(bundle executionbundle.Verified) (string, error) {
	file, err := os.CreateTemp("", "platform-execution-bundle-*.tar")
	if err != nil {
		return "", err
	}
	name := file.Name()
	cleanup := func(e error) (string, error) {
		_ = file.Close()
		_ = os.Remove(name)
		return "", e
	}
	writer := tar.NewWriter(file)
	paths := append([]string{"manifest.yaml"}, make([]string, 0, len(bundle.Manifest.Components))...)
	for _, component := range bundle.Manifest.Components {
		paths = append(paths, component.Path)
	}
	for _, relative := range paths {
		absolute := filepath.Join(bundle.Root, filepath.FromSlash(relative))
		info, err := os.Stat(absolute)
		if err != nil || !info.Mode().IsRegular() {
			return cleanup(errors.New("EXECUTION_BUNDLE_COMPONENT_INVALID"))
		}
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return cleanup(err)
		}
		header.Name = relative
		if err := writer.WriteHeader(header); err != nil {
			return cleanup(err)
		}
		input, err := os.Open(absolute)
		if err != nil {
			return cleanup(err)
		}
		_, copyErr := io.Copy(writer, input)
		closeErr := input.Close()
		if copyErr != nil {
			return cleanup(copyErr)
		}
		if closeErr != nil {
			return cleanup(closeErr)
		}
	}
	if err := writer.Close(); err != nil {
		return cleanup(err)
	}
	if err := file.Close(); err != nil {
		_ = os.Remove(name)
		return "", err
	}
	return name, nil
}

func (t OpenSSHTransport) transferBundle(ctx context.Context, node Node, identity, stage, root string) error {
	for _, name := range []string{"ansible-core", "catalog", "contracts", "runtime", "services"} {
		source := filepath.Join(root, name)
		if info, err := os.Stat(source); err != nil || !info.IsDir() {
			return errors.New("EXECUTION_BUNDLE_LAYOUT_INVALID")
		}
		args := append(t.scpBase(node, identity), "-O", "-r", "--", source, t.destination(node, stage))
		if _, err := t.run(ctx, "scp", args, nil); err != nil {
			return fmt.Errorf("EXECUTION_BUNDLE_TRANSFER_FAILED:%s:%w", name, err)
		}
	}
	manifest := filepath.Join(root, "manifest.yaml")
	args := append(t.scpBase(node, identity), "-O", "--", manifest, t.destination(node, path.Join(stage, "manifest.yaml")))
	_, err := t.run(ctx, "scp", args, nil)
	return err
}

func (t OpenSSHTransport) ActivateStagedRuntime(ctx context.Context, node Node, stage string, bundle executionbundle.Verified) (Runtime, error) {
	if !validBundleStage(stage) {
		return Runtime{}, errors.New("EXECUTION_BUNDLE_STAGE_INVALID")
	}
	bootstrapScript, activationScript := runtimePreparationScripts(bundle)
	platforms := make([]string, 0, len(bundle.Manifest.Platforms))
	for _, platform := range bundle.Manifest.Platforms {
		platforms = append(platforms, platform.OS+":"+platform.Version+":"+platform.Architecture)
	}
	bootstrap := "0"
	for _, component := range bundle.Manifest.Components {
		if component.Path == runtimeBootstrapComponent {
			bootstrap = "1"
		}
	}
	args := []string{"-n", "sh", "-s", "--", stage, t.runtimeRoot(), bundle.Digest, bundle.Manifest.BundleVersion, bundle.Manifest.CoreVersion, bundle.Manifest.BootstrapProtocol, strings.Join(platforms, " "), bootstrap}
	complete := false
	defer func() {
		if !complete {
			cleanupCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 30*time.Second)
			defer cancel()
			_, _ = t.ssh(cleanupCtx, node, "sudo", []string{"-n", "sh", "-s", "--", stage}, []byte(runtimeCandidateCleanupScript))
		}
	}()
	if _, err := t.ssh(ctx, node, "sudo", args, []byte(bootstrapScript)); err != nil {
		return Runtime{}, err
	}
	if err := ctx.Err(); err != nil {
		return Runtime{}, err
	}
	if _, err := t.ssh(ctx, node, "sudo", args, []byte(activationScript)); err != nil {
		return Runtime{}, err
	}
	complete = true
	return Runtime{BundleVersion: bundle.Manifest.BundleVersion, BundleDigest: bundle.Digest, CoreVersion: bundle.Manifest.CoreVersion, Protocol: bundle.Manifest.BootstrapProtocol, Ansible: true, Capabilities: true}, nil
}
func (t OpenSSHTransport) DiscardStagedRuntime(ctx context.Context, node Node, stage string) error {
	if !validBundleStage(stage) {
		return errors.New("EXECUTION_BUNDLE_STAGE_INVALID")
	}
	_, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte("case \"$1\" in /var/tmp/platform-installer-bootstrap-*) rm -rf -- \"$1\";; *) exit 64;; esac\n"))
	return err
}

func validBundleStage(stage string) bool {
	const prefix = "/var/tmp/platform-installer-bootstrap-"
	if !strings.HasPrefix(stage, prefix) || len(stage) != len(prefix)+32 {
		return false
	}
	suffix := strings.TrimPrefix(stage, prefix)
	if strings.ToLower(suffix) != suffix {
		return false
	}
	_, err := hex.DecodeString(suffix)
	return err == nil
}

// ExecuteService is the production service entrypoint. The source projection
// is ephemeral extra-vars; the project remains the operator-authored input and
// Ansible only gates and executes the already selected source.
func (t OpenSSHTransport) ExecuteService(ctx context.Context, request ServiceExecutionRequest, projections map[string]map[string]artifactsource.Result) (bool, error) {
	playbook, serviceCollections, ok := servicePlaybook(request.Service, request.Operation)
	if !ok || request.ProjectRoot == "" || len(projections) == 0 || !validRemoteSecretFiles(request.PKISecretFiles) {
		return false, errors.New("SERVICE_EXECUTION_INPUT_INVALID")
	}
	archive, err := createProjectArchive(request.ProjectRoot)
	if err != nil {
		return false, err
	}
	defer os.Remove(archive)
	identity, err := t.Identity.IdentityFile(request.Target.CredentialRef)
	if err != nil {
		return false, err
	}
	if request.Target.User == "" || request.Target.HostKey.State != "TRUSTED" || request.Target.HostKey.KnownHosts == "" {
		return false, errors.New("SERVICE_EXECUTION_CONNECTION_POLICY_INVALID")
	}
	knownHosts, err := os.ReadFile(request.Target.HostKey.KnownHosts)
	if err != nil {
		return false, errors.New("SERVICE_EXECUTION_KNOWN_HOSTS_UNAVAILABLE")
	}
	remote := serviceWorkspace(request.Target.ID, request.Service)
	vars, err := os.CreateTemp("", "platform-service-vars-*.json")
	if err != nil {
		return false, err
	}
	varsPath := vars.Name()
	defer os.Remove(varsPath)
	data, err := json.Marshal(map[string]any{
		"platform_resolved_artifact_sources_by_target": projections,
		"platform_resolved_artifact_sources":           "{{ platform_resolved_artifact_sources_by_target[inventory_hostname] | default({}) }}",
		"platform_service_catalog_path":                "/var/lib/platform-installer/runtime/current/catalog/service-catalog.yml",
		"platform_project_manifest_path":               remote + "/project.yml",
		"platform_validation_artifact":                 remote + "/validation-result.json",
		"platform_pki_secret_files":                    request.PKISecretFiles,
		"ansible_user":                                 request.Target.User,
		"ansible_private_key_file":                     remote + "/identity",
		"ansible_ssh_common_args":                      "-o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=" + remote + "/known_hosts",
	})
	if err != nil {
		_ = vars.Close()
		return false, err
	}
	if _, err := vars.Write(data); err != nil {
		_ = vars.Close()
		return false, err
	}
	if err := vars.Close(); err != nil {
		return false, err
	}
	cleanup := func() {
		_, _ = t.ssh(context.Background(), request.Target, "sh", []string{"-s", "--", remote}, []byte("case \"$1\" in /var/tmp/platform-installer/service/*) rm -rf -- \"$1\";; *) exit 64;; esac\n"))
	}
	defer cleanup()
	if _, err := t.ssh(ctx, request.Target, "sh", []string{"-s", "--", remote}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/service/*) ;; *) exit 64;; esac\nrm -rf -- \"$1\"\nmkdir -p -- \"$1\"\n")); err != nil {
		return false, err
	}
	knownHostsFile, err := os.CreateTemp("", "platform-known-hosts-*")
	if err != nil {
		return false, err
	}
	knownHostsPath := knownHostsFile.Name()
	defer os.Remove(knownHostsPath)
	if err := knownHostsFile.Chmod(0o600); err != nil {
		_ = knownHostsFile.Close()
		return false, err
	}
	if _, err := knownHostsFile.Write(knownHosts); err != nil {
		_ = knownHostsFile.Close()
		return false, err
	}
	if err := knownHostsFile.Close(); err != nil {
		return false, err
	}
	for _, pair := range [][2]string{{archive, remote + "/project.tar"}, {varsPath, remote + "/runtime-vars.json"}, {knownHostsPath, remote + "/known_hosts"}, {identity, remote + "/identity"}} {
		args := append(t.scpBase(request.Target, identity), "-O", "--", pair[0], t.destination(request.Target, pair[1]))
		if _, err := t.run(ctx, "scp", args, nil); err != nil {
			return false, err
		}
	}
	script := "set -eu\nroot=/var/lib/platform-installer/runtime/current\nwork=$1\nplaybook=$2\nservice_collections=$3\ncase \"$work\" in /var/tmp/platform-installer/service/*) ;; *) exit 64;; esac\ncase \"$playbook:$service_collections\" in services/kafka/playbooks/apply.yml:services/kafka/ansible_collections|services/kafka/playbooks/verify.yml:services/kafka/ansible_collections|services/keepalived/playbooks/apply.yml:services/keepalived/ansible_collections|services/keepalived/playbooks/verify.yml:services/keepalived/ansible_collections) ;; *) exit 64;; esac\nsudo -n tar -xf \"$work/project.tar\" -C \"$work\"\nsudo -n rm -f -- \"$work/project.tar\"\nsudo -n test -f \"$work/inventory/hosts.yml\"\nsudo -n test -f \"$root/$playbook\"\nsudo -n env ANSIBLE_CONFIG=\"$root/ansible-core/ansible.cfg\" ANSIBLE_COLLECTIONS_PATH=\"$root/ansible-core/collections:$root/$service_collections\" ansible-playbook -i \"$work/inventory/hosts.yml\" \"$root/$playbook\" -e @\"$work/runtime-vars.json\"\nsudo -n rm -f -- \"$work/runtime-vars.json\"\n"
	if _, err := t.ssh(ctx, request.Target, "sh", []string{"-s", "--", remote, playbook, serviceCollections}, []byte(script)); err != nil {
		return false, err
	}
	return true, nil
}

func serviceWorkspace(targetID, service string) string {
	hash := sha256.Sum256([]byte(targetID + "\x00" + service))
	return "/var/tmp/platform-installer/service/run-" + hex.EncodeToString(hash[:8])
}

func servicePlaybook(service, operation string) (string, string, bool) {
	if operation == "" {
		operation = "apply"
	}
	switch service + ":" + operation {
	case "kafka:apply":
		return "services/kafka/playbooks/apply.yml", "services/kafka/ansible_collections", true
	case "kafka:verify":
		return "services/kafka/playbooks/verify.yml", "services/kafka/ansible_collections", true
	case "keepalived:apply":
		return "services/keepalived/playbooks/apply.yml", "services/keepalived/ansible_collections", true
	case "keepalived:verify":
		return "services/keepalived/playbooks/verify.yml", "services/keepalived/ansible_collections", true
	default:
		return "", "", false
	}
}

func createProjectArchive(root string) (string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", errors.New("SERVICE_PROJECT_INVALID")
	}
	info, err := os.Lstat(absolute)
	if err != nil || !info.IsDir() || isUnsafeFilesystemLink(info) {
		return "", errors.New("SERVICE_PROJECT_INVALID")
	}
	for _, required := range []string{"inventory"} {
		entry, statErr := os.Lstat(filepath.Join(absolute, required))
		if statErr != nil || !entry.IsDir() || isUnsafeFilesystemLink(entry) {
			return "", errors.New("SERVICE_PROJECT_INVALID")
		}
	}
	file, err := os.CreateTemp("", "platform-service-project-*.tar")
	if err != nil {
		return "", err
	}
	name := file.Name()
	writer := tar.NewWriter(file)
	cleanup := func(e error) (string, error) {
		_ = writer.Close()
		_ = file.Close()
		_ = os.Remove(name)
		return "", e
	}
	for _, entry := range []string{"inventory", "project.yml", "ansible.cfg", "application-packages", "library-packages"} {
		candidate := filepath.Join(absolute, entry)
		if _, statErr := os.Lstat(candidate); statErr != nil {
			if errors.Is(statErr, os.ErrNotExist) && entry != "inventory" {
				continue
			}
			return cleanup(errors.New("SERVICE_PROJECT_INVALID"))
		}
		if err := appendTarPath(writer, absolute, candidate); err != nil {
			return cleanup(err)
		}
	}
	if err := writer.Close(); err != nil {
		_ = file.Close()
		_ = os.Remove(name)
		return "", err
	}
	if err := file.Close(); err != nil {
		_ = os.Remove(name)
		return "", err
	}
	return name, nil
}

const managedCandidateAnsibleConfig = "# Managed by Platform Installer.\n" +
	"# This is standard Ansible configuration; formatting may be normalized.\n" +
	"[defaults]\n" +
	"inventory = ./inventory/hosts.yml\n" +
	"retry_files_enabled = False\n" +
	"host_key_checking = True\n" +
	"interpreter_python = auto_silent\n" +
	"hash_behaviour = merge\n"

// createCandidateProjectArchive is intentionally narrower than the service
// archive. Only documents frozen by UI-01A cross the Execution Node boundary.
func createCandidateProjectArchive(root string) (string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", errors.New("PROJECT_CANDIDATE_INVALID")
	}
	rootInfo, err := os.Lstat(absolute)
	if err != nil || !rootInfo.IsDir() || isUnsafeFilesystemLink(rootInfo) {
		return "", errors.New("PROJECT_CANDIDATE_INVALID")
	}
	paths := []string{"project.yml", "ansible.cfg", "inventory/hosts.yml"}
	for _, directory := range []string{"inventory/group_vars", "inventory/host_vars", "application-packages", "library-packages"} {
		candidateRoot := filepath.Join(absolute, filepath.FromSlash(directory))
		entry, statErr := os.Lstat(candidateRoot)
		if errors.Is(statErr, os.ErrNotExist) {
			continue
		}
		if statErr != nil || !entry.IsDir() || isUnsafeFilesystemLink(entry) {
			return "", errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
		}
		if walkErr := filepath.WalkDir(candidateRoot, func(current string, entry os.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			info, infoErr := entry.Info()
			if infoErr != nil {
				return infoErr
			}
			if isUnsafeFilesystemLink(info) {
				return errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
			}
			if entry.IsDir() {
				return nil
			}
			if !entry.Type().IsRegular() {
				return errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
			}
			relative, relErr := filepath.Rel(absolute, current)
			if relErr != nil || !containedLocal(absolute, current) {
				return errors.New("PROJECT_CANDIDATE_PATH_INVALID")
			}
			logical := filepath.ToSlash(relative)
			if candidateArchiveLogicalPathAllowed(logical) {
				paths = append(paths, logical)
			}
			return nil
		}); walkErr != nil {
			return "", walkErr
		}
	}
	slices.Sort(paths)

	file, err := os.CreateTemp("", "platform-candidate-project-*.tar")
	if err != nil {
		return "", err
	}
	name := file.Name()
	writer := tar.NewWriter(file)
	cleanup := func(cause error) (string, error) {
		_ = writer.Close()
		_ = file.Close()
		_ = os.Remove(name)
		return "", cause
	}
	limits := projectArchiveLimits{}
	seen := make(map[string]bool, len(paths))
	identities := make([]os.FileInfo, 0, len(paths))
	for _, logical := range paths {
		if !candidateArchiveLogicalPathAllowed(logical) || !utf8.ValidString(logical) || len([]byte(logical)) > 512 {
			return cleanup(errors.New("PROJECT_CANDIDATE_PATH_INVALID"))
		}
		folded := strings.ToLower(logical)
		if seen[folded] {
			return cleanup(errors.New("PROJECT_CANDIDATE_PATH_COLLISION"))
		}
		seen[folded] = true
		content, readErr := readStableCandidateFile(absolute, logical)
		if readErr != nil {
			return cleanup(readErr)
		}
		identity, identityErr := os.Lstat(filepath.Join(absolute, filepath.FromSlash(logical)))
		if identityErr != nil {
			return cleanup(errors.New("PROJECT_CANDIDATE_FILE_REPLACED"))
		}
		for _, previous := range identities {
			if os.SameFile(previous, identity) {
				return cleanup(errors.New("PROJECT_CANDIDATE_HARDLINK_UNSAFE"))
			}
		}
		identities = append(identities, identity)
		if logical == "ansible.cfg" && string(content) != managedCandidateAnsibleConfig {
			return cleanup(errors.New("PROJECT_CANDIDATE_ANSIBLE_CONFIG_INVALID"))
		}
		limits.files++
		limits.bytes += int64(len(content))
		if limits.files > 4096 || len(content) > 4*1024*1024 || limits.bytes > 64*1024*1024 {
			return cleanup(errors.New("PROJECT_CANDIDATE_LIMIT_EXCEEDED"))
		}
		header := &tar.Header{Name: logical, Mode: 0o600, Size: int64(len(content)), Typeflag: tar.TypeReg, Format: tar.FormatPAX}
		if err := writer.WriteHeader(header); err != nil {
			return cleanup(err)
		}
		if _, err := writer.Write(content); err != nil {
			return cleanup(err)
		}
	}
	if err := writer.Close(); err != nil {
		_ = file.Close()
		_ = os.Remove(name)
		return "", err
	}
	if err := file.Close(); err != nil {
		_ = os.Remove(name)
		return "", err
	}
	if info, statErr := os.Stat(name); statErr != nil || info.Size() > 32*1024*1024 {
		_ = os.Remove(name)
		return "", errors.New("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
	}
	return name, nil
}

func candidateArchiveLogicalPathAllowed(logical string) bool {
	if installer.ApplicationPackagePathAllowed(logical) {
		return true
	}
	if logical == "project.yml" || logical == "ansible.cfg" || logical == "inventory/hosts.yml" {
		return true
	}
	if strings.Contains(logical, "\\") || strings.Contains(logical, ":") || path.Clean(logical) != logical || strings.HasPrefix(logical, "/") {
		return false
	}
	extension := strings.ToLower(path.Ext(logical))
	if extension != ".yml" && extension != ".yaml" && extension != ".json" {
		return false
	}
	return strings.HasPrefix(logical, "inventory/group_vars/") || strings.HasPrefix(logical, "inventory/host_vars/")
}

func readStableCandidateFile(root, logical string) ([]byte, error) {
	absolute := filepath.Join(root, filepath.FromSlash(logical))
	if !containedLocal(root, absolute) {
		return nil, errors.New("PROJECT_CANDIDATE_PATH_INVALID")
	}
	before, err := os.Lstat(absolute)
	if err != nil || !before.Mode().IsRegular() || isUnsafeFilesystemLink(before) {
		return nil, errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
	}
	if before.Size() > 4*1024*1024 {
		return nil, errors.New("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
	}
	input, err := os.Open(absolute)
	if err != nil {
		return nil, errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
	}
	defer input.Close()
	opened, err := input.Stat()
	if err != nil || !opened.Mode().IsRegular() || !os.SameFile(before, opened) {
		return nil, errors.New("PROJECT_CANDIDATE_FILE_REPLACED")
	}
	system := reflect.ValueOf(opened.Sys())
	if system.IsValid() && system.Kind() == reflect.Ptr && !system.IsNil() {
		links := system.Elem().FieldByName("Nlink")
		if links.IsValid() && links.CanUint() && links.Uint() > 1 {
			return nil, errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
		}
	}
	if runtime.GOOS == "windows" {
		output, linkErr := exec.Command("fsutil", "hardlink", "list", absolute).CombinedOutput()
		if linkErr != nil {
			// Error 50 means the filesystem itself does not support hardlinks.
			// Other failures cannot prove that the candidate file is single-link.
			if !bytes.Contains(output, []byte("Error 50:")) {
				return nil, errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
			}
		} else {
			lines := strings.Split(strings.TrimSpace(strings.ReplaceAll(string(output), "\r\n", "\n")), "\n")
			if len(lines) != 1 || strings.TrimSpace(lines[0]) == "" {
				return nil, errors.New("PROJECT_CANDIDATE_FILE_UNSAFE")
			}
		}
	}
	content, err := io.ReadAll(io.LimitReader(input, 4*1024*1024+1))
	if err != nil || len(content) > 4*1024*1024 {
		return nil, errors.New("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
	}
	after, err := input.Stat()
	pathAfter, pathErr := os.Lstat(absolute)
	if err != nil || pathErr != nil || !os.SameFile(opened, after) || !os.SameFile(after, pathAfter) || opened.Size() != after.Size() || !opened.ModTime().Equal(after.ModTime()) {
		return nil, errors.New("PROJECT_CANDIDATE_FILE_REPLACED")
	}
	return content, nil
}

type projectArchiveLimits struct{ files, bytes int64 }

func appendTarPath(writer *tar.Writer, root, source string) error {
	return filepath.WalkDir(source, func(current string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(root, current)
		if err != nil || !containedLocal(root, current) {
			return errors.New("SERVICE_PROJECT_PATH_INVALID")
		}
		if relative == "." {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if isUnsafeFilesystemLink(info) {
			return errors.New("SERVICE_PROJECT_SYMLINK_UNSAFE")
		}
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = filepath.ToSlash(relative)
		if err := writer.WriteHeader(header); err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		if !entry.Type().IsRegular() {
			return errors.New("SERVICE_PROJECT_FILE_UNSAFE")
		}
		input, err := os.Open(current)
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(writer, input)
		closeErr := input.Close()
		if copyErr != nil {
			return copyErr
		}
		return closeErr
	})
}

func (t OpenSSHTransport) stageRoot() string {
	if t.StageRoot != "" {
		return t.StageRoot
	}
	return "/var/tmp/platform-installer-bootstrap"
}
func (t OpenSSHTransport) runtimeRoot() string {
	if t.RuntimeRoot != "" {
		return t.RuntimeRoot
	}
	return "/var/lib/platform-installer/runtime"
}
func (t OpenSSHTransport) ssh(ctx context.Context, node Node, program string, args []string, input []byte) ([]byte, error) {
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return nil, err
	}
	return t.withSudoInput(ctx, program, args, input, func(program string, args []string, input []byte) ([]byte, error) {
		full := append(t.base(node, identity), node.User+"@"+node.Address, program)
		full = append(full, args...)
		return t.run(ctx, "ssh", full, input)
	})
}

func (t OpenSSHTransport) sshBounded(ctx context.Context, node Node, program string, args []string, input []byte, limit int) ([]byte, error) {
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return nil, err
	}
	return t.withSudoInput(ctx, program, args, input, func(program string, args []string, input []byte) ([]byte, error) {
		full := append(t.base(node, identity), node.User+"@"+node.Address, program)
		full = append(full, args...)
		return t.runBounded(ctx, "ssh", full, input, limit)
	})
}

func (t OpenSSHTransport) sshSeparatedBounded(ctx context.Context, node Node, program string, args []string, input []byte, stdoutLimit, stderrLimit int) ([]byte, error) {
	identity, err := t.identityFile(node.CredentialRef)
	if err != nil {
		return nil, errors.New("EXECUTION_NODE_TRANSPORT_FAILED")
	}
	return t.withSudoInput(ctx, program, args, input, func(program string, args []string, input []byte) ([]byte, error) {
		full := append(t.base(node, identity), node.User+"@"+node.Address, program)
		full = append(full, args...)
		return t.runSeparatedBounded(ctx, "ssh", full, input, stdoutLimit, stderrLimit)
	})
}

// ProbeTargetHostKey is read-only target host-key discovery from the trusted
// Execution Node. It never accepts a key or alters trust on either machine.
func (t OpenSSHTransport) ProbeTargetHostKey(ctx context.Context, node Node, address string, port uint16) ([]byte, error) {
	if port == 0 || address == "" || len(address) > 253 || strings.ContainsAny(address, " \t\r\n'\";|&$`(){}[]*?!\\") {
		return nil, errors.New("TARGET_HOST_KEY_PROBE_FAILED")
	}
	return t.sshSeparatedBounded(ctx, node, "ssh-keyscan", []string{"-T", "5", "-p", strconv.Itoa(int(port)), "-t", "ed25519,ecdsa,rsa", address}, nil, 16384, 1024)
}
func (t OpenSSHTransport) identityFile(reference string) (string, error) {
	if t.Password != nil {
		return "", nil
	}
	if t.Identity == nil {
		return "", errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return t.Identity.IdentityFile(reference)
}
func (t OpenSSHTransport) base(node Node, identity string) []string {
	args := []string{}
	if t.IsolatedHostKeyTrust {
		args = append(args, "-F", "none", "-o", "GlobalKnownHostsFile=none", "-o", "KnownHostsCommand=none", "-o", "UpdateHostKeys=no")
	}
	args = append(args, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile="+node.HostKey.KnownHosts)
	if t.Password != nil {
		args = append(args, "-o", "BatchMode=no", "-o", "PreferredAuthentications=password", "-o", "PubkeyAuthentication=no", "-o", "KbdInteractiveAuthentication=no", "-o", "NumberOfPasswordPrompts=1")
	} else {
		args = append(args, "-o", "BatchMode=yes", "-i", identity)
	}
	return append(args, "-p", fmt.Sprint(node.Port))
}
func (t OpenSSHTransport) scpBase(node Node, identity string) []string {
	args := t.base(node, identity)
	for i := range args {
		if args[i] == "-p" {
			args[i] = "-P"
		}
	}
	return args
}
func (t OpenSSHTransport) destination(node Node, value string) string {
	return node.User + "@" + node.Address + ":" + value
}
func (t OpenSSHTransport) run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	release, err := t.acquireCommandGuard(ctx)
	if err != nil {
		return nil, err
	}
	defer release()
	runner := t.Runner
	if runner == nil {
		runner = osRunner{password: t.Password}
	}
	out, err := runner.Run(ctx, name, args, input)
	if err != nil {
		detail := strings.TrimSpace(string(out))
		if len(detail) > 512 {
			detail = detail[:512]
		}
		if detail != "" && t.Password == nil && t.SudoPassword == nil {
			return nil, fmt.Errorf("EXECUTION_NODE_TRANSPORT_FAILED:%s:%s", name, detail)
		}
		return nil, fmt.Errorf("EXECUTION_NODE_TRANSPORT_FAILED:%s", name)
	}
	return out, nil
}

func (t OpenSSHTransport) runBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	release, guardErr := t.acquireCommandGuard(ctx)
	if guardErr != nil {
		return nil, guardErr
	}
	defer release()
	runner := t.Runner
	if runner == nil {
		runner = osRunner{password: t.Password}
	}
	var out []byte
	var err error
	if bounded, ok := runner.(boundedCommandRunner); ok {
		out, err = bounded.RunBounded(ctx, name, args, input, limit)
	} else {
		out, err = runner.Run(ctx, name, args, input)
		if len(out) > limit {
			out = out[:limit]
			err = errors.New("EXECUTION_NODE_OUTPUT_LIMIT")
		}
	}
	if err != nil {
		return out, fmt.Errorf("EXECUTION_NODE_TRANSPORT_FAILED:%s", name)
	}
	return out, nil
}

func (t OpenSSHTransport) runSeparatedBounded(ctx context.Context, name string, args []string, input []byte, stdoutLimit, stderrLimit int) ([]byte, error) {
	release, guardErr := t.acquireCommandGuard(ctx)
	if guardErr != nil {
		return nil, guardErr
	}
	defer release()
	runner := t.Runner
	if runner == nil {
		runner = osRunner{password: t.Password}
	}
	separated, ok := runner.(separatedCommandRunner)
	if !ok {
		return nil, errors.New("EXECUTION_NODE_TRANSPORT_FAILED")
	}
	stdout, _, err := separated.RunSeparatedBounded(ctx, name, args, input, stdoutLimit, stderrLimit)
	if err != nil {
		// Keep bounded stdout for closed protocol error decoding only. Stderr
		// and the process error never become diagnostics or secret content.
		return stdout, errors.New("EXECUTION_NODE_TRANSPORT_FAILED")
	}
	return stdout, nil
}

func (t OpenSSHTransport) acquireCommandGuard(ctx context.Context) (func(), error) {
	if t.ContextCommandGuard != nil {
		release, err := t.ContextCommandGuard(ctx)
		if err != nil || release == nil {
			return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
		}
		return release, nil
	}
	if t.CommandGuard == nil {
		return func() {}, nil
	}
	release, err := t.CommandGuard()
	if err != nil || release == nil {
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	return release, nil
}
func remoteChecks(bundle executionbundle.Verified) string {
	var b strings.Builder
	b.WriteString("set -eu\ncd -- \"$1\"\n")
	for _, c := range bundle.Manifest.Components {
		fmt.Fprintf(&b, "test -f %q\n[ \"$(wc -c < %q)\" = %d ]\nprintf '%%s  %%s\\n' %q %q | sha256sum -c -\n", c.Path, c.Path, c.Size, strings.TrimPrefix(c.SHA256, "sha256:"), c.Path)
	}
	return b.String()
}
func parseFacts(raw string) map[string]string {
	values := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			values[parts[0]] = parts[1]
		}
	}
	return values
}
func parseInt64(value string) int64 { var result int64; fmt.Sscan(value, &result); return result }

func containedLocal(root, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}

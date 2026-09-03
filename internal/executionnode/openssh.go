package executionnode

// This adapter is deliberately semantic: all remote paths and shell programs
// are fixed here, while credentials stay behind a runtime-only resolver.

import (
	"archive/tar"
	"bytes"
	"context"
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
	"strings"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/executionbundle"
)

type IdentityResolver interface {
	IdentityFile(credentialRef string) (string, error)
}

type commandRunner interface {
	Run(context.Context, string, []string, []byte) ([]byte, error)
}

type osRunner struct{}

func (osRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	command := exec.CommandContext(ctx, name, args...)
	command.Stdin = bytes.NewReader(input)
	return command.CombinedOutput()
}

// OpenSSHTransport is the one product transport for the pre-Core boundary.
// It never accepts a caller-defined remote command or destination.
type OpenSSHTransport struct {
	Identity       IdentityResolver
	Runner         commandRunner
	RepositoryRoot string
	RuntimeRoot    string
	StageRoot      string
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
	sum := sha256.Sum256([]byte(node.ID))
	remote := "/var/tmp/platform-installer/acquisition/" + hex.EncodeToString(sum[:8])
	cleanup := func() {
		_, _ = t.ssh(context.Background(), node, "sh", []string{"-s", "--", remote}, []byte("case \"$1\" in /var/tmp/platform-installer/acquisition/*) rm -rf -- \"$1\";; *) exit 64;; esac\n"))
	}
	defer cleanup()
	script := "set -eu\ncase \"$1\" in /var/tmp/platform-installer/acquisition/*) ;; *) exit 64;; esac\nrm -rf -- \"$1\"\nmkdir -p -- \"$1\"\nsudo -n dnf -q download --resolve --alldeps --destdir \"$1\" -- python3 ansible-core openssl ca-certificates tar gzip\nrpm=$(find \"$1\" -maxdepth 1 -type f -name '*.rpm' -print -quit)\ntest -n \"$rpm\"\ncd \"$1\"\nsudo -n tar -cf closure.tar -- *.rpm\nsudo -n chmod 0644 closure.tar\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte(script)); err != nil {
		return errors.New("EXECUTION_RUNTIME_CLOSURE_FAILED")
	}
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
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
	id := strings.TrimPrefix(bundle.Digest, "sha256:")
	stage := path.Join(t.stageRoot(), id)
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/bootstrap/*) ;; *) exit 64;; esac\nrm -rf -- \"$1\"\nmkdir -p -- \"$1\"\n")); err != nil {
		return "", err
	}
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return "", err
	}
	archivePath, err := createBundleArchive(bundle)
	if err != nil {
		_ = t.DiscardStagedRuntime(context.Background(), node, stage)
		return "", err
	}
	defer os.Remove(archivePath)
	archiveRemote := stage + ".tar"
	args := append(t.scpBase(node, identity), "-O", "--", archivePath, t.destination(node, archiveRemote))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		_ = t.DiscardStagedRuntime(context.Background(), node, stage)
		return "", err
	}
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage, archiveRemote}, []byte("set -eu\nstage=$1; archive=$2\ncase \"$stage:$archive\" in /var/tmp/platform-installer/bootstrap/*:/var/tmp/platform-installer/bootstrap/*.tar) ;; *) exit 64;; esac\ntar -xf \"$archive\" -C \"$stage\"\nrm -f -- \"$archive\"\n")); err != nil {
		_ = t.DiscardStagedRuntime(context.Background(), node, stage)
		return "", err
	}
	script := remoteChecks(bundle)
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte(script)); err != nil {
		_ = t.DiscardStagedRuntime(context.Background(), node, stage)
		return "", err
	}
	return stage, nil
}

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
	id := strings.TrimPrefix(bundle.Digest, "sha256:")
	root := t.runtimeRoot()
	release := path.Join(root, "releases", id)
	candidate := stage
	script := "set -eu\nstage=$1; release=$2; root=$3; bundle_digest=$4; bundle_version=$5; core_version=$6; protocol=$7\ncase \"$stage:$release:$root\" in /var/tmp/platform-installer/bootstrap/*:/var/lib/platform-installer/runtime/releases/*:/var/lib/platform-installer/runtime) ;; *) exit 64;; esac\ncase \"$bundle_digest\" in sha256:*) ;; *) exit 64;; esac\nsudo -n install -d -m 0750 \"$root/releases\" \"$root/state\"\nsudo -n rm -rf -- \"$release\"\nsudo -n cp -a -- \"$stage\" \"$release\"\nsudo -n test -f \"$release/manifest.yaml\"\nsudo -n test -f \"$release/ansible-core/playbooks/execution-capabilities.yml\"\nsudo -n env ANSIBLE_CONFIG=\"$release/ansible-core/ansible.cfg\" ANSIBLE_COLLECTIONS_PATH=\"$release/ansible-core/collections\" ansible-playbook -i localhost, \"$release/ansible-core/playbooks/execution-capabilities.yml\" -e \"platform_execution_runtime_root=$release\" -e \"platform_execution_bundle_digest=$bundle_digest\" >/dev/null\nsudo -n sh -c 'umask 077; printf \"BUNDLE_VERSION=%s\\nBUNDLE_DIGEST=%s\\nCORE_VERSION=%s\\nPROTOCOL=%s\\nANSIBLE=yes\\nCAPABILITIES=yes\\n\" \"$1\" \"$2\" \"$3\" \"$4\" > \"$5.new\"; mv -f -- \"$5.new\" \"$5\"' -- \"$bundle_version\" \"$bundle_digest\" \"$core_version\" \"$protocol\" \"$root/state/active\"\nsudo -n ln -sfn -- \"$release\" \"$root/current.new\"\nsudo -n mv -Tf -- \"$root/current.new\" \"$root/current\"\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", candidate, release, root, bundle.Digest, bundle.Manifest.BundleVersion, bundle.Manifest.CoreVersion, bundle.Manifest.BootstrapProtocol}, []byte(script)); err != nil {
		return Runtime{}, err
	}
	return Runtime{BundleVersion: bundle.Manifest.BundleVersion, BundleDigest: bundle.Digest, CoreVersion: bundle.Manifest.CoreVersion, Protocol: bundle.Manifest.BootstrapProtocol, Ansible: true, Capabilities: true}, nil
}
func (t OpenSSHTransport) DiscardStagedRuntime(ctx context.Context, node Node, stage string) error {
	_, err := t.ssh(ctx, node, "sh", []string{"-s", "--", stage}, []byte("case \"$1\" in /var/tmp/platform-installer/bootstrap/*) rm -rf -- \"$1\";; *) exit 64;; esac\n"))
	return err
}

// ExecuteService is the production service entrypoint. The source projection
// is ephemeral extra-vars; the project remains the operator-authored input and
// Ansible only gates and executes the already selected source.
func (t OpenSSHTransport) ExecuteService(ctx context.Context, request ServiceExecutionRequest, projections map[string]map[string]artifactsource.Result) (bool, error) {
	playbook, serviceCollections, ok := servicePlaybook(request.Service, request.Operation)
	if !ok || request.ProjectRoot == "" || len(projections) == 0 {
		return false, errors.New("SERVICE_EXECUTION_INPUT_INVALID")
	}
	archive, err := createProjectArchive(request.ProjectRoot)
	if err != nil {
		return false, err
	}
	defer os.Remove(archive)
	hash := sha256.Sum256([]byte(request.Target.ID + "\x00" + request.Service))
	remote := "/var/tmp/platform-installer/service/" + hex.EncodeToString(hash[:8])
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
		"platform_validation_artifact":                 remote + "/validation-result.json",
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
	identity, err := t.Identity.IdentityFile(request.Target.CredentialRef)
	if err != nil {
		return false, err
	}
	cleanup := func() {
		_, _ = t.ssh(context.Background(), request.Target, "sh", []string{"-s", "--", remote}, []byte("case \"$1\" in /var/tmp/platform-installer/service/*) rm -rf -- \"$1\";; *) exit 64;; esac\n"))
	}
	defer cleanup()
	if _, err := t.ssh(ctx, request.Target, "sh", []string{"-s", "--", remote}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/service/*) ;; *) exit 64;; esac\nrm -rf -- \"$1\"\nmkdir -p -- \"$1\"\n")); err != nil {
		return false, err
	}
	for _, pair := range [][2]string{{archive, remote + "/project.tar"}, {varsPath, remote + "/runtime-vars.json"}} {
		args := append(t.scpBase(request.Target, identity), "-O", "--", pair[0], t.destination(request.Target, pair[1]))
		if _, err := t.run(ctx, "scp", args, nil); err != nil {
			return false, err
		}
	}
	script := "set -eu\nroot=/var/lib/platform-installer/runtime/current\nwork=$1\nplaybook=$2\nservice_collections=$3\ncase \"$work\" in /var/tmp/platform-installer/service/*) ;; *) exit 64;; esac\ncase \"$playbook:$service_collections\" in services/kafka/playbooks/apply.yml:services/kafka/ansible_collections|services/kafka/playbooks/verify.yml:services/kafka/ansible_collections|services/keepalived/playbooks/apply.yml:services/keepalived/ansible_collections|services/keepalived/playbooks/verify.yml:services/keepalived/ansible_collections) ;; *) exit 64;; esac\nsudo -n tar -xf \"$work/project.tar\" -C \"$work\"\nsudo -n rm -f -- \"$work/project.tar\"\nsudo -n test -d \"$work/inventory\"\nsudo -n test -f \"$root/$playbook\"\nsudo -n env ANSIBLE_CONFIG=\"$root/ansible-core/ansible.cfg\" ANSIBLE_COLLECTIONS_PATH=\"$root/ansible-core/collections:$root/$service_collections\" ansible-playbook -i \"$work/inventory\" \"$root/$playbook\" -e @\"$work/runtime-vars.json\"\nsudo -n rm -f -- \"$work/runtime-vars.json\"\n"
	if _, err := t.ssh(ctx, request.Target, "sh", []string{"-s", "--", remote, playbook, serviceCollections}, []byte(script)); err != nil {
		return false, err
	}
	return true, nil
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
	info, err := os.Stat(absolute)
	if err != nil || !info.IsDir() {
		return "", errors.New("SERVICE_PROJECT_INVALID")
	}
	for _, required := range []string{"inventory"} {
		entry, statErr := os.Stat(filepath.Join(absolute, required))
		if statErr != nil || !entry.IsDir() {
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
	for _, entry := range []string{"inventory", "project.yml", "ansible.cfg"} {
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

func appendTarPath(writer *tar.Writer, root, source string) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return errors.New("SERVICE_PROJECT_SYMLINK_UNSAFE")
		}
		relative, err := filepath.Rel(root, path)
		if err != nil || !containedLocal(root, path) {
			return errors.New("SERVICE_PROJECT_PATH_INVALID")
		}
		if relative == "." {
			return nil
		}
		fileInfo, err := entry.Info()
		if err != nil {
			return err
		}
		header, err := tar.FileInfoHeader(fileInfo, "")
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
		input, err := os.Open(path)
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
	return "/var/tmp/platform-installer/bootstrap"
}
func (t OpenSSHTransport) runtimeRoot() string {
	if t.RuntimeRoot != "" {
		return t.RuntimeRoot
	}
	return "/var/lib/platform-installer/runtime"
}
func (t OpenSSHTransport) ssh(ctx context.Context, node Node, program string, args []string, input []byte) ([]byte, error) {
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return nil, err
	}
	full := append(t.base(node, identity), node.User+"@"+node.Address, program)
	full = append(full, args...)
	return t.run(ctx, "ssh", full, input)
}
func (t OpenSSHTransport) base(node Node, identity string) []string {
	return []string{"-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + node.HostKey.KnownHosts, "-i", identity, "-p", fmt.Sprint(node.Port)}
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
	runner := t.Runner
	if runner == nil {
		runner = osRunner{}
	}
	out, err := runner.Run(ctx, name, args, input)
	if err != nil {
		detail := strings.TrimSpace(string(out))
		if len(detail) > 512 {
			detail = detail[:512]
		}
		if detail != "" {
			return nil, fmt.Errorf("EXECUTION_NODE_TRANSPORT_FAILED:%s:%s", name, detail)
		}
		return nil, fmt.Errorf("EXECUTION_NODE_TRANSPORT_FAILED:%s", name)
	}
	return out, nil
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

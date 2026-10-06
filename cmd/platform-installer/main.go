package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"platform-installer/internal/artifactsource"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
)

type fileIdentity struct{ path string }

func (i fileIdentity) IdentityFile(string) (string, error) {
	if i.path == "" {
		return "", errors.New("runtime identity is unavailable")
	}
	return i.path, nil
}

// executionNodeBundleBuilder is the production bundle builder. Python and
// Ansible Core run only on the trusted execution node.
type executionNodeBundleBuilder struct {
	transport executionnode.OpenSSHTransport
}

func (b executionNodeBundleBuilder) BuildOnExecutionNode(ctx context.Context, node executionnode.Node, input, version, core string) (string, error) {
	return b.transport.BuildOnExecutionNode(ctx, node, input, version, core)
}

func main() {
	flag.Usage = func() {
		writeCLIUsage(flag.CommandLine.Output())
		flag.PrintDefaults()
	}
	command := flag.String("command", "", "CLI operation; see -help for the complete list")
	runID := flag.String("run-id", "", "execution-watch: required explicit run ID")
	nodeID := flag.String("node-id", "", "execution-watch: stable node ID (default external-<address>)")
	runtimeRoot := flag.String("runtime-root", ".runtime", "execution-watch: Installer runtime root for the local derived event mirror")
	after := flag.Int("after", 0, "execution-watch: stdout sequence checkpoint; follows until terminal, Ctrl+C detaches only. Exit: 0 succeeded, 1 remote failed/cancelled/interrupted, 2 invalid input, 3 observer/local failure (remote outcome unchanged), 130 detached")
	address := flag.String("address", "", "Execution Node address")
	user := flag.String("user", "", "Execution Node user")
	identity := flag.String("identity", "", "runtime SSH identity path")
	knownHosts := flag.String("known-hosts", "", "trusted known_hosts path")
	fingerprint := flag.String("fingerprint", "", "operator-approved host fingerprint")
	bundle := flag.String("bundle", "", "explicit verified bundle root")
	cacheRoot := flag.String("cache", "cache", "local immutable bundle cache")
	port := flag.Uint("port", 22, "SSH port")
	version := flag.String("bundle-version", "", "acquisition bundle version")
	artifact := flag.String("artifact", "", "explicit DEV artifact file outside the bundle cache")
	artifactRef := flag.String("artifact-ref", "", "bundle-relative runtime artifact reference")
	artifactSHA := flag.String("artifact-sha256", "", "expected artifact SHA-256")
	requirementID := flag.String("requirement-id", "", "artifact requirement ID")
	requirementName := flag.String("requirement-name", "", "repository package name")
	requirementVersion := flag.String("requirement-version", "", "required package version")
	requirementOS := flag.String("requirement-os", "", "target OS")
	requirementArchitecture := flag.String("requirement-architecture", "", "target architecture")
	flag.Parse()
	if *command == "execution-watch" {
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		code := executionWatch(ctx, watchOptions{runID: *runID, nodeID: *nodeID, runtimeRoot: *runtimeRoot, after: *after, address: *address, user: *user, identity: *identity, knownHosts: *knownHosts, fingerprint: *fingerprint, port: *port}, os.Stdout, os.Stderr, newWatchBackend)
		stop()
		os.Exit(code)
	}
	if *command == "validate-bundle" {
		if *bundle == "" {
			fatal("EXECUTION_BUNDLE_INPUT_INVALID")
		}
		result, err := executionbundle.ValidateRoot(*bundle)
		if err != nil {
			fatal(err.Error())
		}
		output(result)
		return
	}
	if *command == "publish-bundle" {
		if *bundle == "" || *cacheRoot == "" {
			fatal("EXECUTION_BUNDLE_INPUT_INVALID")
		}
		result, err := (executionbundle.Cache{Root: *cacheRoot}).Publish(*bundle)
		if err != nil {
			fatal(err.Error())
		}
		output(result)
		return
	}
	if *command == "import-artifact" {
		if *bundle == "" || *cacheRoot == "" || *artifact == "" || *artifactRef == "" || *artifactSHA == "" || *version == "" || *address == "" || *user == "" || *identity == "" || *knownHosts == "" || *fingerprint == "" || *port > 65535 {
			fatal("EXECUTION_ARTIFACT_IMPORT_INPUT_INVALID")
		}
		if insideBundleCache(*artifact, *cacheRoot) {
			fatal("EXECUTION_ARTIFACT_IMPORT_SOURCE_INVALID")
		}
		verified, err := executionbundle.ValidateRoot(*bundle)
		if err != nil {
			fatal(err.Error())
		}
		input, cleanup, err := executionbundle.PrepareRuntimeInput(verified, *artifact, *artifactRef, *artifactSHA)
		if err != nil {
			fatal(err.Error())
		}
		defer cleanup()
		repositoryRoot, err := filepath.Abs(".")
		if err != nil {
			fatal("EXECUTION_ARTIFACT_IMPORT_BUILD_FAILED")
		}
		node := executionnode.Node{ID: "artifact-import@" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
		transport := executionnode.OpenSSHTransport{Identity: fileIdentity{*identity}, RepositoryRoot: repositoryRoot}
		builder := executionNodeBundleBuilder{transport: transport}
		builtRoot, err := builder.BuildOnExecutionNode(context.Background(), node, input, *version, verified.Manifest.CoreVersion)
		if err != nil {
			fatal("EXECUTION_ARTIFACT_IMPORT_BUILD_FAILED: " + err.Error())
		}
		defer os.RemoveAll(builtRoot)
		built, err := executionbundle.ValidateRoot(builtRoot)
		if err != nil {
			fatal("EXECUTION_ARTIFACT_IMPORT_BUILD_FAILED")
		}
		published, err := (executionbundle.Cache{Root: *cacheRoot}).Publish(built.Root)
		if err != nil {
			fatal("EXECUTION_ARTIFACT_IMPORT_PUBLICATION_FAILED")
		}
		output(published)
		return
	}
	if *command == "probe-repository" {
		if *address == "" || *user == "" || *identity == "" || *knownHosts == "" || *fingerprint == "" || *requirementID == "" || *requirementName == "" || *requirementOS == "" || *requirementArchitecture == "" || *port > 65535 {
			fatal("REPOSITORY_PROBE_INPUT_INVALID")
		}
		node := executionnode.Node{ID: *requirementID + "@" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
		transport := executionnode.OpenSSHTransport{Identity: fileIdentity{*identity}}
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		result, err := transport.ProbeRepository(ctx, node, artifactsource.Requirement{ID: *requirementID, Name: *requirementName, Version: *requirementVersion, OS: *requirementOS, Architecture: *requirementArchitecture})
		if err != nil {
			fatal(err.Error())
		}
		output(result)
		return
	}
	if *command == "" || *address == "" || *user == "" || *identity == "" || *knownHosts == "" || *fingerprint == "" || *port > 65535 {
		fatal("EXECUTION_NODE_INPUT_INVALID")
	}
	node := executionnode.Node{ID: "external-" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
	transport := executionnode.OpenSSHTransport{Identity: fileIdentity{*identity}}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	switch *command {
	case "inspect":
		result, err := transport.InspectExecutionNode(ctx, node)
		if err != nil {
			fatal("EXECUTION_NODE_INSPECT_FAILED")
		}
		output(result)
	case "acquire":
		if *cacheRoot == "" || *version == "" {
			fatal("EXECUTION_ACQUISITION_INPUT_INVALID")
		}
		repositoryRoot, err := filepath.Abs(".")
		if err != nil {
			fatal("EXECUTION_ACQUISITION_INPUT_INVALID")
		}
		transport.RepositoryRoot = repositoryRoot
		builder := executionNodeBundleBuilder{transport: transport}
		service := executionnode.NewAcquisitionService(transport, builder, executionbundle.Cache{Root: *cacheRoot})
		result, err := service.AcquireExecutionRuntime(ctx, node, *version)
		if err != nil {
			fatal(err.Error())
		}
		output(result)
	case "prepare":
		if *cacheRoot == "" {
			fatal("EXECUTION_BUNDLE_CACHE_INVALID")
		}
		service := executionnode.NewService(transport, executionnode.WithBundleCache(executionbundle.Cache{Root: *cacheRoot}))
		plan, err := service.PlanExecutionNodePreparation(ctx, node, *bundle)
		if err != nil {
			fatal("EXECUTION_NODE_PLAN_FAILED")
		}
		result, err := service.Prepare(ctx, node, *bundle, plan.ID)
		if err != nil {
			fatal(err.Error())
		}
		output(result)
	default:
		fatal("EXECUTION_NODE_COMMAND_INVALID")
	}
}

func writeCLIUsage(w io.Writer) {
	fmt.Fprintln(w, "Platform Installer CLI (developer/operator tools; project bundle updates are performed in the desktop UI).")
	fmt.Fprintln(w, "Usage: platform-installer -command <name> [flags]")
	fmt.Fprintln(w, "Commands:")
	fmt.Fprintln(w, "  validate-bundle   Verify a supplied immutable bundle (-bundle). Does not publish it.")
	fmt.Fprintln(w, "  publish-bundle    Verify and publish a bundle into the local immutable cache (-bundle, -cache).")
	fmt.Fprintln(w, "  import-artifact   DEV-only: rebuild a bundle with an explicit verified artifact on a trusted node.")
	fmt.Fprintln(w, "  inspect           Inspect a trusted Execution Node.")
	fmt.Fprintln(w, "  acquire           DEV-only: acquire a runtime bundle on a trusted acquisition node.")
	fmt.Fprintln(w, "  prepare           Prepare a selected Execution Node using a verified bundle.")
	fmt.Fprintln(w, "  probe-repository  Probe a target node's approved repository for one artifact requirement.")
	fmt.Fprintln(w, "  execution-watch   Follow an existing run's detailed events without changing its outcome.")
	fmt.Fprintln(w, "Developer bundle preparation on a trusted environment with Python/Core:")
	fmt.Fprintln(w, "  python ansible-core/tools/build_execution_runtime_bundle.py --runtime-input <runtime-dir> --output <new-bundle-dir> --bundle-version <version> --core-version <version>")
	fmt.Fprintln(w, "  platform-installer -command validate-bundle -bundle <new-bundle-dir>")
	fmt.Fprintln(w, "Transfer the entire validated bundle directory through the approved channel into <project>/bundle; the desktop UI detects it and requires explicit Bind confirmation.")
	fmt.Fprintln(w, "Flags:")
}

func insideBundleCache(source, cache string) bool {
	absoluteSource, sourceErr := filepath.Abs(source)
	absoluteCache, cacheErr := filepath.Abs(cache)
	if sourceErr != nil || cacheErr != nil {
		return true
	}
	relative, err := filepath.Rel(absoluteCache, absoluteSource)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) && !filepath.IsAbs(relative)
}

func output(value any)  { encoded, _ := json.Marshal(value); fmt.Println(string(encoded)) }
func fatal(code string) { fmt.Fprintln(os.Stderr, code); os.Exit(1) }

// qa-runtime-promote is a DEV/QA-only resumable promotion helper. It is never
// called by the Installer UI or production Execution Node lifecycle.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/qapromotion"
)

type identity struct{ path string }

func (i identity) IdentityFile(string) (string, error) { return i.path, nil }

func main() {
	project := flag.String("project", "", "explicit cumulative QA project root")
	checkpointRoot := flag.String("runtime-root", ".runtime/qa", "runtime-only QA checkpoint root")
	cache := flag.String("cache", "bundle", "immutable bundle cache")
	expectedArtifact := flag.String("expected-artifact-digest", "", "current project artifact lock digest")
	expectedCatalog := flag.String("expected-catalog-digest", "", "current project catalog lock digest")
	publishedDigest := flag.String("published-digest", "", "explicit already-published bundle digest to resume; never selects latest")
	runtimeInput := flag.String("runtime-input", "", "verified runtime input for a new build; retained only before publish")
	bundleVersion := flag.String("bundle-version", "", "new immutable bundle version")
	address := flag.String("address", "", "trusted QA Execution Node address")
	user := flag.String("user", "", "trusted QA Execution Node user")
	identityPath := flag.String("identity", "", "runtime-only SSH identity")
	knownHosts := flag.String("known-hosts", "", "trusted SSH known_hosts")
	fingerprint := flag.String("fingerprint", "", "approved SSH host fingerprint")
	port := flag.Uint("port", 22, "SSH port")
	flag.Parse()
	if *project == "" || *expectedArtifact == "" || *expectedCatalog == "" || (*publishedDigest == "" && (*runtimeInput == "" || *bundleVersion == "")) || *address == "" || *user == "" || *identityPath == "" || *knownHosts == "" || *fingerprint == "" || *port == 0 || *port > 65535 {
		fatal("QA_RUNTIME_PROMOTION_INPUT_INVALID")
	}
	repoRoot, err := filepath.Abs(".")
	if err != nil {
		fatal("QA_RUNTIME_PROMOTION_INPUT_INVALID")
	}
	node := executionnode.Node{ID: "qa-runtime-promotion@" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
	transport := executionnode.OpenSSHTransport{Identity: identity{*identityPath}, RepositoryRoot: repoRoot}
	service := executionnode.NewService(transport, executionnode.WithBundleCache(executionbundle.Cache{Root: *cache}))
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	result, err := qapromotion.Promote(ctx, qapromotion.Request{CheckpointRoot: *checkpointRoot, CacheRoot: *cache, ProjectRoot: *project, ExpectedArtifactDigest: *expectedArtifact, ExpectedCatalogDigest: *expectedCatalog, PublishedDigest: *publishedDigest, RuntimeInput: *runtimeInput, BundleVersion: *bundleVersion, Node: node}, qapromotion.Dependencies{
		Build: func(ctx context.Context, node executionnode.Node, input, version string) (executionbundle.Verified, error) {
			built, err := transport.BuildOnExecutionNode(ctx, node, input, version, "")
			if err != nil {
				return executionbundle.Verified{}, err
			}
			return executionbundle.ValidateRoot(built)
		},
		Publish: func(_ context.Context, bundle executionbundle.Verified) (executionbundle.Verified, error) {
			return (executionbundle.Cache{Root: *cache}).Publish(bundle.Root)
		},
		CleanupBuild: func(bundle executionbundle.Verified) { _ = os.RemoveAll(filepath.Dir(bundle.Root)) },
		Prepare: func(ctx context.Context, node executionnode.Node, bundle executionbundle.Verified) (executionnode.Result, error) {
			plan, err := service.PlanExecutionNodePreparation(ctx, node, bundle.Root)
			if err != nil {
				return executionnode.Result{}, err
			}
			return service.Prepare(ctx, node, bundle.Root, plan.ID)
		},
		UpdateLocks: installer.NewBackend(nil).UpdateRuntimeLockSet,
		ReadLocks:   qapromotion.ReadLocks,
	})
	if err != nil {
		fatal(err.Error())
	}
	encoded, _ := json.Marshal(result)
	fmt.Println(string(encoded))
}

func fatal(message string) { fmt.Fprintln(os.Stderr, message); os.Exit(1) }

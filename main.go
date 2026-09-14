package main

import (
	"context"
	"embed"
	"errors"
	"flag"
	"os"
	"path/filepath"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/projectlifecycle"
)

//go:embed all:frontend/dist
var assets embed.FS

type desktopIdentity struct{ path string }

func (i desktopIdentity) IdentityFile(string) (string, error) {
	if i.path == "" {
		return "", errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return i.path, nil
}

func main() {
	address := flag.String("execution-node-address", "", "READY Execution Node address")
	user := flag.String("execution-node-user", "", "Execution Node SSH user")
	identity := flag.String("execution-node-identity", "", "runtime-only SSH identity path")
	knownHosts := flag.String("execution-node-known-hosts", "", "trusted known_hosts path")
	fingerprint := flag.String("execution-node-fingerprint", "", "operator-approved host fingerprint")
	port := flag.Uint("execution-node-port", 22, "Execution Node SSH port")
	bundle := flag.String("execution-bundle", "", "verified local runtime bundle root")
	flag.Parse()
	bundleRoot := resolveBundleRoot(*bundle)

	var reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	reader = unavailableProjectReader{}
	sources := map[string]string{}
	if bundleRoot != "" {
		if _, err := executionbundle.ValidateRoot(bundleRoot); err == nil {
			sources[projectlifecycle.DefaultCompatibilitySourceID] = bundleRoot
		}
	}
	if *address != "" && *user != "" && *identity != "" && *knownHosts != "" && *fingerprint != "" && bundleRoot != "" && *port > 0 && *port <= 65535 {
		if verified, err := executionbundle.ValidateRoot(bundleRoot); err == nil {
			node := executionnode.Node{ID: "desktop-" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
			release := map[string]any{"bundleDigest": verified.Digest, "coreVersion": verified.Manifest.CoreVersion, "catalogDigest": verified.Manifest.CatalogDigest, "planningProtocol": executionbundle.ProtocolVersion}
			reader = projectReader{transport: executionnode.OpenSSHTransport{Identity: desktopIdentity{*identity}}, node: node, runtimeRelease: release}
		}
	}
	applicationConfig, applicationConfigErr := loadApplicationConfig()
	app := NewApp(reader, projectlifecycle.NewService(sources), WithApplicationConfig(applicationConfig, applicationConfigErr))
	if err := wails.Run(&options.App{Title: "Platform Installer", Width: 1280, Height: 800, MinWidth: 1024, MinHeight: 720, AssetServer: &assetserver.Options{Assets: assets}, OnStartup: app.startup, OnShutdown: app.shutdown, Bind: []interface{}{app}}); err != nil {
		_, _ = os.Stderr.WriteString(err.Error() + "\n")
	}
}

func loadApplicationConfig() (appconfig.Config, error) {
	workingDirectory, _ := os.Getwd()
	executable, _ := os.Executable()
	path, err := appconfig.ResolveDevelopmentPath(workingDirectory, executable)
	if err != nil {
		return appconfig.Config{}, err
	}
	return appconfig.Load(path)
}

// resolveBundleRoot accepts an explicit operator path first. For the
// development desktop executable it additionally recognizes the repository's
// single immutable cache at <repo>/bundle/<digest>, relative to build/bin.
// Every candidate is still fully verified before it becomes a source.
func resolveBundleRoot(explicit string) string {
	if explicit != "" {
		return explicit
	}
	executable, err := os.Executable()
	if err != nil {
		return ""
	}
	cacheRoot := bundleCacheDirectory(executable)
	entries, err := os.ReadDir(cacheRoot)
	if err != nil {
		return ""
	}
	var found string
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		candidate := filepath.Join(cacheRoot, entry.Name())
		if _, err := executionbundle.ValidateRoot(candidate); err != nil {
			continue
		}
		if found != "" {
			return ""
		}
		found = candidate
	}
	return found
}

func bundleCacheDirectory(executable string) string {
	return filepath.Clean(filepath.Join(filepath.Dir(executable), "..", "..", "bundle"))
}

package main

import (
	"context"
	"embed"
	"errors"
	"flag"
	"os"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
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

	var reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	}
	reader = unavailableProjectReader{}
	if *address != "" && *user != "" && *identity != "" && *knownHosts != "" && *fingerprint != "" && *bundle != "" && *port > 0 && *port <= 65535 {
		if verified, err := executionbundle.ValidateRoot(*bundle); err == nil {
			node := executionnode.Node{ID: "desktop-" + *address, Address: *address, User: *user, Port: uint16(*port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: *knownHosts, Fingerprint: *fingerprint}}
			release := map[string]any{"bundleDigest": verified.Digest, "coreVersion": verified.Manifest.CoreVersion, "catalogDigest": verified.Manifest.CatalogDigest, "planningProtocol": executionbundle.ProtocolVersion}
			reader = projectReader{transport: executionnode.OpenSSHTransport{Identity: desktopIdentity{*identity}}, node: node, runtimeRelease: release}
		}
	}
	app := NewApp(reader)
	if err := wails.Run(&options.App{Title: "Platform Installer", Width: 1280, Height: 800, MinWidth: 1024, MinHeight: 720, AssetServer: &assetserver.Options{Assets: assets}, OnStartup: app.startup, Bind: []interface{}{app}}); err != nil {
		_, _ = os.Stderr.WriteString(err.Error() + "\n")
	}
}

//go:build !browser

package main

import (
	"embed"
	"flag"
	"os"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	address := flag.String("execution-node-address", "", "READY Execution Node address")
	user := flag.String("execution-node-user", "", "Execution Node SSH user")
	identity := flag.String("execution-node-identity", "", "runtime-only SSH identity path")
	knownHosts := flag.String("execution-node-known-hosts", "", "trusted known_hosts path")
	fingerprint := flag.String("execution-node-fingerprint", "", "operator-approved host fingerprint")
	port := flag.Uint("execution-node-port", 22, "Execution Node SSH port")
	bundle := flag.String("execution-bundle", "", "verified local runtime bundle root")
	flag.Parse()

	app, err := newConfiguredApp(
		appLaunchSettings{
			address: *address, user: *user, identity: *identity,
			knownHosts: *knownHosts, fingerprint: *fingerprint,
			port: *port, bundle: *bundle,
		},
		wailsDialogProvider{},
		wailsEventPublisher{},
	)
	if err != nil {
		_, _ = os.Stderr.WriteString("QA_SECRET_FILE_SELECTION_INVALID\n")
		return
	}
	if err := wails.Run(&options.App{
		Title: "Platform Installer", Width: 1280, Height: 800,
		MinWidth: 1024, MinHeight: 720,
		AssetServer: &assetserver.Options{Assets: assets},
		OnStartup:   app.startup, OnShutdown: app.shutdown,
		Bind: []interface{}{app},
	}); err != nil {
		_, _ = os.Stderr.WriteString(err.Error() + "\n")
	}
}

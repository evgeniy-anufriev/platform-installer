//go:build !browser

package main

import (
	"embed"
	"flag"
	"os"
	"platform-installer/internal/desktop"
	"platform-installer/internal/sshpassword"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:frontend/dist
var assets embed.FS

// App preserves the Wails binding namespace while the implementation lives in
// the internal desktop package.
type App struct{ *desktop.App }

func main() {
	if sshpassword.Dispatch() {
		return
	}
	address := flag.String("execution-node-address", "", "READY Execution Node address")
	user := flag.String("execution-node-user", "", "Execution Node SSH user")
	identity := flag.String("execution-node-identity", "", "runtime-only SSH identity path")
	knownHosts := flag.String("execution-node-known-hosts", "", "trusted known_hosts path")
	fingerprint := flag.String("execution-node-fingerprint", "", "operator-approved host fingerprint")
	port := flag.Uint("execution-node-port", 22, "Execution Node SSH port")
	bundle := flag.String("execution-bundle", "", "verified local runtime bundle root")
	flag.Parse()

	app, err := desktop.NewWailsApp(desktop.LaunchSettings{
		Address: *address, User: *user, Identity: *identity,
		KnownHosts: *knownHosts, Fingerprint: *fingerprint,
		Port: *port, Bundle: *bundle,
	})
	if err != nil {
		_, _ = os.Stderr.WriteString("QA_SECRET_FILE_SELECTION_INVALID\n")
		return
	}
	onStartup, onShutdown := desktop.WailsLifecycle(app)
	if err := wails.Run(&options.App{
		Title: "Platform Installer", Width: 1280, Height: 800,
		MinWidth: 1024, MinHeight: 720,
		AssetServer: &assetserver.Options{Assets: assets},
		OnStartup:   onStartup, OnShutdown: onShutdown,
		Bind: []interface{}{&App{App: app}},
	}); err != nil {
		_, _ = os.Stderr.WriteString(err.Error() + "\n")
	}
}

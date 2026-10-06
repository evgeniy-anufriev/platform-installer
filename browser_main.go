//go:build browser && windows

package main

import (
	"context"
	"embed"
	"flag"
	"io/fs"
	"os"
	"os/signal"
)

//go:embed all:frontend/dist
var browserAssets embed.FS

func main() {
	address := flag.String("execution-node-address", "", "READY Execution Node address")
	user := flag.String("execution-node-user", "", "Execution Node SSH user")
	identity := flag.String("execution-node-identity", "", "runtime-only SSH identity path")
	knownHosts := flag.String("execution-node-known-hosts", "", "trusted known_hosts path")
	fingerprint := flag.String("execution-node-fingerprint", "", "operator-approved host fingerprint")
	port := flag.Uint("execution-node-port", 22, "Execution Node SSH port")
	bundle := flag.String("execution-bundle", "", "verified local runtime bundle root")
	flag.Parse()

	events := newBrowserEventHub()
	app, err := newConfiguredApp(appLaunchSettings{address: *address, user: *user, identity: *identity, knownHosts: *knownHosts, fingerprint: *fingerprint, port: *port, bundle: *bundle}, newBrowserDialogProvider(), events)
	if err != nil {
		_, _ = os.Stderr.WriteString("BROWSER_APPLICATION_START_FAILED\n")
		return
	}
	webRoot, err := fs.Sub(browserAssets, "frontend/dist")
	if err != nil {
		_, _ = os.Stderr.WriteString("BROWSER_ASSETS_UNAVAILABLE\n")
		return
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	if err := runBrowserHost(ctx, app, webRoot, events); err != nil {
		_, _ = os.Stderr.WriteString("BROWSER_HOST_FAILED\n")
	}
}

//go:build browser && linux

package main

import (
	"context"
	"embed"
	"flag"
	"io/fs"
	"net"
	"os"
	"os/signal"
	"platform-installer/internal/sshpassword"
	"strconv"
	"strings"
	"syscall"
)

//go:embed all:frontend/dist
var browserAssets embed.FS

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
	listenAddress := flag.String("browser-listen", "127.0.0.1:8765", "browser HTTP listener address; dev only, restrict access to the browser workstation and localhost")
	publicHost := flag.String("browser-host", "127.0.0.1:8765", "Host:port used by the browser; must match the browser URL exactly")
	allowInsecureDevHTTP := flag.Bool("browser-allow-insecure-dev-http", false, "explicitly allow remote HTTP for development only; credentials and secret uploads are not protected in transit")
	flag.Parse()
	if !*allowInsecureDevHTTP {
		_, _ = os.Stderr.WriteString("BROWSER_REMOTE_HTTP_REQUIRES_DEV_OPT_IN\n")
		return
	}
	if !validBrowserAuthority(*publicHost) || !browserListenerMatchesHost(*listenAddress, *publicHost) {
		_, _ = os.Stderr.WriteString("BROWSER_HOST_CONFIGURATION_INVALID\n")
		return
	}

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
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := runRemoteBrowserHost(ctx, app, webRoot, events, *listenAddress, *publicHost); err != nil {
		_, _ = os.Stderr.WriteString("BROWSER_HOST_FAILED\n")
	}
}

func browserListenerMatchesHost(listenAddress, publicHost string) bool {
	_, listenPort, listenErr := net.SplitHostPort(listenAddress)
	_, publicPort, publicErr := net.SplitHostPort(publicHost)
	return listenErr == nil && publicErr == nil && listenPort != "0" && listenPort == publicPort
}

func validBrowserAuthority(value string) bool {
	host, portText, err := net.SplitHostPort(value)
	if err != nil || host == "" {
		return false
	}
	port, err := strconv.Atoi(portText)
	if err != nil || port <= 0 || port > 65535 {
		return false
	}
	if net.ParseIP(host) != nil {
		return true
	}
	if len(host) > 253 || host == "localhost." {
		return false
	}
	for _, label := range strings.Split(host, ".") {
		if len(label) == 0 || len(label) > 63 || label[0] == '-' || label[len(label)-1] == '-' {
			return false
		}
		for _, r := range label {
			if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-') {
				return false
			}
		}
	}
	return true
}

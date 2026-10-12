//go:build browser && linux

package main

import (
	"embed"
	"platform-installer/internal/desktop"
)

//go:embed all:frontend/dist
var browserAssets embed.FS

func main() {
	desktop.RunBrowserLinux(browserAssets)
}

//go:build browser && !windows && !linux

package main

import "os"

func main() {
	_, _ = os.Stderr.WriteString("BROWSER_HOST_WINDOWS_REQUIRED\n")
}

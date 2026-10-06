//go:build !windows

package commandwindow

import "os/exec"

func Configure(_ *exec.Cmd) {}

package commandwindow

import (
	"os/exec"
	"syscall"
)

const createNoWindow = 0x08000000

// Configure prevents a console window from stealing focus when the Wails app
// launches a short-lived command-line transport process on Windows.
func Configure(command *exec.Cmd) {
	command.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: createNoWindow,
	}
}

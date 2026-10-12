//go:build browser && windows

package desktop

import (
	"errors"
	"os/exec"
	"syscall"
)

func openBrowser(address string) error {
	command := exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", address)
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	if err := command.Start(); err != nil {
		return errors.New("BROWSER_LAUNCH_FAILED")
	}
	_ = command.Process.Release()
	return nil
}

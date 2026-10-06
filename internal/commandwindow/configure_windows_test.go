package commandwindow

import (
	"os/exec"
	"testing"
)

func TestConfigureSuppressesConsoleWindow(t *testing.T) {
	command := exec.Command("ssh", "-V")
	Configure(command)
	if command.SysProcAttr == nil || !command.SysProcAttr.HideWindow || command.SysProcAttr.CreationFlags&createNoWindow == 0 {
		t.Fatal("transport command would open a console window")
	}
}

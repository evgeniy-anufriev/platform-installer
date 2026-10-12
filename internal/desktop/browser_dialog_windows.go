//go:build browser && windows

package desktop

import (
	"context"
	"encoding/base64"
	"errors"
	"os/exec"
	"strings"
	"syscall"
	"unicode/utf16"
	"unicode/utf8"
)

type windowsBrowserDialogProvider struct{}

func newBrowserDialogProvider() DialogProvider { return windowsBrowserDialogProvider{} }

func (windowsBrowserDialogProvider) OpenDirectory(ctx context.Context, options DialogOptions) (string, error) {
	script := "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='" + escapePowerShell(options.Title) + "'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::Out.Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($d.SelectedPath)))}"
	return runNativePicker(ctx, script)
}

func (windowsBrowserDialogProvider) OpenFile(ctx context.Context, options DialogOptions) (string, error) {
	filters := make([]string, 0, len(options.Filters))
	for _, filter := range options.Filters {
		filters = append(filters, escapePowerShell(filter.DisplayName)+"|"+escapePowerShell(filter.Pattern))
	}
	filter := "All files|*.*"
	if len(filters) > 0 {
		filter = strings.Join(filters, "|")
	}
	script := "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='" + escapePowerShell(options.Title) + "'; $d.Filter='" + filter + "'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::Out.Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($d.FileName)))}"
	return runNativePicker(ctx, script)
}

func escapePowerShell(value string) string { return strings.ReplaceAll(value, "'", "''") }

func runNativePicker(ctx context.Context, script string) (string, error) {
	encoded := base64.StdEncoding.EncodeToString(utf16LE(script))
	command := exec.CommandContext(ctx, "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-STA", "-EncodedCommand", encoded)
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	output, err := command.Output()
	if err != nil {
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		return "", errors.New("NATIVE_DIALOG_FAILED")
	}
	decoded, err := base64.StdEncoding.DecodeString(string(output))
	if err != nil || !utf8.Valid(decoded) {
		return "", errors.New("NATIVE_DIALOG_OUTPUT_INVALID")
	}
	return string(decoded), nil
}

func utf16LE(value string) []byte {
	codes := utf16.Encode([]rune(value))
	bytes := make([]byte, len(codes)*2)
	for i, code := range codes {
		bytes[i*2], bytes[i*2+1] = byte(code), byte(code>>8)
	}
	return bytes
}

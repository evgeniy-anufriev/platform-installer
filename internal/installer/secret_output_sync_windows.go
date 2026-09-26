//go:build windows

package installer

import (
	"unsafe"

	"golang.org/x/sys/windows"
)

var secretOutputFlush = windows.NewLazySystemDLL("ntdll.dll").NewProc("NtFlushBuffersFileEx")

// Fail closed if the filesystem cannot durably flush the held directory.
func syncSecretOutputDirectory(directory *exportDirectory) error {
	if err := secretOutputFlush.Find(); err != nil {
		return err
	}
	var status windows.IO_STATUS_BLOCK
	result, _, _ := secretOutputFlush.Call(uintptr(directory.handle), 0, 0, 0, uintptr(unsafe.Pointer(&status)))
	if int32(result) < 0 {
		return windows.NTStatus(result)
	}
	return nil
}

func openSecretOutputDirectory(parent *exportDirectory, parts []string) (*exportDirectory, error) {
	return parent.openDirectoryWithAccess(parts, windows.FILE_GENERIC_READ|windows.FILE_GENERIC_WRITE|windows.DELETE)
}

//go:build windows

package installer

import (
	"os"
	"syscall"
	"unsafe"
)

type replaceFunc func(source, destination string) error

var moveFileEx = syscall.NewLazyDLL("kernel32.dll").NewProc("MoveFileExW")

const moveFileReplaceExisting = 0x1
const moveFileWriteThrough = 0x8

func atomicReplace(source, destination string) error {
	from, err := syscall.UTF16PtrFromString(source)
	if err != nil {
		return err
	}
	to, err := syscall.UTF16PtrFromString(destination)
	if err != nil {
		return err
	}
	result, _, callErr := moveFileEx.Call(uintptr(unsafe.Pointer(from)), uintptr(unsafe.Pointer(to)),
		moveFileReplaceExisting|moveFileWriteThrough)
	if result == 0 {
		if callErr != nil && callErr != syscall.Errno(0) {
			return callErr
		}
		return os.ErrInvalid
	}
	return nil
}

func syncDirectory(path string) error { return nil }

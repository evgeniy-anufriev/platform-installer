//go:build windows

package projectlifecycle

import (
	"errors"
	"syscall"
	"unsafe"
)

var moveFileEx = syscall.NewLazyDLL("kernel32.dll").NewProc("MoveFileExW")

const moveFileWriteThrough = 0x8

func atomicPublish(source, destination string) error {
	from, err := syscall.UTF16PtrFromString(source)
	if err != nil {
		return err
	}
	to, err := syscall.UTF16PtrFromString(destination)
	if err != nil {
		return err
	}
	result, _, callErr := moveFileEx.Call(uintptr(unsafe.Pointer(from)), uintptr(unsafe.Pointer(to)), moveFileWriteThrough)
	if result == 0 {
		if callErr != syscall.Errno(0) {
			return callErr
		}
		return errors.New("PROJECT_PUBLISH_FAILED")
	}
	return nil
}

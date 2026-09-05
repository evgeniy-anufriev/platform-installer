package executionnode

import (
	"os"
	"syscall"
	"unsafe"
)

const (
	lockfileFailImmediately = 0x00000001
	lockfileExclusiveLock   = 0x00000002
)

var (
	kernel32LockFileEx   = syscall.NewLazyDLL("kernel32.dll").NewProc("LockFileEx")
	kernel32UnlockFileEx = syscall.NewLazyDLL("kernel32.dll").NewProc("UnlockFileEx")
)

func lockEventMirror(file *os.File) (func() error, error) {
	overlapped := &syscall.Overlapped{}
	result, _, callErr := kernel32LockFileEx.Call(file.Fd(), lockfileExclusiveLock|lockfileFailImmediately, 0, 0xffffffff, 0xffffffff, uintptr(unsafe.Pointer(overlapped)))
	if result == 0 {
		return nil, callErr
	}
	return func() error {
		result, _, callErr := kernel32UnlockFileEx.Call(file.Fd(), 0, 0xffffffff, 0xffffffff, uintptr(unsafe.Pointer(overlapped)))
		if result == 0 {
			return callErr
		}
		return nil
	}, nil
}

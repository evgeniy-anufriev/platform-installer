//go:build aix || darwin || dragonfly || freebsd || linux || netbsd || openbsd || solaris

package executionnode

import (
	"os"
	"syscall"
)

func lockEventMirror(file *os.File) (func() error, error) {
	if err := syscall.Flock(int(file.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return nil, err
	}
	return func() error { return syscall.Flock(int(file.Fd()), syscall.LOCK_UN) }, nil
}

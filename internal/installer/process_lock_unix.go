//go:build !windows

package installer

import (
	"errors"
	"os"

	"golang.org/x/sys/unix"
)

func tryProcessFileLock(file *os.File) (func() error, bool, error) {
	err := unix.Flock(int(file.Fd()), unix.LOCK_EX|unix.LOCK_NB)
	if errors.Is(err, unix.EWOULDBLOCK) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return func() error { return unix.Flock(int(file.Fd()), unix.LOCK_UN) }, true, nil
}

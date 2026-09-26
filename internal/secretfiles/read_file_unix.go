//go:build !windows

package secretfiles

import (
	"os"

	"golang.org/x/sys/unix"
)

func openSelectedFile(path string) (*os.File, error) {
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC|unix.O_NONBLOCK, 0)
	if err != nil {
		return nil, err
	}
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil || stat.Mode&unix.S_IFMT != unix.S_IFREG {
		_ = unix.Close(fd)
		return nil, ErrSelectedFile
	}
	file := os.NewFile(uintptr(fd), "selected-secret")
	if file == nil {
		_ = unix.Close(fd)
		return nil, ErrSelectedFile
	}
	return file, nil
}

//go:build !windows

package runtimesecret

import (
	"os"
	"syscall"
)

func openPrivateKey(path string) (*os.File, error) {
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(fd), "private-key"), nil
}

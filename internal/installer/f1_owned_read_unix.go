//go:build !windows

package installer

import (
	"errors"
	"io"
	"os"

	"golang.org/x/sys/unix"
)

func readF1OwnedFile(root string, parts []string, limit int64) ([]byte, error) {
	rootFD, err := unix.Open(root, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	defer unix.Close(rootFD)
	directory := rootFD
	for _, part := range parts[:len(parts)-1] {
		child, openErr := unix.Openat(directory, part, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if openErr != nil {
			if directory != rootFD {
				_ = unix.Close(directory)
			}
			if errors.Is(openErr, unix.ENOENT) {
				return nil, os.ErrNotExist
			}
			return nil, openErr
		}
		if directory != rootFD {
			_ = unix.Close(directory)
		}
		directory = child
	}
	if directory != rootFD {
		defer unix.Close(directory)
	}
	fd, err := unix.Openat(directory, parts[len(parts)-1], unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		if errors.Is(err, unix.ENOENT) {
			return nil, os.ErrNotExist
		}
		return nil, err
	}
	file := os.NewFile(uintptr(fd), parts[len(parts)-1])
	if file == nil {
		_ = unix.Close(fd)
		return nil, errors.New("managed file open failed")
	}
	defer file.Close()
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil || stat.Mode&unix.S_IFMT != unix.S_IFREG || stat.Size > limit {
		return nil, errors.New("managed file is unsafe")
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil || int64(len(data)) != stat.Size {
		return nil, errors.New("managed file read failed")
	}
	return data, nil
}

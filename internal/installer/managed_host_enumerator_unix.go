//go:build !windows

package installer

import (
	"errors"
	"os"

	"golang.org/x/sys/unix"
)

func enumerateManagedHostDirectories(root string, limit int) ([]string, error) {
	rootFD, err := unix.Open(root, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	defer unix.Close(rootFD)
	inventoryFD, err := unix.Openat(rootFD, "inventory", unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		if errors.Is(err, unix.ENOENT) {
			return []string{}, nil
		}
		return nil, err
	}
	defer unix.Close(inventoryFD)
	hostVarsFD, err := unix.Openat(inventoryFD, "host_vars", unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		if errors.Is(err, unix.ENOENT) {
			return []string{}, nil
		}
		return nil, err
	}
	file := os.NewFile(uintptr(hostVarsFD), "host_vars")
	if file == nil {
		return nil, errors.New("managed host directory open failed")
	}
	// file owns hostVarsFD from this point.
	hostVarsFD = -1
	defer file.Close()
	entries, err := file.ReadDir(limit + 1)
	if err != nil {
		return nil, err
	}
	if len(entries) > limit {
		return nil, errors.New("managed host directory limit exceeded")
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		child, openErr := unix.Openat(int(file.Fd()), entry.Name(), unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if openErr != nil {
			return nil, openErr
		}
		_ = unix.Close(child)
		names = append(names, entry.Name())
	}
	return names, nil
}

//go:build !windows

package executionbundle

import (
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/sys/unix"
)

func verifiedRootIdentity(root string) (string, error) {
	var stat unix.Stat_t
	if err := unix.Stat(root, &stat); err != nil {
		return "", err
	}
	if stat.Mode&unix.S_IFMT != unix.S_IFDIR {
		return "", errors.New("not a directory")
	}
	return fmt.Sprintf("%d:%d", stat.Dev, stat.Ino), nil
}

func readVerifiedComponent(verified Verified, component Component, limit int64) ([]byte, error) {
	rootFD, err := unix.Open(verified.Root, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer unix.Close(rootFD)
	if !sameUnixIdentity(rootFD, verified.rootIdentity, true) {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	parts := strings.Split(component.Path, "/")
	directoryFD := rootFD
	for _, part := range parts[:len(parts)-1] {
		child, openErr := unix.Openat(directoryFD, part, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if openErr != nil {
			if directoryFD != rootFD {
				_ = unix.Close(directoryFD)
			}
			return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
		if directoryFD != rootFD {
			_ = unix.Close(directoryFD)
		}
		directoryFD = child
		if !sameUnixIdentity(directoryFD, "", true) {
			_ = unix.Close(directoryFD)
			return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
	}
	if directoryFD != rootFD {
		defer unix.Close(directoryFD)
	}
	fileFD, err := unix.Openat(directoryFD, parts[len(parts)-1], unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	file := os.NewFile(uintptr(fileFD), component.Path)
	if file == nil {
		_ = unix.Close(fileFD)
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer file.Close()
	var stat unix.Stat_t
	if err := unix.Fstat(fileFD, &stat); err != nil || stat.Mode&unix.S_IFMT != unix.S_IFREG || stat.Size != component.Size || stat.Size > limit {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	content, err := io.ReadAll(io.LimitReader(file, component.Size+1))
	if err != nil || int64(len(content)) != component.Size {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_CHECKSUM_MISMATCH")
	}
	return content, nil
}

func readBundleManifest(root string) ([]byte, error) {
	rootFD, err := unix.Open(root, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer unix.Close(rootFD)
	fileFD, err := unix.Openat(rootFD, "manifest.yaml", unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	file := os.NewFile(uintptr(fileFD), "manifest.yaml")
	if file == nil {
		_ = unix.Close(fileFD)
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer file.Close()
	var stat unix.Stat_t
	if err := unix.Fstat(fileFD, &stat); err != nil || stat.Mode&unix.S_IFMT != unix.S_IFREG || stat.Size > 1024*1024 {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	data, err := io.ReadAll(io.LimitReader(file, 1024*1024+1))
	if err != nil || int64(len(data)) != stat.Size {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	return data, nil
}

func sameUnixIdentity(fd int, expected string, directory bool) bool {
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		return false
	}
	if directory && stat.Mode&unix.S_IFMT != unix.S_IFDIR {
		return false
	}
	identity := fmt.Sprintf("%d:%d", stat.Dev, stat.Ino)
	return expected == "" || identity == expected
}

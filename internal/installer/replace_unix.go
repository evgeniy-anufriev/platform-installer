//go:build !windows

package installer

import "os"

type replaceFunc func(source, destination string) error

func atomicReplace(source, destination string) error { return os.Rename(source, destination) }

func syncDirectory(path string) error {
	directory, err := os.Open(path)
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}

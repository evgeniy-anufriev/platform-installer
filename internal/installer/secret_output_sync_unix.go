//go:build linux

package installer

import "golang.org/x/sys/unix"

// Sync the held directory, not a pathname that can be replaced.
func syncSecretOutputDirectory(directory *exportDirectory) error {
	return unix.Fsync(directory.fd)
}

func openSecretOutputDirectory(parent *exportDirectory, parts []string) (*exportDirectory, error) {
	return parent.openDirectory(parts)
}

//go:build !windows

package installer

import (
	"os"
	"strconv"
	"syscall"
)

func hardenWriterFile(file *os.File, mode os.FileMode) error {
	return file.Chmod(mode)
}

func createWriterFile(path string, mode os.FileMode) (*os.File, error) {
	return os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
}

func openWriterLockFile(path string) (*os.File, error) {
	return os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
}

func openWriterSecurityHandle(path string) (*os.File, error) { return os.Open(path) }

func writerFileIdentity(file *os.File) (string, error) {
	info, err := file.Stat()
	if err != nil {
		return "", err
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return "", os.ErrInvalid
	}
	return strconv.FormatUint(uint64(stat.Dev), 16) + ":" + strconv.FormatUint(uint64(stat.Ino), 16), nil
}

func finalizeCanonicalACL(_ string, _ bool) error { return nil }

func finalizeCanonicalDirectory(path string, mode os.FileMode) error { return os.Chmod(path, mode) }

func captureCanonicalSecurity(_ string) (string, error) { return "", nil }

func validCanonicalSecurity(value string) bool { return value == "" }

func applyCanonicalSecurity(_ string, _ *os.File) error { return nil }

func canonicalSecurityMatches(_ string, expected string) (bool, error) { return expected == "", nil }

//go:build aix || darwin || dragonfly || freebsd || linux || netbsd || openbsd || solaris

package executionnode

import "os"

func isUnsafeFilesystemLink(info os.FileInfo) bool {
	return info == nil || info.Mode()&os.ModeSymlink != 0
}

func mirrorDirectoryPrivate(info os.FileInfo) bool {
	return info != nil && info.Mode().Perm()&0o077 == 0
}

func hardenMirrorHandle(file *os.File) error {
	info, err := file.Stat()
	if err != nil {
		return err
	}
	if info.IsDir() {
		return file.Chmod(0o700)
	}
	return file.Chmod(0o600)
}

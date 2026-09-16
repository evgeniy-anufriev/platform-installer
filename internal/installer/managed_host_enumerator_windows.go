//go:build windows

package installer

import (
	"errors"
	"os"
	"path/filepath"

	"golang.org/x/sys/windows"
)

func enumerateManagedHostDirectories(root string, limit int) ([]string, error) {
	pointer, err := windows.UTF16PtrFromString(root)
	if err != nil {
		return nil, err
	}
	rootHandle, err := windows.CreateFile(pointer, windows.FILE_GENERIC_READ, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if err != nil {
		return nil, err
	}
	defer windows.CloseHandle(rootHandle)
	if err := verifyF1WindowsHandle(rootHandle, true); err != nil {
		return nil, err
	}
	inventory, err := openF1WindowsRelative(rootHandle, "inventory", true)
	if err != nil {
		if errors.Is(err, windows.ERROR_FILE_NOT_FOUND) || errors.Is(err, windows.ERROR_PATH_NOT_FOUND) || managedDirectoryAbsent(root, "inventory") {
			return []string{}, nil
		}
		return nil, err
	}
	defer windows.CloseHandle(inventory)
	hostVars, err := openF1WindowsRelative(inventory, "host_vars", true)
	if err != nil {
		if errors.Is(err, windows.ERROR_FILE_NOT_FOUND) || errors.Is(err, windows.ERROR_PATH_NOT_FOUND) || managedDirectoryAbsent(root, "inventory", "host_vars") {
			return []string{}, nil
		}
		return nil, err
	}
	file := os.NewFile(uintptr(hostVars), "host_vars")
	if file == nil {
		_ = windows.CloseHandle(hostVars)
		return nil, errors.New("managed host directory open failed")
	}
	// file owns hostVars from this point.
	hostVars = 0
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
		child, openErr := openF1WindowsRelative(windows.Handle(file.Fd()), entry.Name(), true)
		if openErr != nil {
			return nil, openErr
		}
		_ = windows.CloseHandle(child)
		names = append(names, entry.Name())
	}
	return names, nil
}

// A pathname check is used only to classify an already-failed handle-relative
// open as absence. It never authorizes a subsequent read from that pathname.
func managedDirectoryAbsent(root string, parts ...string) bool {
	_, err := os.Lstat(filepath.Join(append([]string{root}, parts...)...))
	return errors.Is(err, os.ErrNotExist)
}

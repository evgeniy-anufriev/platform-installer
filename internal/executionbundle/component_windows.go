//go:build windows

package executionbundle

import (
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"unsafe"

	"golang.org/x/sys/windows"
)

func verifiedRootIdentity(root string) (string, error) {
	handle, err := openWindowsRoot(root)
	if err != nil {
		return "", err
	}
	defer windows.CloseHandle(handle)
	return windowsIdentity(handle, true)
}

func readVerifiedComponent(verified Verified, component Component, limit int64) ([]byte, error) {
	root, err := openWindowsRoot(verified.Root)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer windows.CloseHandle(root)
	identity, err := windowsIdentity(root, true)
	if err != nil || identity != verified.rootIdentity {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	parts := strings.Split(component.Path, "/")
	directory := root
	for _, part := range parts[:len(parts)-1] {
		child, openErr := openWindowsRelative(directory, part, true)
		if openErr != nil {
			if directory != root {
				_ = windows.CloseHandle(directory)
			}
			return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
		if directory != root {
			_ = windows.CloseHandle(directory)
		}
		directory = child
	}
	if directory != root {
		defer windows.CloseHandle(directory)
	}
	handle, err := openWindowsRelative(directory, parts[len(parts)-1], false)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	file := os.NewFile(uintptr(handle), component.Path)
	if file == nil {
		_ = windows.CloseHandle(handle)
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer file.Close()
	if _, err := windowsIdentity(handle, false); err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() != component.Size || info.Size() > limit {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	content, err := io.ReadAll(io.LimitReader(file, component.Size+1))
	if err != nil || int64(len(content)) != component.Size {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_CHECKSUM_MISMATCH")
	}
	return content, nil
}

func readBundleManifest(root string) ([]byte, error) {
	directory, err := openWindowsRoot(root)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer windows.CloseHandle(directory)
	handle, err := openWindowsRelative(directory, "manifest.yaml", false)
	if err != nil {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	file := os.NewFile(uintptr(handle), "manifest.yaml")
	if file == nil {
		_ = windows.CloseHandle(handle)
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() > 1024*1024 {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	data, err := io.ReadAll(io.LimitReader(file, 1024*1024+1))
	if err != nil || int64(len(data)) != info.Size() {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
	}
	return data, nil
}

func openWindowsRoot(path string) (windows.Handle, error) {
	pointer, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return 0, err
	}
	return windows.CreateFile(pointer, windows.FILE_GENERIC_READ, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS|windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
}

func openWindowsRelative(root windows.Handle, name string, directory bool) (windows.Handle, error) {
	objectName, err := windows.NewNTUnicodeString(name)
	if err != nil {
		return 0, err
	}
	attributes := uint32(windows.FILE_SYNCHRONOUS_IO_NONALERT | windows.FILE_OPEN_REPARSE_POINT)
	if directory {
		attributes |= windows.FILE_DIRECTORY_FILE
	} else {
		attributes |= windows.FILE_NON_DIRECTORY_FILE
	}
	object := windows.OBJECT_ATTRIBUTES{Length: uint32(unsafe.Sizeof(windows.OBJECT_ATTRIBUTES{})), RootDirectory: root, ObjectName: objectName, Attributes: windows.OBJ_CASE_INSENSITIVE | windows.OBJ_DONT_REPARSE}
	var handle windows.Handle
	var status windows.IO_STATUS_BLOCK
	if err := windows.NtCreateFile(&handle, windows.FILE_GENERIC_READ, &object, &status, nil, 0, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, windows.FILE_OPEN, attributes, 0, 0); err != nil {
		return 0, err
	}
	if _, err := windowsIdentity(handle, directory); err != nil {
		_ = windows.CloseHandle(handle)
		return 0, err
	}
	return handle, nil
}

func windowsIdentity(handle windows.Handle, directory bool) (string, error) {
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil {
		return "", err
	}
	if info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || (info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0) != directory {
		return "", errors.New("unsafe file object")
	}
	return fmt.Sprintf("%d:%d:%d", info.VolumeSerialNumber, info.FileIndexHigh, info.FileIndexLow), nil
}

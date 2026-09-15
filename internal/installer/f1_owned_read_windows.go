//go:build windows

package installer

import (
	"errors"
	"io"
	"os"
	"unsafe"

	"golang.org/x/sys/windows"
)

func readF1OwnedFile(root string, parts []string, limit int64) ([]byte, error) {
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
	directory := rootHandle
	for _, part := range parts[:len(parts)-1] {
		child, openErr := openF1WindowsRelative(directory, part, true)
		if openErr != nil {
			if openErr == windows.ERROR_FILE_NOT_FOUND || openErr == windows.ERROR_PATH_NOT_FOUND || errors.Is(openErr, windows.ERROR_FILE_NOT_FOUND) || errors.Is(openErr, windows.ERROR_PATH_NOT_FOUND) {
				return nil, os.ErrNotExist
			}
			return nil, openErr
		}
		if directory != rootHandle {
			_ = windows.CloseHandle(directory)
		}
		directory = child
	}
	if directory != rootHandle {
		defer windows.CloseHandle(directory)
	}
	handle, err := openF1WindowsRelative(directory, parts[len(parts)-1], false)
	if err != nil {
		if err == windows.ERROR_FILE_NOT_FOUND || err == windows.ERROR_PATH_NOT_FOUND || errors.Is(err, windows.ERROR_FILE_NOT_FOUND) || errors.Is(err, windows.ERROR_PATH_NOT_FOUND) {
			return nil, os.ErrNotExist
		}
		return nil, err
	}
	file := os.NewFile(uintptr(handle), parts[len(parts)-1])
	if file == nil {
		_ = windows.CloseHandle(handle)
		return nil, errors.New("managed file open failed")
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() > limit {
		return nil, errors.New("managed file is unsafe")
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil || int64(len(data)) != info.Size() {
		return nil, errors.New("managed file read failed")
	}
	return data, nil
}

func openF1WindowsRelative(root windows.Handle, name string, directory bool) (windows.Handle, error) {
	nameValue, err := windows.NewNTUnicodeString(name)
	if err != nil {
		return 0, err
	}
	options := uint32(windows.FILE_SYNCHRONOUS_IO_NONALERT | windows.FILE_OPEN_REPARSE_POINT)
	if directory {
		options |= windows.FILE_DIRECTORY_FILE
	} else {
		options |= windows.FILE_NON_DIRECTORY_FILE
	}
	object := windows.OBJECT_ATTRIBUTES{Length: uint32(unsafe.Sizeof(windows.OBJECT_ATTRIBUTES{})), RootDirectory: root, ObjectName: nameValue, Attributes: windows.OBJ_CASE_INSENSITIVE | windows.OBJ_DONT_REPARSE}
	var handle windows.Handle
	var status windows.IO_STATUS_BLOCK
	if err := windows.NtCreateFile(&handle, windows.FILE_GENERIC_READ, &object, &status, nil, 0, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, windows.FILE_OPEN, options, 0, 0); err != nil {
		return 0, err
	}
	if err := verifyF1WindowsHandle(handle, directory); err != nil {
		_ = windows.CloseHandle(handle)
		return 0, err
	}
	return handle, nil
}

func verifyF1WindowsHandle(handle windows.Handle, directory bool) error {
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil {
		return err
	}
	if info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || (info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0) != directory {
		return errors.New("managed file is unsafe")
	}
	return nil
}

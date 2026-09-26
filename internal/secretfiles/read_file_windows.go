//go:build windows

package secretfiles

import (
	"os"

	"golang.org/x/sys/windows"
)

func openSelectedFile(path string) (*os.File, error) {
	pointer, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return nil, ErrSelectedFile
	}
	handle, err := windows.CreateFile(pointer, windows.GENERIC_READ, windows.FILE_SHARE_READ, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if err != nil {
		return nil, err
	}
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0 {
		_ = windows.CloseHandle(handle)
		return nil, ErrSelectedFile
	}
	file := os.NewFile(uintptr(handle), "selected-secret")
	if file == nil {
		_ = windows.CloseHandle(handle)
		return nil, ErrSelectedFile
	}
	return file, nil
}

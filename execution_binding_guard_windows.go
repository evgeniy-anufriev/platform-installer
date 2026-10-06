//go:build windows

package main

import (
	"crypto/sha256"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

var bindingConvertSD = syscall.NewLazyDLL("advapi32.dll").NewProc("ConvertStringSecurityDescriptorToSecurityDescriptorW")
var bindingSetFileSecurity = syscall.NewLazyDLL("advapi32.dll").NewProc("SetFileSecurityW")

const bindingProtectedDACL = 0x80000004

func hardenBindingPath(file *os.File) error {
	token, err := syscall.OpenCurrentProcessToken()
	if err != nil {
		return err
	}
	defer token.Close()
	user, err := token.GetTokenUser()
	if err != nil {
		return err
	}
	sid, err := user.User.Sid.String()
	if err != nil {
		return err
	}
	sddl, err := syscall.UTF16PtrFromString("D:P(A;;FA;;;" + sid + ")(A;;FA;;;SY)(A;;FA;;;BA)")
	if err != nil {
		return err
	}
	var descriptor uintptr
	var size uint32
	result, _, callErr := bindingConvertSD.Call(uintptr(unsafe.Pointer(sddl)), 1, uintptr(unsafe.Pointer(&descriptor)), uintptr(unsafe.Pointer(&size)))
	if result == 0 || descriptor == 0 {
		return callErr
	}
	defer syscall.LocalFree(syscall.Handle(descriptor))
	path, err := syscall.UTF16PtrFromString(file.Name())
	if err != nil {
		return err
	}
	result, _, callErr = bindingSetFileSecurity.Call(uintptr(unsafe.Pointer(path)), bindingProtectedDACL, descriptor)
	if result == 0 {
		return callErr
	}
	opened, err := file.Stat()
	if err != nil {
		return err
	}
	linked, err := os.Lstat(file.Name())
	if err != nil || !os.SameFile(opened, linked) || linked.Mode()&os.ModeSymlink != 0 {
		return errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	return nil
}

// holdVerifiedBindingFile locks every pathname component against rename and
// the exact opened file against write/delete for the lifetime of ssh/scp.
// This narrow guard is only for the V02 Windows UI transport.
func holdVerifiedBindingFile(path string, identity os.FileInfo, digest [sha256.Size]byte, maxBytes int64) (func(), error) {
	if !filepath.IsAbs(path) || identity == nil {
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	clean := filepath.Clean(path)
	volume := filepath.VolumeName(clean)
	if volume == "" {
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	current := volume + string(filepath.Separator)
	relative := strings.TrimPrefix(clean, current)
	if relative == clean || relative == "" {
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	var held []*os.File
	closeHeld := func() {
		for i := len(held) - 1; i >= 0; i-- {
			_ = held[i].Close()
		}
	}
	parts := strings.Split(relative, string(filepath.Separator))
	for i := 0; i < len(parts); i++ {
		if i != 0 {
			current = filepath.Join(current, parts[i-1])
		}
		directory, err := openBindingComponent(current, true)
		if err != nil {
			closeHeld()
			return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
		}
		held = append(held, directory)
	}
	file, err := openBindingComponent(clean, false)
	if err != nil {
		closeHeld()
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	held = append(held, file)
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || !os.SameFile(info, identity) || info.Size() < 1 || info.Size() > maxBytes {
		closeHeld()
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	bytes, err := io.ReadAll(io.LimitReader(file, maxBytes+1))
	if err != nil || int64(len(bytes)) != info.Size() || sha256.Sum256(bytes) != digest {
		closeHeld()
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	return closeHeld, nil
}

func openBindingComponent(path string, directory bool) (*os.File, error) {
	pointer, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return nil, err
	}
	access := uint32(windows.GENERIC_READ)
	flags := uint32(windows.FILE_FLAG_OPEN_REPARSE_POINT)
	share := uint32(windows.FILE_SHARE_READ)
	if directory {
		access = windows.FILE_READ_ATTRIBUTES
		flags |= windows.FILE_FLAG_BACKUP_SEMANTICS
		share |= windows.FILE_SHARE_WRITE
	}
	handle, err := windows.CreateFile(pointer, access, share, nil, windows.OPEN_EXISTING, flags, 0)
	if err != nil {
		return nil, err
	}
	var info windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(handle, &info) != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || (info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0) != directory {
		_ = windows.CloseHandle(handle)
		return nil, errors.New("EXECUTION_NODE_BINDING_INVALID")
	}
	return os.NewFile(uintptr(handle), "binding-component"), nil
}

// Delete by the opened object, never by a pathname observed earlier. If a
// lease or an unrelated process still holds either object, retain it safely.
func removeSessionKnownHosts(filePath string, fileInfo os.FileInfo, directory string, directoryInfo os.FileInfo) {
	if fileInfo == nil || directoryInfo == nil || filepath.Dir(filePath) != directory {
		return
	}
	if !markBindingObjectDeleted(filePath, fileInfo, false) {
		return
	}
	_ = markBindingObjectDeleted(directory, directoryInfo, true)
}

func removeSessionDirectory(path string, info os.FileInfo) {
	if info != nil {
		_ = markBindingObjectDeleted(path, info, true)
	}
}

func markBindingObjectDeleted(path string, original os.FileInfo, directory bool) bool {
	pointer, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return false
	}
	flags := uint32(windows.FILE_FLAG_OPEN_REPARSE_POINT)
	if directory {
		flags |= windows.FILE_FLAG_BACKUP_SEMANTICS
	}
	handle, err := windows.CreateFile(pointer, windows.DELETE|windows.FILE_READ_ATTRIBUTES, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, nil, windows.OPEN_EXISTING, flags, 0)
	if err != nil {
		return false
	}
	file := os.NewFile(uintptr(handle), "session-host-key-cleanup")
	if file == nil {
		_ = windows.CloseHandle(handle)
		return false
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !os.SameFile(info, original) || info.IsDir() != directory {
		return false
	}
	var attributes windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(handle, &attributes) != nil || attributes.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 {
		return false
	}
	deleteFlag := []byte{1}
	return windows.SetFileInformationByHandle(handle, windows.FileDispositionInfo, &deleteFlag[0], uint32(len(deleteFlag))) == nil
}

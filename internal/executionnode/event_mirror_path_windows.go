package executionnode

import (
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

var (
	convertStringSecurityDescriptor = syscall.NewLazyDLL("advapi32.dll").NewProc("ConvertStringSecurityDescriptorToSecurityDescriptorW")
	setFileSecurity                 = syscall.NewLazyDLL("advapi32.dll").NewProc("SetFileSecurityW")
)

const protectedDACLInformation = 0x80000004

func isUnsafeFilesystemLink(info os.FileInfo) bool {
	if info == nil || info.Mode()&os.ModeSymlink != 0 {
		return true
	}
	data, ok := info.Sys().(*syscall.Win32FileAttributeData)
	return !ok || data.FileAttributes&syscall.FILE_ATTRIBUTE_REPARSE_POINT != 0
}

func mirrorDirectoryPrivate(info os.FileInfo) bool {
	return info != nil
}

func hardenMirrorHandle(file *os.File) error {
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
	result, _, callErr := convertStringSecurityDescriptor.Call(uintptr(unsafe.Pointer(sddl)), 1, uintptr(unsafe.Pointer(&descriptor)), uintptr(unsafe.Pointer(&size)))
	if result == 0 {
		return callErr
	}
	if descriptor == 0 {
		return errors.New("EXECUTION_MIRROR_DACL_INVALID")
	}
	defer syscall.LocalFree(syscall.Handle(descriptor))
	path, err := syscall.UTF16PtrFromString(filepath.Clean(file.Name()))
	if err != nil {
		return err
	}
	result, _, callErr = setFileSecurity.Call(uintptr(unsafe.Pointer(path)), protectedDACLInformation, descriptor)
	if result == 0 {
		return callErr
	}
	opened, openErr := file.Stat()
	linked, linkErr := os.Lstat(file.Name())
	if openErr != nil || linkErr != nil || isUnsafeFilesystemLink(linked) || !os.SameFile(opened, linked) {
		return errors.New("EXECUTION_MIRROR_DACL_TARGET_CHANGED")
	}
	return nil
}

//go:build windows

package installer

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

const maxCanonicalSecurityDescriptorBytes = 64 * 1024

var writerConvertSecurityDescriptor = syscall.NewLazyDLL("advapi32.dll").NewProc("ConvertStringSecurityDescriptorToSecurityDescriptorW")
var writerSetKernelObjectSecurity = syscall.NewLazyDLL("advapi32.dll").NewProc("SetKernelObjectSecurity")
var writerGetKernelObjectSecurity = syscall.NewLazyDLL("advapi32.dll").NewProc("GetKernelObjectSecurity")
var writerGetSecurityDescriptorControl = syscall.NewLazyDLL("advapi32.dll").NewProc("GetSecurityDescriptorControl")
var writerCreatePrivateObjectSecurityEx = syscall.NewLazyDLL("advapi32.dll").NewProc("CreatePrivateObjectSecurityEx")
var writerDestroyPrivateObjectSecurity = syscall.NewLazyDLL("advapi32.dll").NewProc("DestroyPrivateObjectSecurity")

const (
	writerDACLInformation            = 0x00000004
	writerProtectedDACLInformation   = 0x80000000
	writerUnprotectedDACLInformation = 0x20000000
	writerDACLProtectedControl       = 0x1000
	writerSEFDACLAutoInherit         = 0x00000001
	writerReadControl                = 0x00020000
	writerWriteDACL                  = 0x00040000
	writerGenericRead                = 0x80000000
	writerGenericWrite               = 0x40000000
	writerFileReadAttributes         = 0x00000080
	writerShareRead                  = 0x00000001
	writerShareWrite                 = 0x00000002
	writerShareDelete                = 0x00000004
	writerOpenExisting               = 3
	writerOpenAlways                 = 4
	writerCreateNew                  = 1
	writerOpenReparsePoint           = 0x00200000
	writerBackupSemantics            = 0x02000000
	writerFileAttributeNormal        = 0x00000080
)

type writerGenericMapping struct {
	GenericRead    uint32
	GenericWrite   uint32
	GenericExecute uint32
	GenericAll     uint32
}

func captureCanonicalSecurity(path string) (string, error) {
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	descriptor, _, err := readWriterDACL(file)
	if err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(descriptor), nil
}

func validCanonicalSecurity(value string) bool {
	descriptor, err := base64.StdEncoding.DecodeString(value)
	return err == nil && len(descriptor) > 0 && len(descriptor) <= maxCanonicalSecurityDescriptorBytes
}

func applyCanonicalSecurity(value string, destination *os.File) error {
	descriptor, err := base64.StdEncoding.DecodeString(value)
	if err != nil || len(descriptor) == 0 || len(descriptor) > maxCanonicalSecurityDescriptorBytes {
		return errors.New("WRITER_CANONICAL_DACL_INVALID")
	}
	var control uint16
	var revision uint32
	result, _, callErr := writerGetSecurityDescriptorControl.Call(uintptr(unsafe.Pointer(&descriptor[0])), uintptr(unsafe.Pointer(&control)), uintptr(unsafe.Pointer(&revision)))
	if result == 0 {
		return callErr
	}
	information := uintptr(writerDACLInformation | writerUnprotectedDACLInformation)
	if control&writerDACLProtectedControl != 0 {
		information = writerDACLInformation | writerProtectedDACLInformation
	}
	result, _, callErr = writerSetKernelObjectSecurity.Call(destination.Fd(), information, uintptr(unsafe.Pointer(&descriptor[0])))
	if result == 0 {
		return callErr
	}
	return nil
}

func canonicalSecurityMatches(path, expected string) (bool, error) {
	actual, err := captureCanonicalSecurity(path)
	if err != nil {
		return false, err
	}
	actualBytes, actualErr := base64.StdEncoding.DecodeString(actual)
	expectedBytes, expectedErr := base64.StdEncoding.DecodeString(expected)
	if actualErr != nil || expectedErr != nil {
		return false, errors.New("WRITER_CANONICAL_DACL_INVALID")
	}
	// Windows may normalize inheritance bookkeeping flags when the same DACL is
	// applied to a replacement file. The protected/unprotected boundary and the
	// ACL bytes are authoritative; AUTO_INHERITED is not a semantic DACL change.
	if len(actualBytes) >= 4 && len(expectedBytes) >= 4 {
		actualControl := binary.LittleEndian.Uint16(actualBytes[2:4]) & writerDACLProtectedControl
		expectedControl := binary.LittleEndian.Uint16(expectedBytes[2:4]) & writerDACLProtectedControl
		binary.LittleEndian.PutUint16(actualBytes[2:4], actualControl)
		binary.LittleEndian.PutUint16(expectedBytes[2:4], expectedControl)
	}
	return bytes.Equal(actualBytes, expectedBytes), nil
}

func readWriterDACL(file *os.File) ([]byte, uint16, error) {
	var needed uint32
	result, _, callErr := writerGetKernelObjectSecurity.Call(file.Fd(), writerDACLInformation, 0, 0, uintptr(unsafe.Pointer(&needed)))
	if result == 0 && needed == 0 {
		return nil, 0, callErr
	}
	descriptor := make([]byte, needed)
	result, _, callErr = writerGetKernelObjectSecurity.Call(file.Fd(), writerDACLInformation, uintptr(unsafe.Pointer(&descriptor[0])), uintptr(needed), uintptr(unsafe.Pointer(&needed)))
	if result == 0 {
		return nil, 0, callErr
	}
	var control uint16
	var revision uint32
	result, _, callErr = writerGetSecurityDescriptorControl.Call(uintptr(unsafe.Pointer(&descriptor[0])), uintptr(unsafe.Pointer(&control)), uintptr(unsafe.Pointer(&revision)))
	if result == 0 {
		return nil, 0, callErr
	}
	return descriptor, control, nil
}

func finalizeCanonicalACL(path string, existed bool) error {
	if existed {
		return nil
	}
	return applyInheritedCanonicalACL(path, false)
}

func applyInheritedCanonicalACL(path string, directory bool) error {
	parent, err := openWriterSecurityHandle(filepath.Dir(path))
	if err != nil {
		return err
	}
	defer parent.Close()
	descriptor, _, err := readWriterDACL(parent)
	if err != nil {
		return err
	}
	var inherited uintptr
	mapping := writerGenericMapping{GenericRead: 0x00120089, GenericWrite: 0x00120116, GenericExecute: 0x001200a0, GenericAll: 0x001f01ff}
	token, err := syscall.OpenCurrentProcessToken()
	if err != nil {
		return err
	}
	defer token.Close()
	isDirectory := uintptr(0)
	if directory {
		isDirectory = 1
	}
	result, _, callErr := writerCreatePrivateObjectSecurityEx.Call(
		uintptr(unsafe.Pointer(&descriptor[0])), 0, uintptr(unsafe.Pointer(&inherited)), 0,
		isDirectory, writerSEFDACLAutoInherit, uintptr(token), uintptr(unsafe.Pointer(&mapping)),
	)
	if result == 0 {
		return callErr
	}
	defer writerDestroyPrivateObjectSecurity.Call(uintptr(unsafe.Pointer(&inherited)))
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		return err
	}
	defer file.Close()
	result, _, callErr = writerSetKernelObjectSecurity.Call(file.Fd(), writerDACLInformation|writerUnprotectedDACLInformation, inherited)
	if result == 0 {
		return callErr
	}
	return nil
}

func finalizeCanonicalDirectory(path string, _ os.FileMode) error {
	return applyInheritedCanonicalACL(path, true)
}

func hardenWriterFile(file *os.File, _ os.FileMode) error {
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
	result, _, callErr := writerConvertSecurityDescriptor.Call(
		uintptr(unsafe.Pointer(sddl)), 1, uintptr(unsafe.Pointer(&descriptor)), uintptr(unsafe.Pointer(&size)),
	)
	if result == 0 {
		return callErr
	}
	if descriptor == 0 {
		return errors.New("WRITER_DACL_INVALID")
	}
	defer syscall.LocalFree(syscall.Handle(descriptor))
	result, _, callErr = writerSetKernelObjectSecurity.Call(
		file.Fd(), writerDACLInformation|writerProtectedDACLInformation, descriptor,
	)
	if result == 0 {
		return callErr
	}
	return nil
}

func createWriterFile(path string, _ os.FileMode) (*os.File, error) {
	name, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return nil, err
	}
	handle, err := syscall.CreateFile(name, writerGenericWrite|writerReadControl|writerWriteDACL, 0, nil,
		writerCreateNew, writerFileAttributeNormal|writerOpenReparsePoint, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(handle), path), nil
}

func openWriterLockFile(path string) (*os.File, error) {
	name, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return nil, err
	}
	handle, err := syscall.CreateFile(name, writerGenericRead|writerGenericWrite|writerReadControl|writerWriteDACL,
		writerShareRead|writerShareWrite|writerShareDelete, nil, writerOpenAlways,
		writerFileAttributeNormal|writerOpenReparsePoint, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(handle), path), nil
}

func openWriterSecurityHandle(path string) (*os.File, error) {
	name, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return nil, err
	}
	handle, err := syscall.CreateFile(name, writerFileReadAttributes|writerReadControl|writerWriteDACL,
		writerShareRead|writerShareWrite|writerShareDelete, nil, writerOpenExisting,
		writerOpenReparsePoint|writerBackupSemantics, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(handle), path), nil
}

func writerFileIdentity(file *os.File) (string, error) {
	var information syscall.ByHandleFileInformation
	if err := syscall.GetFileInformationByHandle(syscall.Handle(file.Fd()), &information); err != nil {
		return "", err
	}
	return fmt.Sprintf("%08x:%08x%08x", information.VolumeSerialNumber, information.FileIndexHigh, information.FileIndexLow), nil
}

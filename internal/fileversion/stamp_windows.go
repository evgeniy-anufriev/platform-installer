package fileversion

import (
	"os"
	"unsafe"

	"golang.org/x/sys/windows"
)

func Read(file *os.File) (Stamp, bool) {
	handle := windows.Handle(file.Fd())
	var filesystem [16]uint16
	if windows.GetVolumeInformationByHandle(handle, nil, 0, nil, nil, nil, &filesystem[0], uint32(len(filesystem))) != nil {
		return Stamp{}, false
	}
	switch windows.UTF16ToString(filesystem[:]) {
	case "NTFS", "ReFS":
	default:
		return Stamp{}, false
	}
	var identity windows.ByHandleFileInformation
	var basic struct {
		CreationTime, LastAccessTime, LastWriteTime, ChangeTime int64
		Attributes, Padding                                     uint32
	}
	if windows.GetFileInformationByHandle(handle, &identity) != nil ||
		identity.NumberOfLinks != 1 ||
		identity.FileAttributes&(windows.FILE_ATTRIBUTE_DIRECTORY|windows.FILE_ATTRIBUTE_REPARSE_POINT) != 0 ||
		windows.GetFileInformationByHandleEx(handle, windows.FileBasicInfo,
			(*byte)(unsafe.Pointer(&basic)), uint32(unsafe.Sizeof(basic))) != nil ||
		basic.ChangeTime == 0 {
		return Stamp{}, false
	}
	inode := uint64(identity.FileIndexHigh)<<32 | uint64(identity.FileIndexLow)
	if inode == 0 {
		return Stamp{}, false
	}
	return Stamp{Device: uint64(identity.VolumeSerialNumber), Inode: inode,
		Changed: basic.ChangeTime, Created: basic.CreationTime,
		Modified: basic.LastWriteTime,
		Size:     int64(uint64(identity.FileSizeHigh)<<32 | uint64(identity.FileSizeLow))}, true
}

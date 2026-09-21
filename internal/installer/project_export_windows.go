//go:build windows

package installer

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"unsafe"

	"golang.org/x/sys/windows"
)

type exportIdentity struct {
	volume uint32
	index  uint64
}

func (identity exportIdentity) empty() bool { return identity.volume == 0 && identity.index == 0 }
func (identity exportIdentity) String() string {
	return hex.EncodeToString([]byte{byte(identity.volume), byte(identity.volume >> 8), byte(identity.volume >> 16), byte(identity.volume >> 24), byte(identity.index), byte(identity.index >> 8), byte(identity.index >> 16), byte(identity.index >> 24), byte(identity.index >> 32), byte(identity.index >> 40), byte(identity.index >> 48), byte(identity.index >> 56)})
}

type exportFileIdentity struct {
	exportIdentity
	links uint32
}

type exportDirectory struct{ handle windows.Handle }

type exportEntryKind uint8

const (
	exportEntryDirectory exportEntryKind = iota + 1
	exportEntryRegular
)

type exportEntry struct {
	name string
	kind exportEntryKind
}

func openExportSourceDirectory(root string) (*exportDirectory, error) {
	return openExportWindowsRoot(root, windows.FILE_GENERIC_READ)
}

func openExportDestinationDirectory(root string) (*exportDirectory, error) {
	return openExportWindowsRoot(root, windows.FILE_GENERIC_READ|windows.FILE_GENERIC_WRITE|windows.FILE_TRAVERSE|windows.DELETE)
}

func openExportWindowsRoot(root string, access uint32) (*exportDirectory, error) {
	volume := filepath.VolumeName(root)
	if volume == "" || strings.HasPrefix(volume, `\\`) {
		return nil, errors.New("unsafe export root")
	}
	logicalAnchor := volume + "\\"
	anchor := `\\?\` + logicalAnchor
	pointer, err := windows.UTF16PtrFromString(anchor)
	if err != nil {
		return nil, err
	}
	// A drive root is the trusted, non-replaceable traversal anchor. It is not a
	// reparse point itself, so avoid OPEN_REPARSE_POINT here; every untrusted
	// component below it is opened with the no-follow relative helper.
	handle, err := windows.CreateFile(pointer, windows.FILE_GENERIC_READ, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_BACKUP_SEMANTICS, 0)
	if err != nil {
		return nil, err
	}
	directory := &exportDirectory{handle: handle}
	if err := directory.verify(); err != nil {
		directory.close()
		return nil, err
	}
	relative, err := filepath.Rel(logicalAnchor, root)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		directory.close()
		return nil, errors.New("unsafe export root")
	}
	components := strings.Split(relative, string(filepath.Separator))
	opened, err := directory.openDirectoryWithAccess(components, access)
	directory.close()
	return opened, err
}

func (directory *exportDirectory) close() {
	if directory != nil && directory.handle != 0 {
		_ = windows.CloseHandle(directory.handle)
		directory.handle = 0
	}
}

func (directory *exportDirectory) verify() error {
	var info windows.ByHandleFileInformation
	if directory == nil || directory.handle == 0 || windows.GetFileInformationByHandle(directory.handle, &info) != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY == 0 {
		return errors.New("unsafe export directory")
	}
	return nil
}

func (directory *exportDirectory) identity() exportIdentity {
	var info windows.ByHandleFileInformation
	if directory == nil || directory.handle == 0 || windows.GetFileInformationByHandle(directory.handle, &info) != nil {
		return exportIdentity{}
	}
	return exportIdentity{volume: info.VolumeSerialNumber, index: uint64(info.FileIndexHigh)<<32 | uint64(info.FileIndexLow)}
}

func (directory *exportDirectory) openDirectory(parts []string) (*exportDirectory, error) {
	return directory.openDirectoryWithAccess(parts, windows.FILE_GENERIC_READ)
}

func (directory *exportDirectory) openDirectoryWithAccess(parts []string, access uint32) (*exportDirectory, error) {
	if directory == nil || directory.handle == 0 {
		return nil, errors.New("unsafe export directory")
	}
	current := directory.handle
	owned := false
	for index, part := range parts {
		partAccess := uint32(windows.FILE_GENERIC_READ)
		if index == len(parts)-1 {
			partAccess = access
		}
		next, err := openExportWindowsRelative(current, part, true, partAccess, windows.FILE_OPEN)
		if err != nil {
			if owned {
				_ = windows.CloseHandle(current)
			}
			return nil, exportWindowsNotExist(err)
		}
		if owned {
			_ = windows.CloseHandle(current)
		}
		current, owned = next, true
	}
	if !owned {
		return nil, errors.New("unsafe export directory")
	}
	return &exportDirectory{handle: current}, nil
}

func (directory *exportDirectory) entries() ([]exportEntry, error) {
	duplicate, err := duplicateExportWindowsHandle(directory.handle)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(duplicate), "export-directory")
	if file == nil {
		_ = windows.CloseHandle(duplicate)
		return nil, errors.New("unsafe export directory")
	}
	entries, err := file.ReadDir(maxExportDirectoryEntries + 1)
	closeErr := file.Close()
	if (err != nil && !errors.Is(err, io.EOF)) || closeErr != nil || len(entries) > maxExportDirectoryEntries {
		return nil, errors.New("unsafe export directory")
	}
	result := make([]exportEntry, 0, len(entries))
	for _, entry := range entries {
		name := entry.Name()
		if name == "" || name == "." || name == ".." {
			return nil, errors.New("unsafe export directory")
		}
		child, directoryErr := openExportWindowsRelative(directory.handle, name, true, windows.FILE_GENERIC_READ, windows.FILE_OPEN)
		if directoryErr == nil {
			_ = windows.CloseHandle(child)
			result = append(result, exportEntry{name: name, kind: exportEntryDirectory})
			continue
		}
		child, fileErr := openExportWindowsRelative(directory.handle, name, false, windows.FILE_GENERIC_READ, windows.FILE_OPEN)
		if fileErr != nil {
			return nil, errors.New("unsafe export directory")
		}
		_ = windows.CloseHandle(child)
		result = append(result, exportEntry{name: name, kind: exportEntryRegular})
	}
	sort.Slice(result, func(left, right int) bool { return result[left].name < result[right].name })
	return result, nil
}

func (directory *exportDirectory) readFile(parts []string, limit int64) ([]byte, exportFileIdentity, error) {
	if len(parts) == 0 {
		return nil, exportFileIdentity{}, errors.New("unsafe export file")
	}
	parent := directory
	var owned *exportDirectory
	if len(parts) > 1 {
		var err error
		owned, err = directory.openDirectory(parts[:len(parts)-1])
		if err != nil {
			return nil, exportFileIdentity{}, err
		}
		defer owned.close()
		parent = owned
	}
	handle, err := openExportWindowsRelative(parent.handle, parts[len(parts)-1], false, windows.FILE_GENERIC_READ, windows.FILE_OPEN)
	if err != nil {
		return nil, exportFileIdentity{}, exportWindowsNotExist(err)
	}
	file := os.NewFile(uintptr(handle), parts[len(parts)-1])
	if file == nil {
		_ = windows.CloseHandle(handle)
		return nil, exportFileIdentity{}, errors.New("unsafe export file")
	}
	defer file.Close()
	identity, size, err := exportWindowsFileIdentity(handle)
	if err != nil || identity.links != 1 {
		return nil, exportFileIdentity{}, errors.New("unsafe export file")
	}
	if size > limit {
		return nil, exportFileIdentity{}, errors.New("EXPORT_LIMIT_EXCEEDED")
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if err != nil || int64(len(data)) != size {
		return nil, exportFileIdentity{}, errors.New("unsafe export file")
	}
	after, afterSize, afterErr := exportWindowsFileIdentity(handle)
	if afterErr != nil || after != identity || afterSize != size {
		return nil, exportFileIdentity{}, errors.New("PROJECT_CHANGED")
	}
	return data, identity, nil
}

func (directory *exportDirectory) exists(name string) (bool, error) {
	handle, directoryErr := openExportWindowsRelative(directory.handle, name, true, windows.FILE_GENERIC_READ, windows.FILE_OPEN)
	if directoryErr == nil {
		_ = windows.CloseHandle(handle)
		return true, nil
	}
	handle, fileErr := openExportWindowsRelative(directory.handle, name, false, windows.FILE_GENERIC_READ, windows.FILE_OPEN)
	if fileErr == nil {
		_ = windows.CloseHandle(handle)
		return true, nil
	}
	if isExportNotExist(exportWindowsNotExist(directoryErr)) && isExportNotExist(exportWindowsNotExist(fileErr)) {
		return false, nil
	}
	return false, errors.New("unsafe export destination")
}

func (directory *exportDirectory) createStaging(_ string) (*exportDirectory, string, error) {
	for attempt := 0; attempt < 16; attempt++ {
		value := make([]byte, 12)
		if _, err := rand.Read(value); err != nil {
			return nil, "", err
		}
		name := ".platform-export-" + hex.EncodeToString(value)
		handle, err := openExportWindowsRelative(directory.handle, name, true, windows.FILE_GENERIC_READ|windows.FILE_GENERIC_WRITE|windows.DELETE, windows.FILE_CREATE)
		if err == nil {
			return &exportDirectory{handle: handle}, name, nil
		}
		if !errors.Is(err, windows.ERROR_FILE_EXISTS) && !errors.Is(err, windows.ERROR_ALREADY_EXISTS) {
			return nil, "", err
		}
	}
	return nil, "", errors.New("staging name collision")
}

func (directory *exportDirectory) createDirectory(name string) (*exportDirectory, error) {
	handle, err := openExportWindowsRelative(directory.handle, name, true, windows.FILE_GENERIC_READ|windows.FILE_GENERIC_WRITE|windows.DELETE, windows.FILE_CREATE)
	if err != nil {
		return nil, err
	}
	return &exportDirectory{handle: handle}, nil
}

func (directory *exportDirectory) writeFile(name string, content []byte) error {
	handle, err := openExportWindowsRelative(directory.handle, name, false, windows.FILE_GENERIC_READ|windows.FILE_GENERIC_WRITE|windows.DELETE, windows.FILE_CREATE)
	if err != nil {
		return err
	}
	file := os.NewFile(uintptr(handle), name)
	if file == nil {
		_ = windows.CloseHandle(handle)
		return errors.New("unsafe export file")
	}
	if _, err := file.Write(content); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return err
	}
	return file.Close()
}

func (directory *exportDirectory) publish(staging *exportDirectory, _ string, destination string) error {
	name, err := windows.UTF16FromString(destination)
	if err != nil {
		return err
	}
	type renameHeader struct {
		ReplaceIfExists byte
		_               [7]byte
		RootDirectory   windows.Handle
		FileNameLength  uint32
		FileName        uint16
	}
	headerSize := int(unsafe.Offsetof(renameHeader{}.FileName))
	buffer := make([]byte, headerSize+len(name)*2)
	header := (*renameHeader)(unsafe.Pointer(&buffer[0]))
	header.RootDirectory = directory.handle
	header.FileNameLength = uint32((len(name) - 1) * 2)
	copy(buffer[headerSize:], unsafe.Slice((*byte)(unsafe.Pointer(&name[0])), len(name)*2))
	var status windows.IO_STATUS_BLOCK
	// SetFileInformationByHandle(FileRenameInfo) rejects a non-nil
	// RootDirectory on current Windows despite the documented relative-name
	// shape. NtSetInformationFile's FileRenameInformation class preserves the
	// retained parent-handle authority required by UI-01I.
	return windows.NtSetInformationFile(staging.handle, &status, &buffer[0], uint32(len(buffer)), 10)
}

func (directory *exportDirectory) removeOwnedTree(staging *exportDirectory, _ string) error {
	if staging == nil || staging.identity().empty() {
		return nil
	}
	if err := removeExportWindowsDirectory(staging); err != nil {
		return err
	}
	return markExportWindowsDelete(staging.handle)
}

func removeExportWindowsDirectory(directory *exportDirectory) error {
	entries, err := directory.entries()
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if entry.kind == exportEntryDirectory {
			child, openErr := directory.openDirectory([]string{entry.name})
			if openErr != nil {
				return openErr
			}
			err = removeExportWindowsDirectory(child)
			if err == nil {
				err = markExportWindowsDelete(child.handle)
			}
			child.close()
			if err != nil {
				return err
			}
			continue
		}
		handle, openErr := openExportWindowsRelative(directory.handle, entry.name, false, windows.DELETE, windows.FILE_OPEN)
		if openErr != nil {
			return openErr
		}
		err = markExportWindowsDelete(handle)
		_ = windows.CloseHandle(handle)
		if err != nil {
			return err
		}
	}
	return nil
}

func markExportWindowsDelete(handle windows.Handle) error {
	buffer := []byte{1}
	return windows.SetFileInformationByHandle(handle, windows.FileDispositionInfo, &buffer[0], uint32(len(buffer)))
}

func openExportWindowsRelative(root windows.Handle, name string, directory bool, access, disposition uint32) (windows.Handle, error) {
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
	if err := windows.NtCreateFile(&handle, access, &object, &status, nil, 0, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE, disposition, options, 0, 0); err != nil {
		return 0, err
	}
	if err := verifyExportWindowsHandle(handle, directory); err != nil {
		_ = windows.CloseHandle(handle)
		return 0, err
	}
	return handle, nil
}

func verifyExportWindowsHandle(handle windows.Handle, directory bool) error {
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || (info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0) != directory {
		return errors.New("unsafe export object")
	}
	return nil
}

func exportWindowsFileIdentity(handle windows.Handle) (exportFileIdentity, int64, error) {
	var info windows.ByHandleFileInformation
	if err := windows.GetFileInformationByHandle(handle, &info); err != nil || info.FileAttributes&windows.FILE_ATTRIBUTE_REPARSE_POINT != 0 || info.FileAttributes&windows.FILE_ATTRIBUTE_DIRECTORY != 0 {
		return exportFileIdentity{}, 0, errors.New("unsafe export file")
	}
	identity := exportFileIdentity{exportIdentity: exportIdentity{volume: info.VolumeSerialNumber, index: uint64(info.FileIndexHigh)<<32 | uint64(info.FileIndexLow)}, links: info.NumberOfLinks}
	return identity, int64(uint64(info.FileSizeHigh)<<32 | uint64(info.FileSizeLow)), nil
}

func duplicateExportWindowsHandle(handle windows.Handle) (windows.Handle, error) {
	var duplicate windows.Handle
	err := windows.DuplicateHandle(windows.CurrentProcess(), handle, windows.CurrentProcess(), &duplicate, 0, false, windows.DUPLICATE_SAME_ACCESS)
	return duplicate, err
}

func exportWindowsNotExist(err error) error {
	if err == windows.ERROR_FILE_NOT_FOUND || err == windows.ERROR_PATH_NOT_FOUND || err == windows.STATUS_OBJECT_NAME_NOT_FOUND || err == windows.STATUS_OBJECT_PATH_NOT_FOUND || errors.Is(err, windows.ERROR_FILE_NOT_FOUND) || errors.Is(err, windows.ERROR_PATH_NOT_FOUND) || errors.Is(err, windows.STATUS_OBJECT_NAME_NOT_FOUND) || errors.Is(err, windows.STATUS_OBJECT_PATH_NOT_FOUND) {
		return os.ErrNotExist
	}
	return err
}

func isExportNotExist(err error) bool { return errors.Is(err, os.ErrNotExist) }

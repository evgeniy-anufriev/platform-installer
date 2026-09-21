//go:build linux

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

	"golang.org/x/sys/unix"
)

type exportIdentity struct {
	device uint64
	inode  uint64
}

func (identity exportIdentity) empty() bool { return identity.device == 0 && identity.inode == 0 }
func (identity exportIdentity) String() string {
	return hex.EncodeToString([]byte{byte(identity.device), byte(identity.device >> 8), byte(identity.device >> 16), byte(identity.device >> 24), byte(identity.device >> 32), byte(identity.device >> 40), byte(identity.device >> 48), byte(identity.device >> 56), byte(identity.inode), byte(identity.inode >> 8), byte(identity.inode >> 16), byte(identity.inode >> 24), byte(identity.inode >> 32), byte(identity.inode >> 40), byte(identity.inode >> 48), byte(identity.inode >> 56)})
}

type exportFileIdentity struct {
	exportIdentity
	links uint64
}

type exportDirectory struct{ fd int }

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
	return openExportUnixRoot(root)
}
func openExportDestinationDirectory(root string) (*exportDirectory, error) {
	return openExportUnixRoot(root)
}

func openExportUnixRoot(root string) (*exportDirectory, error) {
	if !filepath.IsAbs(root) {
		return nil, errors.New("unsafe export root")
	}
	fd, err := unix.Open("/", unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	directory := &exportDirectory{fd: fd}
	if err := directory.verify(); err != nil {
		directory.close()
		return nil, err
	}
	relative := strings.TrimPrefix(filepath.Clean(root), string(filepath.Separator))
	if relative == "" {
		directory.close()
		return nil, errors.New("unsafe export root")
	}
	opened, err := directory.openDirectory(strings.Split(relative, string(filepath.Separator)))
	directory.close()
	return opened, err
}

func (directory *exportDirectory) close() {
	if directory != nil && directory.fd >= 0 {
		_ = unix.Close(directory.fd)
		directory.fd = -1
	}
}

func (directory *exportDirectory) verify() error {
	var stat unix.Stat_t
	if directory == nil || directory.fd < 0 || unix.Fstat(directory.fd, &stat) != nil || stat.Mode&unix.S_IFMT != unix.S_IFDIR {
		return errors.New("unsafe export directory")
	}
	return nil
}

func (directory *exportDirectory) identity() exportIdentity {
	var stat unix.Stat_t
	if directory == nil || directory.fd < 0 || unix.Fstat(directory.fd, &stat) != nil {
		return exportIdentity{}
	}
	return exportIdentity{device: uint64(stat.Dev), inode: stat.Ino}
}

func (directory *exportDirectory) openDirectory(parts []string) (*exportDirectory, error) {
	if directory == nil || directory.fd < 0 {
		return nil, errors.New("unsafe export directory")
	}
	current, owned := directory.fd, false
	for _, part := range parts {
		next, err := unix.Openat(current, part, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if err != nil {
			if owned {
				_ = unix.Close(current)
			}
			return nil, exportUnixNotExist(err)
		}
		if owned {
			_ = unix.Close(current)
		}
		current, owned = next, true
	}
	if !owned {
		return nil, errors.New("unsafe export directory")
	}
	child := &exportDirectory{fd: current}
	if err := child.verify(); err != nil {
		child.close()
		return nil, err
	}
	return child, nil
}

func (directory *exportDirectory) entries() ([]exportEntry, error) {
	duplicate, err := unix.Dup(directory.fd)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(duplicate), "export-directory")
	if file == nil {
		_ = unix.Close(duplicate)
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
		child, directoryErr := directory.openDirectory([]string{name})
		if directoryErr == nil {
			child.close()
			result = append(result, exportEntry{name: name, kind: exportEntryDirectory})
			continue
		}
		fd, fileErr := unix.Openat(directory.fd, name, unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
		if fileErr != nil {
			return nil, errors.New("unsafe export directory")
		}
		var stat unix.Stat_t
		valid := unix.Fstat(fd, &stat) == nil && stat.Mode&unix.S_IFMT == unix.S_IFREG
		_ = unix.Close(fd)
		if !valid {
			return nil, errors.New("unsafe export directory")
		}
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
	fd, err := unix.Openat(parent.fd, parts[len(parts)-1], unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, exportFileIdentity{}, exportUnixNotExist(err)
	}
	file := os.NewFile(uintptr(fd), parts[len(parts)-1])
	if file == nil {
		_ = unix.Close(fd)
		return nil, exportFileIdentity{}, errors.New("unsafe export file")
	}
	defer file.Close()
	identity, size, err := exportUnixFileIdentity(fd)
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
	after, afterSize, afterErr := exportUnixFileIdentity(fd)
	if afterErr != nil || after != identity || afterSize != size {
		return nil, exportFileIdentity{}, errors.New("PROJECT_CHANGED")
	}
	return data, identity, nil
}

func (directory *exportDirectory) exists(name string) (bool, error) {
	child, directoryErr := directory.openDirectory([]string{name})
	if directoryErr == nil {
		child.close()
		return true, nil
	}
	fd, fileErr := unix.Openat(directory.fd, name, unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0)
	if fileErr == nil {
		_ = unix.Close(fd)
		return true, nil
	}
	if isExportNotExist(exportUnixNotExist(directoryErr)) && isExportNotExist(exportUnixNotExist(fileErr)) {
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
		if err := unix.Mkdirat(directory.fd, name, 0o700); err == nil {
			staging, openErr := directory.openDirectory([]string{name})
			if openErr != nil {
				return nil, "", openErr
			}
			return staging, name, nil
		} else if !errors.Is(err, unix.EEXIST) {
			return nil, "", err
		}
	}
	return nil, "", errors.New("staging name collision")
}

func (directory *exportDirectory) createDirectory(name string) (*exportDirectory, error) {
	if err := unix.Mkdirat(directory.fd, name, 0o700); err != nil {
		return nil, err
	}
	return directory.openDirectory([]string{name})
}

func (directory *exportDirectory) writeFile(name string, content []byte) error {
	fd, err := unix.Openat(directory.fd, name, unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW|unix.O_CLOEXEC, 0o600)
	if err != nil {
		return err
	}
	file := os.NewFile(uintptr(fd), name)
	if file == nil {
		_ = unix.Close(fd)
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

func (directory *exportDirectory) publish(_ *exportDirectory, stagingName, destination string) error {
	return unix.Renameat2(directory.fd, stagingName, directory.fd, destination, unix.RENAME_NOREPLACE)
}

func (directory *exportDirectory) removeOwnedTree(staging *exportDirectory, stagingName string) error {
	linked, err := directory.openDirectory([]string{stagingName})
	if err != nil {
		return err
	}
	linkedIdentity, stagingIdentity := linked.identity(), staging.identity()
	linked.close()
	if linkedIdentity != stagingIdentity {
		return errors.New("EXPORT_STAGING_RETAINED")
	}
	// Linux has no unlink-by-open-directory-handle primitive. A pathname-based
	// recursive cleanup could delete a sibling swapped in after the identity
	// check above, so fail closed and leave staging for operator cleanup.
	return errors.New("EXPORT_STAGING_RETAINED")
}

func exportUnixFileIdentity(fd int) (exportFileIdentity, int64, error) {
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil || stat.Mode&unix.S_IFMT != unix.S_IFREG {
		return exportFileIdentity{}, 0, errors.New("unsafe export file")
	}
	return exportFileIdentity{exportIdentity: exportIdentity{device: uint64(stat.Dev), inode: stat.Ino}, links: uint64(stat.Nlink)}, stat.Size, nil
}

func exportUnixNotExist(err error) error {
	if errors.Is(err, unix.ENOENT) || errors.Is(err, unix.ENOTDIR) {
		return os.ErrNotExist
	}
	return err
}

func isExportNotExist(err error) bool { return errors.Is(err, os.ErrNotExist) }

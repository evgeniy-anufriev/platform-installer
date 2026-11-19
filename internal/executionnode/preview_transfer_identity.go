package executionnode

import (
	"archive/tar"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"

	"platform-installer/internal/fileversion"
)

var errPreviewStampUnavailable = errors.New("preview file version unavailable")

// The desktop opens one project at a time. Keep only the most recent tar hash,
// and only for the service preview. The node still verifies the actual archive.
var previewArchiveIdentity = struct {
	sync.Mutex
	stamp, slot, digest string
}{}

func previewTransferIdentity(root string) (string, string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", "", err
	}
	stamp, err := previewArchiveStamp(absolute)
	if errors.Is(err, errPreviewStampUnavailable) {
		return projectTransferIdentity(root)
	}
	if err != nil {
		return "", "", err
	}
	previewArchiveIdentity.Lock()
	if previewArchiveIdentity.stamp == stamp {
		slot, digest := previewArchiveIdentity.slot, previewArchiveIdentity.digest
		previewArchiveIdentity.Unlock()
		return slot, digest, nil
	}
	previewArchiveIdentity.Unlock()
	slot, digest, err := projectTransferIdentity(root)
	if err != nil {
		return "", "", err
	}
	after, err := previewArchiveStamp(absolute)
	if err != nil || after != stamp {
		// Some filesystems update metadata as a side effect of reading the
		// file. Keep the old full-read path when the stamp cannot be reused.
		return projectTransferIdentity(root)
	}
	previewArchiveIdentity.Lock()
	previewArchiveIdentity.stamp, previewArchiveIdentity.slot, previewArchiveIdentity.digest = stamp, slot, digest
	previewArchiveIdentity.Unlock()
	return slot, digest, nil
}

func previewArchiveStamp(absolute string) (string, error) {
	hash := sha256.New()
	encode := json.NewEncoder(hash)
	if err := encode.Encode(absolute); err != nil {
		return "", err
	}
	err := visitProjectArchive(absolute, func(candidate string) error {
		return visitTarPath(absolute, candidate, func(path string, info os.FileInfo, header *tar.Header) error {
			if err := encode.Encode(header); err != nil || info.IsDir() {
				return err
			}
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()
			opened, err := file.Stat()
			if err != nil || !os.SameFile(info, opened) || info.Size() != opened.Size() || !info.ModTime().Equal(opened.ModTime()) {
				return errPreviewStampUnavailable
			}
			stamp, ok := fileversion.Read(file)
			if !ok {
				return errPreviewStampUnavailable
			}
			return encode.Encode(stamp)
		})
	})
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

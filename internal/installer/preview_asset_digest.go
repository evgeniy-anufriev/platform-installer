package installer

import (
	"os"
	"strings"
	"sync"

	"platform-installer/internal/fileversion"
)

const maxPreviewAssetDigests = 4096

var previewAssetDigests = struct {
	sync.Mutex
	values map[fileversion.Stamp]string
}{values: make(map[fileversion.Stamp]string)}

type previewAssetRead struct {
	stamp     fileversion.Stamp
	cacheable bool
	digest    string
}

func (read *previewAssetRead) lookup(file *os.File) bool {
	read.stamp, read.cacheable = fileversion.Read(file)
	if read.cacheable {
		previewAssetDigests.Lock()
		read.digest = previewAssetDigests.values[read.stamp]
		previewAssetDigests.Unlock()
	}
	return read.digest != ""
}

func (read *previewAssetRead) unchanged(file *os.File) bool {
	if !read.cacheable {
		return true
	}
	stamp, ok := fileversion.Read(file)
	return ok && stamp == read.stamp
}

func (read *previewAssetRead) remember(digest string) {
	if !read.cacheable {
		return
	}
	previewAssetDigests.Lock()
	defer previewAssetDigests.Unlock()
	if len(previewAssetDigests.values) >= maxPreviewAssetDigests {
		clear(previewAssetDigests.values)
	}
	previewAssetDigests.values[read.stamp] = digest
}

func packageAssetPath(logical string) bool {
	parts := strings.SplitN(logical, "/", 5)
	return len(parts) == 5 && (parts[0] == "application-packages" || parts[0] == "library-packages") && parts[3] == "assets"
}

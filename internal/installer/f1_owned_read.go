package installer

import (
	"errors"
	"path"
	"strings"
)

// readF1OwnedDocument is intentionally limited to the fixed Installer-owned
// managed documents consumed by the F1 local projection. Its platform reader
// binds every traversal step and the final bytes to opened no-follow handles.
func readF1OwnedDocument(root, logical string) ([]byte, error) {
	if !safeF1OwnedLogicalPath(logical) {
		return nil, errors.New("managed logical path is invalid")
	}
	return readF1OwnedFile(root, strings.Split(logical, "/"), maxManagedDocumentBytes)
}

func safeF1OwnedLogicalPath(logical string) bool {
	if logical == "" || strings.Contains(logical, "\\") || path.Clean(logical) != logical || strings.HasPrefix(logical, "/") {
		return false
	}
	for _, part := range strings.Split(logical, "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	return true
}

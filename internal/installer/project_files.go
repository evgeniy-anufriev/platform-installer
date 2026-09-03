package installer

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const (
	desiredDocument   = "inventory/group_vars/all/platform-installer.yml"
	generatedDocument = "inventory/group_vars/all/platform-state.yml"
)

type projectDocument struct {
	LogicalPath string
	Digest      string
}

func digestBytes(content []byte) string {
	sum := sha256.Sum256(content)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func cleanRoot(root string) (string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	resolved, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return "", blocked("PROJECT_PATH_INVALID", "Project root cannot be resolved", "projectRoot")
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.IsDir() {
		return "", blocked("PROJECT_PATH_INVALID", "Project root is not a directory", "projectRoot")
	}
	return filepath.Clean(resolved), nil
}

func logicalPath(path string) string { return filepath.ToSlash(path) }

func safeProjectPath(root, logical string, allowMissing bool) (string, error) {
	if logical == "" || filepath.IsAbs(logical) || filepath.VolumeName(logical) != "" {
		return "", blocked("PATH_UNSAFE", "Managed document path is unsafe", "document.logicalPath")
	}
	clean := filepath.Clean(filepath.FromSlash(logical))
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return "", blocked("PATH_UNSAFE", "Managed document path escapes the project", "document.logicalPath")
	}
	path := filepath.Join(root, clean)
	relative, err := filepath.Rel(root, path)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", blocked("PATH_UNSAFE", "Managed document path escapes the project", "document.logicalPath")
	}
	current := root
	parts := strings.Split(filepath.ToSlash(clean), "/")
	for index, part := range parts {
		current = filepath.Join(current, part)
		info, statErr := os.Lstat(current)
		if statErr != nil {
			if os.IsNotExist(statErr) && allowMissing {
				break
			}
			return "", blocked("WRITE_OWNERSHIP_REQUIRED", "Installer-owned document does not exist", "document")
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return "", blocked("PATH_UNSAFE", "Managed document path contains a symlink or reparse point", "document.logicalPath")
		}
		if index < len(parts)-1 && !info.IsDir() {
			return "", blocked("PATH_UNSAFE", "Managed document parent is not a directory", "document.logicalPath")
		}
	}
	return path, nil
}

func collectProjectDocuments(root string) ([]projectDocument, string, error) {
	candidates := []string{"project.yml", "ansible.cfg", "inventory/hosts.yml"}
	for _, directory := range []string{"inventory/group_vars", "inventory/host_vars"} {
		base := filepath.Join(root, filepath.FromSlash(directory))
		if _, err := os.Stat(base); os.IsNotExist(err) {
			continue
		}
		err := filepath.WalkDir(base, func(path string, entry os.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			if entry.Type()&os.ModeSymlink != 0 {
				return blocked("PATH_UNSAFE", "Canonical project documents must not contain symlinks", "project")
			}
			if entry.IsDir() {
				return nil
			}
			extension := strings.ToLower(filepath.Ext(entry.Name()))
			if extension != ".yml" && extension != ".yaml" && extension != ".json" {
				return nil
			}
			relative, err := filepath.Rel(root, path)
			if err != nil {
				return err
			}
			candidates = append(candidates, logicalPath(relative))
			return nil
		})
		if err != nil {
			return nil, "", err
		}
	}
	sort.Strings(candidates)
	seen := make(map[string]bool)
	documents := make([]projectDocument, 0, len(candidates))
	var revisionInput []byte
	for _, logical := range candidates {
		if seen[logical] {
			continue
		}
		seen[logical] = true
		path, err := safeProjectPath(root, logical, true)
		if err != nil {
			return nil, "", err
		}
		content, err := os.ReadFile(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return nil, "", err
		}
		digest := digestBytes(content)
		documents = append(documents, projectDocument{LogicalPath: logical, Digest: digest})
		if logical != generatedDocument {
			revisionInput = append(revisionInput, []byte(logical)...)
			revisionInput = append(revisionInput, 0)
			revisionInput = append(revisionInput, []byte(digest)...)
			revisionInput = append(revisionInput, 0)
		}
	}
	return documents, digestBytes(revisionInput), nil
}

func managedHostDocument(hostID string) string {
	return "inventory/host_vars/" + hostID + "/platform-installer.yml"
}

func discoverOwnedPaths(root string) ([]string, error) {
	paths := []string{desiredDocument}
	hostRoot := filepath.Join(root, "inventory", "host_vars")
	entries, err := os.ReadDir(hostRoot)
	if err != nil && !os.IsNotExist(err) {
		return nil, err
	}
	for _, entry := range entries {
		if entry.IsDir() {
			paths = append(paths, managedHostDocument(entry.Name()))
		}
	}
	owned := make([]string, 0, len(paths))
	for _, logical := range paths {
		path, err := safeProjectPath(root, logical, true)
		if err != nil {
			return nil, err
		}
		content, err := os.ReadFile(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return nil, err
		}
		if strings.HasPrefix(string(content), string(managedHeader)) {
			owned = append(owned, logical)
		}
	}
	sort.Strings(owned)
	return owned, nil
}

func copyProject(source string) (string, func(), error) {
	parent, err := os.MkdirTemp("", "platform-installer-stage-")
	if err != nil {
		return "", nil, err
	}
	cleanup := func() { _ = os.RemoveAll(parent) }
	destination := filepath.Join(parent, "project")
	err = filepath.WalkDir(source, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		if relative == ".git" || relative == ".runtime" {
			return filepath.SkipDir
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return blocked("PATH_UNSAFE", "Staged projects must not contain symlinks", "project")
		}
		target := filepath.Join(destination, relative)
		if entry.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		input, err := os.Open(path)
		if err != nil {
			return err
		}
		defer input.Close()
		output, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, info.Mode().Perm())
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(output, input)
		closeErr := output.Close()
		if copyErr != nil {
			return copyErr
		}
		return closeErr
	})
	if err != nil {
		cleanup()
		return "", nil, fmt.Errorf("stage project: %w", err)
	}
	return destination, cleanup, nil
}

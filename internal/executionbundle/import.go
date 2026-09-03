package executionbundle

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// PrepareRuntimeInput creates a builder input from a verified bundle and an
// explicitly approved local artifact. The source file is never modified.
func PrepareRuntimeInput(bundle Verified, source, relative, expectedSHA string) (string, func(), error) {
	if bundle.Root == "" {
		return "", func() {}, errors.New("EXECUTION_ARTIFACT_IMPORT_BUNDLE_INVALID")
	}
	if !safeRuntimeArtifactRef(relative) || !digestValid(expectedSHA) {
		return "", func() {}, errors.New("EXECUTION_ARTIFACT_IMPORT_INVALID")
	}
	info, err := os.Lstat(source)
	if err != nil || !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 {
		return "", func() {}, errors.New("EXECUTION_ARTIFACT_IMPORT_SOURCE_INVALID")
	}
	sum, err := digestPath(source)
	if err != nil || sum != expectedSHA {
		return "", func() {}, errors.New("EXECUTION_ARTIFACT_IMPORT_CHECKSUM_MISMATCH")
	}
	root, err := os.MkdirTemp("", "platform-installer-artifact-import-")
	if err != nil {
		return "", func() {}, err
	}
	cleanup := func() { _ = os.RemoveAll(root) }
	if err := copyTree(filepath.Join(bundle.Root, "runtime"), root); err != nil {
		cleanup()
		return "", func() {}, err
	}
	destination := filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(relative, "runtime/")))
	if err := os.MkdirAll(filepath.Dir(destination), 0o700); err != nil {
		cleanup()
		return "", func() {}, err
	}
	out, err := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		cleanup()
		return "", func() {}, err
	}
	in, err := os.Open(source)
	if err != nil {
		_ = out.Close()
		cleanup()
		return "", func() {}, err
	}
	_, copyErr := io.Copy(out, in)
	closeInErr := in.Close()
	closeOutErr := out.Close()
	if copyErr != nil || closeInErr != nil || closeOutErr != nil {
		cleanup()
		return "", func() {}, errors.New("EXECUTION_ARTIFACT_IMPORT_COPY_FAILED")
	}
	return root, cleanup, nil
}

func safeRuntimeArtifactRef(value string) bool {
	return strings.HasPrefix(value, "runtime/") && filepath.ToSlash(filepath.Clean(value)) == value && !strings.Contains(value, "..") && len(value) > len("runtime/")
}

func digestPath(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return "sha256:" + hex.EncodeToString(hash.Sum(nil)), nil
}

func copyTree(source, destination string) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		if relative == "." {
			return nil
		}
		target := filepath.Join(destination, relative)
		if entry.Type()&os.ModeSymlink != 0 {
			return errors.New("EXECUTION_ARTIFACT_IMPORT_UNSAFE_BUNDLE")
		}
		if entry.IsDir() {
			return os.MkdirAll(target, 0o700)
		}
		if !entry.Type().IsRegular() {
			return errors.New("EXECUTION_ARTIFACT_IMPORT_UNSAFE_BUNDLE")
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		out, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
		if err != nil {
			_ = in.Close()
			return err
		}
		_, copyErr := io.Copy(out, in)
		_ = in.Close()
		closeErr := out.Close()
		if copyErr != nil {
			return copyErr
		}
		return closeErr
	})
}

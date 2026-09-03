package executionbundle

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Cache is operational state. It must never point at project desired state.
type Cache struct{ Root string }

func (c Cache) Publish(bundleRoot string) (Verified, error) {
	verified, err := ValidateRoot(bundleRoot)
	if err != nil {
		return Verified{}, err
	}
	root, err := cacheRoot(c.Root)
	if err != nil {
		return Verified{}, err
	}
	if err := os.MkdirAll(root, 0o700); err != nil {
		return Verified{}, fmt.Errorf("create bundle cache: %w", err)
	}
	destination := filepath.Join(root, strings.TrimPrefix(verified.Digest, "sha256:"))
	if existing, statErr := ValidateRoot(destination); statErr == nil {
		if existing.Digest == verified.Digest {
			return existing, nil
		}
		return Verified{}, errors.New("EXECUTION_BUNDLE_CACHE_CONFLICT")
	}
	if _, statErr := os.Lstat(destination); statErr == nil {
		return Verified{}, errors.New("EXECUTION_BUNDLE_CACHE_CONFLICT")
	}
	staging, err := os.MkdirTemp(root, ".staging-")
	if err != nil {
		return Verified{}, fmt.Errorf("create bundle staging: %w", err)
	}
	defer os.RemoveAll(staging)
	if err := copyVerifiedTree(verified.Root, staging); err != nil {
		return Verified{}, err
	}
	published, err := ValidateRoot(staging)
	if err != nil || published.Digest != verified.Digest {
		return Verified{}, errors.New("EXECUTION_BUNDLE_PUBLICATION_VERIFY_FAILED")
	}
	if err := os.Rename(staging, destination); err != nil {
		return Verified{}, fmt.Errorf("publish bundle: %w", err)
	}
	return ValidateRoot(destination)
}

func (c Cache) Resolve(override string, platform Platform) (Verified, error) {
	if override != "" {
		verified, err := ValidateRoot(override)
		if err != nil {
			return Verified{}, err
		}
		if supports(verified.Manifest, platform) {
			return verified, nil
		}
		return Verified{}, errors.New("EXECUTION_BUNDLE_INCOMPATIBLE")
	}
	root, err := cacheRoot(c.Root)
	if err != nil {
		return Verified{}, err
	}
	entries, err := os.ReadDir(root)
	if errors.Is(err, os.ErrNotExist) {
		return Verified{}, errors.New("EXECUTION_NODE_BUNDLE_MISSING")
	}
	if err != nil {
		return Verified{}, fmt.Errorf("read bundle cache: %w", err)
	}
	for _, entry := range entries {
		if !entry.IsDir() || strings.HasPrefix(entry.Name(), ".") {
			continue
		}
		verified, validationErr := ValidateRoot(filepath.Join(root, entry.Name()))
		if validationErr == nil && supports(verified.Manifest, platform) {
			return verified, nil
		}
	}
	return Verified{}, errors.New("EXECUTION_NODE_BUNDLE_MISSING")
}

func cacheRoot(root string) (string, error) {
	if root == "" {
		return "", errors.New("EXECUTION_BUNDLE_CACHE_INVALID")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", err
	}
	return absolute, nil
}

func supports(manifest Manifest, expected Platform) bool {
	for _, actual := range manifest.Platforms {
		if actual.OS == expected.OS && actual.Version == expected.Version && actual.Architecture == expected.Architecture {
			return true
		}
	}
	return false
}

func copyVerifiedTree(source, destination string) error {
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
		if !contained(destination, target) {
			return errors.New("EXECUTION_BUNDLE_COMPONENT_PATH_INVALID")
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
		if entry.IsDir() {
			return os.MkdirAll(target, 0o700)
		}
		if !entry.Type().IsRegular() {
			return errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
		input, err := os.Open(path)
		if err != nil {
			return err
		}
		defer input.Close()
		output, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err != nil {
			return err
		}
		_, copyErr := output.ReadFrom(input)
		closeErr := output.Close()
		if copyErr != nil {
			return copyErr
		}
		return closeErr
	})
}

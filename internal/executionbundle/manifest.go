// Package executionbundle validates the offline runtime directory distributed
// beside the Installer. It is intentionally limited to bundle integrity and
// compatibility; it contains no infrastructure or service semantics.
package executionbundle

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

const ProtocolVersion = "v1alpha1"

type Manifest struct {
	APIVersion        string      `yaml:"apiVersion" json:"apiVersion"`
	Kind              string      `yaml:"kind" json:"kind"`
	BundleVersion     string      `yaml:"bundleVersion" json:"bundleVersion"`
	BootstrapProtocol string      `yaml:"bootstrapProtocol" json:"bootstrapProtocol"`
	CoreVersion       string      `yaml:"coreVersion" json:"coreVersion"`
	CatalogDigest     string      `yaml:"catalogDigest" json:"catalogDigest"`
	SchemaDigest      string      `yaml:"schemaDigest" json:"schemaDigest"`
	Platforms         []Platform  `yaml:"platforms" json:"platforms"`
	Components        []Component `yaml:"components" json:"components"`
}

type Platform struct {
	OS           string `yaml:"os" json:"os"`
	Version      string `yaml:"version" json:"version"`
	Architecture string `yaml:"architecture" json:"architecture"`
}

type Component struct {
	Path   string `yaml:"path" json:"path"`
	SHA256 string `yaml:"sha256" json:"sha256"`
	Size   int64  `yaml:"size" json:"size"`
}

type Verified struct {
	Root         string
	Manifest     Manifest
	Digest       string
	rootIdentity string
}

func ValidateRoot(root string) (Verified, error) {
	root, err := filepath.Abs(root)
	if err != nil {
		return Verified{}, fmt.Errorf("resolve bundle root: %w", err)
	}
	info, err := os.Stat(root)
	if err != nil || !info.IsDir() {
		return Verified{}, errors.New("EXECUTION_BUNDLE_ROOT_INVALID")
	}
	rootIdentity, err := verifiedRootIdentity(root)
	if err != nil {
		return Verified{}, errors.New("EXECUTION_BUNDLE_ROOT_INVALID")
	}
	manifestPath := filepath.Join(root, "manifest.yaml")
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		return Verified{}, errors.New("EXECUTION_BUNDLE_MANIFEST_MISSING")
	}
	var manifest Manifest
	if err := yaml.Unmarshal(data, &manifest); err != nil {
		return Verified{}, errors.New("EXECUTION_BUNDLE_MANIFEST_INVALID")
	}
	if manifest.APIVersion != "platform.installer/execution-bundle/v1alpha1" || manifest.Kind != "ExecutionRuntimeBundle" || manifest.BundleVersion == "" || manifest.BootstrapProtocol != ProtocolVersion || manifest.CoreVersion == "" || !digestValid(manifest.CatalogDigest) || !digestValid(manifest.SchemaDigest) {
		return Verified{}, errors.New("EXECUTION_BUNDLE_MANIFEST_INVALID")
	}
	if len(manifest.Platforms) == 0 || len(manifest.Components) == 0 {
		return Verified{}, errors.New("EXECUTION_BUNDLE_CONTENT_MISSING")
	}
	for _, platform := range manifest.Platforms {
		if !safeToken(platform.OS) || !safeToken(platform.Version) || !safeToken(platform.Architecture) {
			return Verified{}, errors.New("EXECUTION_BUNDLE_PLATFORM_INVALID")
		}
	}
	paths := make(map[string]bool, len(manifest.Components))
	components := append([]Component(nil), manifest.Components...)
	sort.Slice(components, func(i, j int) bool { return components[i].Path < components[j].Path })
	if !equalComponents(components, manifest.Components) {
		return Verified{}, errors.New("EXECUTION_BUNDLE_MANIFEST_NOT_DETERMINISTIC")
	}
	for _, component := range manifest.Components {
		if !safeRelative(component.Path) || paths[component.Path] || !digestValid(component.SHA256) || component.Size < 0 {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_INVALID")
		}
		paths[component.Path] = true
		path := filepath.Join(root, filepath.FromSlash(component.Path))
		if !contained(root, path) {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_PATH_INVALID")
		}
		info, err := os.Lstat(path)
		if err != nil {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_MISSING")
		}
		if info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_UNSAFE")
		}
		if info.Size() != component.Size {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_CHECKSUM_MISMATCH")
		}
		digest, err := fileDigest(path)
		if err != nil || digest != component.SHA256 {
			return Verified{}, errors.New("EXECUTION_BUNDLE_COMPONENT_CHECKSUM_MISMATCH")
		}
	}
	return Verified{Root: root, Manifest: manifest, Digest: bytesDigest(data), rootIdentity: rootIdentity}, nil
}

func fileDigest(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err = io.Copy(hash, file); err != nil {
		return "", err
	}
	return "sha256:" + hex.EncodeToString(hash.Sum(nil)), nil
}
func bytesDigest(value []byte) string {
	sum := sha256.Sum256(value)
	return "sha256:" + hex.EncodeToString(sum[:])
}
func digestValid(value string) bool {
	if !strings.HasPrefix(value, "sha256:") || len(value) != 71 {
		return false
	}
	_, err := hex.DecodeString(value[7:])
	return err == nil
}
func safeToken(value string) bool {
	if value == "" || len(value) > 64 {
		return false
	}
	for _, char := range value {
		if !(char >= 'a' && char <= 'z' || char >= 'A' && char <= 'Z' || char >= '0' && char <= '9' || char == '.' || char == '_' || char == '-') {
			return false
		}
	}
	return true
}
func safeRelative(value string) bool {
	return value != "" && filepath.ToSlash(filepath.Clean(value)) == value && !strings.HasPrefix(value, "/") && !strings.HasPrefix(value, "../") && !strings.Contains(value, "/../")
}
func contained(root, path string) bool {
	relative, err := filepath.Rel(root, path)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator))
}
func equalComponents(left, right []Component) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

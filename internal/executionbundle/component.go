package executionbundle

import (
	"errors"
	"strings"

	"gopkg.in/yaml.v3"
)

const maxCatalogComponentBytes int64 = 8 * 1024 * 1024

// ReadVerifiedComponent returns bytes read from the same opened regular-file
// object whose size and digest are checked against a freshly verified manifest
// entry. It is intentionally limited to immutable execution-bundle components.
func ReadVerifiedComponent(verified Verified, componentPath string, limit int64) ([]byte, error) {
	if limit <= 0 || !safeRelative(componentPath) || verified.Root == "" || verified.rootIdentity == "" {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_INVALID")
	}
	var component *Component
	for index := range verified.Manifest.Components {
		candidate := &verified.Manifest.Components[index]
		if candidate.Path != componentPath {
			continue
		}
		if component != nil {
			return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_INVALID")
		}
		component = candidate
	}
	if component == nil || component.Size > limit {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_INVALID")
	}
	content, err := readVerifiedComponent(verified, *component, limit)
	if err != nil {
		return nil, err
	}
	if int64(len(content)) != component.Size || !strings.EqualFold(bytesDigest(content), component.SHA256) {
		return nil, errors.New("EXECUTION_BUNDLE_COMPONENT_CHECKSUM_MISMATCH")
	}
	return content, nil
}

// ReadVerifiedCatalog is the only catalog-component read surface used by the
// Installer. Keeping the fixed path and limit here prevents callers from
// turning ReadVerifiedComponent into a repository browser.
func ReadVerifiedCatalog(verified Verified) ([]byte, error) {
	return ReadVerifiedComponent(verified, "catalog/service-catalog.yml", maxCatalogComponentBytes)
}

// DeclaresManifestIdentity performs only the narrow, handle-bound manifest
// inspection needed to classify an incompatible exact bundle source. It never
// follows a link/reparse point and does not expose manifest content to callers.
func DeclaresManifestIdentity(root, artifactDigest, catalogDigest string) bool {
	data, err := readBundleManifest(root)
	if err != nil || !strings.EqualFold(bytesDigest(data), artifactDigest) {
		return false
	}
	var manifest struct {
		CatalogDigest string `yaml:"catalogDigest"`
	}
	return yaml.Unmarshal(data, &manifest) == nil && manifest.CatalogDigest == catalogDigest
}

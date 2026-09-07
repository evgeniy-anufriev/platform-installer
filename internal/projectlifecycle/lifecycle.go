// Package projectlifecycle owns the local, metadata-only project lifecycle.
// It deliberately does not load Ansible, contact an Execution Node or create
// any first-save inventory documents.
package projectlifecycle

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"

	"gopkg.in/yaml.v3"

	"platform-installer/internal/executionbundle"
)

const (
	DefaultCompatibilitySourceID = "default"
	ClassificationEmpty          = "EMPTY_MANAGED_PROJECT"
	ClassificationManaged        = "MANAGED_PROJECT"
	classificationEmpty          = ClassificationEmpty
	classificationManaged        = ClassificationManaged
	classificationExternal       = "EXTERNAL_PROJECT"
	classificationIncomplete     = "PROJECT_INPUT_INCOMPLETE"
	classificationInvalid        = "MANAGED_PROJECT_INVALID"
	classificationBlocked        = "PROJECT_OPEN_BLOCKED"
	managedProjectLabel          = "platform.installer/managed-project"
	managedProjectMarker         = "v1alpha1"
)

// FirstSaveEligible revalidates the portable managed-project marker and lock
// envelope without relying on process-local creation state.
func FirstSaveEligible(root string) bool {
	result, err := NewService(nil).OpenProject(context.Background(), root)
	return err == nil && result.Classification == ClassificationEmpty
}

type CreateProjectRequest struct {
	ProjectRoot           string `json:"projectRoot"`
	DisplayName           string `json:"displayName"`
	CompatibilitySourceID string `json:"compatibilitySourceId"`
}

type CompatibilitySourceSummary struct {
	ID            string `json:"id"`
	BundleDigest  string `json:"bundleDigest"`
	CatalogDigest string `json:"catalogDigest"`
	BundleVersion string `json:"bundleVersion"`
}

type Project struct {
	ID     string                     `json:"id"`
	Name   string                     `json:"name"`
	Source CompatibilitySourceSummary `json:"source"`
}

type Result struct {
	Root           string   `json:"root"`
	Classification string   `json:"classification"`
	Project        *Project `json:"project,omitempty"`
	Counts         Counts   `json:"counts"`
}

// Counts are a local presentation of an intentionally metadata-only project.
// They are never a second desired-state representation.
type Counts struct {
	Servers     int `json:"servers"`
	Deployments int `json:"deployments"`
	Runs        int `json:"runs"`
}

type source struct {
	id   string
	root string
}

type Service struct {
	sources       map[string]source
	publish       func(string, string) error
	beforePublish func(string) error
	removeAll     func(string) error
}

// NewService receives only installer-controlled bundle roots. The UI can name
// a source by its opaque ID but never supplies its filesystem path or locks.
func NewService(roots map[string]string) *Service {
	sources := make(map[string]source, len(roots))
	for id, root := range roots {
		sources[id] = source{id: id, root: root}
	}
	return &Service{sources: sources, publish: atomicPublish, removeAll: os.RemoveAll}
}

func (s *Service) CreateProject(ctx context.Context, request CreateProjectRequest) (result Result, err error) {
	if err := ctx.Err(); err != nil {
		return Result{}, err
	}
	name, err := validName(request.DisplayName)
	if err != nil {
		return Result{}, err
	}
	source, err := s.compatibilitySource(request.CompatibilitySourceID)
	if err != nil {
		return Result{}, err
	}
	root, parent, err := createDestination(request.ProjectRoot)
	if err != nil {
		return Result{}, err
	}
	if err := assertSafeAncestors(parent); err != nil {
		return Result{}, err
	}
	if _, err := os.Lstat(root); err == nil {
		return Result{}, errors.New("PROJECT_DESTINATION_EXISTS")
	} else if !errors.Is(err, fs.ErrNotExist) {
		return Result{}, errors.New("PROJECT_DESTINATION_INVALID")
	}
	staging, err := os.MkdirTemp(parent, "."+filepath.Base(root)+".create-")
	if err != nil {
		return Result{}, errors.New("PROJECT_PARENT_NOT_WRITABLE")
	}
	published := false
	defer func() {
		if !published {
			// This path came from MkdirTemp above, so cleanup never reaches caller
			// content. Do not silently hide a leftover partial project.
			if cleanupErr := s.removeAll(staging); cleanupErr != nil && err != nil {
				err = errors.New("PROJECT_CREATE_CLEANUP_FAILED")
			}
		}
	}()
	marker := filepath.Join(staging, ".platform-installer-create")
	if err := os.WriteFile(marker, []byte("v1alpha1\n"), 0o600); err != nil {
		return Result{}, errors.New("PROJECT_CREATE_FAILED")
	}
	id, err := projectID()
	if err != nil {
		return Result{}, errors.New("PROJECT_ID_GENERATION_FAILED")
	}
	content, err := marshalManifest(id, name, source)
	if err != nil {
		return Result{}, err
	}
	projectFile := filepath.Join(staging, "project.yml")
	if err := writeSync(projectFile, content); err != nil {
		return Result{}, errors.New("PROJECT_CREATE_FAILED")
	}
	if err := os.Remove(marker); err != nil {
		return Result{}, errors.New("PROJECT_CREATE_FAILED")
	}
	if err := assertSafeAncestors(parent); err != nil {
		return Result{}, err
	}
	if _, err := os.Lstat(root); err == nil {
		return Result{}, errors.New("PROJECT_DESTINATION_EXISTS")
	} else if !errors.Is(err, fs.ErrNotExist) {
		return Result{}, errors.New("PROJECT_DESTINATION_INVALID")
	}
	if s.beforePublish != nil {
		if err := s.beforePublish(root); err != nil {
			return Result{}, err
		}
	}
	if err := s.publish(staging, root); err != nil {
		return Result{}, errors.New("PROJECT_PUBLISH_FAILED")
	}
	published = true
	return Result{Root: root, Classification: classificationEmpty, Project: &Project{ID: id, Name: name, Source: source.summary()}, Counts: Counts{}}, nil
}

func (s *Service) OpenProject(_ context.Context, root string) (Result, error) {
	root, err := existingRoot(root)
	if err != nil {
		return Result{Root: root, Classification: classificationBlocked}, err
	}
	manifest, err := readManifest(root)
	if err != nil {
		return Result{Root: root, Classification: classificationBlocked}, err
	}
	managed := manifest.Metadata.Labels[managedProjectLabel] == managedProjectMarker
	canonical, err := canonicalInputsPresent(root)
	if err != nil {
		return Result{Root: root, Classification: classificationBlocked}, err
	}
	if managed && validEmptyManifest(manifest) {
		result := Result{Root: root, Project: &Project{ID: manifest.Metadata.ID, Name: manifest.Metadata.Name, Source: CompatibilitySourceSummary{BundleDigest: manifest.ArtifactLock.Digest, CatalogDigest: manifest.CatalogLock.Digest}}, Counts: Counts{}}
		if canonical {
			result.Classification = classificationManaged
		} else {
			result.Classification = classificationEmpty
		}
		return result, nil
	}
	if managed {
		return Result{Root: root, Classification: classificationInvalid}, errors.New("MANAGED_PROJECT_INVALID")
	}
	if canonical {
		return Result{Root: root, Classification: classificationExternal}, nil
	}
	return Result{Root: root, Classification: classificationIncomplete}, errors.New("PROJECT_INPUT_INCOMPLETE")
}

func (s *Service) compatibilitySource(id string) (compatibility, error) {
	entry, ok := s.sources[id]
	if !ok || id == "" || entry.root == "" {
		return compatibility{}, errors.New("PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE")
	}
	verified, err := executionbundle.ValidateRoot(entry.root)
	if err != nil {
		return compatibility{}, errors.New("PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE")
	}
	catalog, err := readCatalog(verified)
	if err != nil || catalog.Digest != verified.Manifest.CatalogDigest {
		return compatibility{}, errors.New("PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE")
	}
	return compatibility{id: entry.id, verified: verified, catalog: catalog}, nil
}

type compatibility struct {
	id       string
	verified executionbundle.Verified
	catalog  catalog
}

func (c compatibility) summary() CompatibilitySourceSummary {
	return CompatibilitySourceSummary{ID: c.id, BundleDigest: c.verified.Digest, CatalogDigest: c.verified.Manifest.CatalogDigest, BundleVersion: c.verified.Manifest.BundleVersion}
}

type catalog struct {
	APIVersion  string                `yaml:"apiVersion"`
	Kind        string                `yaml:"kind"`
	Digest      string                `yaml:"digest"`
	Definitions map[string]definition `yaml:"definitions"`
}
type definition struct {
	Metadata struct {
		ID      string `yaml:"id"`
		Version string `yaml:"version"`
	} `yaml:"metadata"`
	Digest string `yaml:"x-definitionDigest"`
}

func readCatalog(verified executionbundle.Verified) (catalog, error) {
	var value catalog
	data, err := os.ReadFile(filepath.Join(verified.Root, "catalog", "service-catalog.yml"))
	if err != nil || yaml.Unmarshal(data, &value) != nil || value.APIVersion != "platform.installer/catalog/v1alpha1" || value.Kind != "ServiceCatalog" || value.Digest == "" || len(value.Definitions) == 0 {
		return catalog{}, errors.New("catalog invalid")
	}
	for id, definition := range value.Definitions {
		if id == "" || id != definition.Metadata.ID || definition.Metadata.Version == "" || !validDigest(definition.Digest) {
			return catalog{}, errors.New("catalog definition invalid")
		}
	}
	return value, nil
}

type manifest struct {
	APIVersion string `yaml:"apiVersion"`
	Kind       string `yaml:"kind"`
	Metadata   struct {
		ID     string            `yaml:"id"`
		Name   string            `yaml:"name"`
		Labels map[string]string `yaml:"labels"`
	} `yaml:"metadata"`
	DesiredStateContract string `yaml:"desiredStateContract"`
	CatalogLock          struct {
		APIVersion string                 `yaml:"apiVersion"`
		Digest     string                 `yaml:"digest"`
		Services   map[string]serviceLock `yaml:"services"`
	} `yaml:"catalogLock"`
	ArtifactLock struct {
		APIVersion string `yaml:"apiVersion"`
		Digest     string `yaml:"digest"`
	} `yaml:"artifactLock"`
	SafeEmptyEnvelope bool `yaml:"-"`
	HasDesiredState   bool `yaml:"-"`
}
type serviceLock struct {
	DefinitionVersion string `yaml:"definitionVersion"`
	Digest            string `yaml:"digest"`
}

func marshalManifest(id, name string, source compatibility) ([]byte, error) {
	value := manifest{APIVersion: "platform.installer/v2alpha1", Kind: "PlatformProject", DesiredStateContract: "platform.installer/project-desired-state/v2alpha1"}
	value.Metadata.ID, value.Metadata.Name = id, name
	value.Metadata.Labels = map[string]string{managedProjectLabel: managedProjectMarker}
	value.CatalogLock.APIVersion, value.CatalogLock.Digest = "platform.installer/catalog/v1alpha1", source.verified.Manifest.CatalogDigest
	value.CatalogLock.Services = make(map[string]serviceLock, len(source.catalog.Definitions))
	for id, definition := range source.catalog.Definitions {
		value.CatalogLock.Services[id] = serviceLock{DefinitionVersion: definition.Metadata.Version, Digest: definition.Digest}
	}
	value.ArtifactLock.APIVersion, value.ArtifactLock.Digest = "platform.installer/artifacts/v1alpha1", source.verified.Digest
	return yaml.Marshal(value)
}

func readManifest(root string) (manifest, error) {
	path := filepath.Join(root, "project.yml")
	info, err := os.Lstat(path)
	if err != nil || info.Mode()&os.ModeSymlink != 0 || !info.Mode().IsRegular() || info.Size() > 1024*1024 {
		return manifest{}, errors.New("PROJECT_OPEN_BLOCKED")
	}
	data, err := os.ReadFile(path)
	var value manifest
	if err != nil || yaml.Unmarshal(data, &value) != nil {
		return manifest{}, errors.New("PROJECT_OPEN_BLOCKED")
	}
	var fields map[string]yaml.Node
	if yaml.Unmarshal(data, &fields) != nil {
		return manifest{}, errors.New("PROJECT_OPEN_BLOCKED")
	}
	allowed := map[string]bool{
		"apiVersion": true, "kind": true, "metadata": true,
		"desiredStateContract": true, "catalogLock": true, "artifactLock": true,
	}
	value.SafeEmptyEnvelope = true
	for key := range fields {
		if key == "desiredState" {
			value.HasDesiredState = true
		}
		if !allowed[key] {
			value.SafeEmptyEnvelope = false
		}
	}
	return value, nil
}

func validEmptyManifest(value manifest) bool {
	if !value.SafeEmptyEnvelope || value.HasDesiredState || value.APIVersion != "platform.installer/v2alpha1" || value.Kind != "PlatformProject" || value.DesiredStateContract != "platform.installer/project-desired-state/v2alpha1" || !validProjectID(value.Metadata.ID) || value.Metadata.Name == "" || len(value.Metadata.Labels) != 1 || value.Metadata.Labels[managedProjectLabel] != managedProjectMarker || value.CatalogLock.APIVersion != "platform.installer/catalog/v1alpha1" || !validDigest(value.CatalogLock.Digest) || len(value.CatalogLock.Services) == 0 || value.ArtifactLock.APIVersion != "platform.installer/artifacts/v1alpha1" || !validDigest(value.ArtifactLock.Digest) {
		return false
	}
	for id, lock := range value.CatalogLock.Services {
		if id == "" || lock.DefinitionVersion == "" || !validDigest(lock.Digest) {
			return false
		}
	}
	return true
}

func canonicalInputsPresent(root string) (bool, error) {
	for _, name := range []string{"ansible.cfg", "inventory"} {
		info, err := os.Lstat(filepath.Join(root, name))
		if err == nil {
			if info.Mode()&os.ModeSymlink != 0 {
				return false, errors.New("PROJECT_OPEN_BLOCKED")
			}
			return true, nil
		}
		if !errors.Is(err, fs.ErrNotExist) {
			return false, errors.New("PROJECT_OPEN_BLOCKED")
		}
	}
	return false, nil
}

func createDestination(root string) (string, string, error) {
	if root == "" || !filepath.IsAbs(root) || filepath.Clean(root) != root || filepath.Base(root) == "." || filepath.Base(root) == string(filepath.Separator) {
		return "", "", errors.New("PROJECT_PATH_INVALID")
	}
	parent := filepath.Dir(root)
	info, err := os.Stat(parent)
	if err != nil || !info.IsDir() {
		return "", "", errors.New("PROJECT_PARENT_MISSING")
	}
	return root, parent, nil
}

func existingRoot(root string) (string, error) {
	if root == "" || !filepath.IsAbs(root) {
		return "", errors.New("PROJECT_OPEN_BLOCKED")
	}
	root = filepath.Clean(root)
	if err := assertSafeAncestors(root); err != nil {
		return root, err
	}
	info, err := os.Lstat(root)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return root, errors.New("PROJECT_OPEN_BLOCKED")
	}
	return root, nil
}

func assertSafeAncestors(path string) error {
	for current := filepath.Clean(path); ; current = filepath.Dir(current) {
		info, err := os.Lstat(current)
		if err != nil || info.Mode()&os.ModeSymlink != 0 || info.Mode()&os.ModeIrregular != 0 {
			return errors.New("PROJECT_PATH_UNSAFE")
		}
		parent := filepath.Dir(current)
		if parent == current {
			return nil
		}
	}
}

func projectID() (string, error) {
	value := make([]byte, 8)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return "project-" + hex.EncodeToString(value), nil
}
func validProjectID(value string) bool {
	if !strings.HasPrefix(value, "project-") || len(value) != len("project-")+16 {
		return false
	}
	_, err := hex.DecodeString(value[len("project-"):])
	return err == nil && strings.ToLower(value) == value
}
func validDigest(value string) bool {
	if !strings.HasPrefix(value, "sha256:") || len(value) != 71 {
		return false
	}
	_, err := hex.DecodeString(value[7:])
	return err == nil
}
func validName(value string) (string, error) {
	value = strings.TrimSpace(value)
	if value == "" || len(value) > 256 || !utf8.ValidString(value) {
		return "", errors.New("PROJECT_DISPLAY_NAME_INVALID")
	}
	for _, r := range value {
		if unicode.IsControl(r) {
			return "", errors.New("PROJECT_DISPLAY_NAME_INVALID")
		}
	}
	return value, nil
}
func writeSync(path string, value []byte) error {
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	if _, err := file.Write(value); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return err
	}
	return file.Close()
}

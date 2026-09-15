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
	"regexp"
	"sort"
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
	Root           string              `json:"root"`
	Classification string              `json:"classification"`
	Project        *Project            `json:"project,omitempty"`
	Counts         Counts              `json:"counts"`
	Catalog        *ProjectCatalogView `json:"catalog,omitempty"`
}

// Counts are a local presentation of an intentionally metadata-only project.
// They are never a second desired-state representation.
type Counts struct {
	Servers     int `json:"servers"`
	Deployments int `json:"deployments"`
	Runs        int `json:"runs"`
}

// ProjectCatalogView is a bounded local compatibility vocabulary derived only
// from the immutable bundle explicitly locked by project.yml. It is not an
// Ansible-resolved snapshot and it contains no service settings or runtime
// semantics.
type ProjectCatalogView struct {
	Status                string                  `json:"status"`
	ExpectedBundleDigest  string                  `json:"expectedBundleDigest"`
	ExpectedCatalogDigest string                  `json:"expectedCatalogDigest"`
	BundleVersion         string                  `json:"bundleVersion,omitempty"`
	Services              []ProjectCatalogService `json:"services,omitempty"`
	Error                 *CatalogViewError       `json:"error,omitempty"`
}

type CatalogViewError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type ProjectCatalogService struct {
	ID                string               `json:"id"`
	DefinitionVersion string               `json:"definitionVersion"`
	DisplayName       string               `json:"displayName"`
	Description       string               `json:"description,omitempty"`
	Category          string               `json:"category,omitempty"`
	UI                ProjectCatalogUI     `json:"ui"`
	EndpointConsumer  bool                 `json:"endpointConsumer"`
	EndpointProvider  bool                 `json:"endpointProvider"`
	Modes             []ProjectCatalogMode `json:"modes"`
}

type ProjectCatalogUI struct {
	Icon               string `json:"icon,omitempty"`
	Order              *int   `json:"order,omitempty"`
	DocumentationTopic string `json:"documentationTopic,omitempty"`
}
type ProjectCatalogMode struct {
	ID            string                     `json:"id"`
	DisplayName   string                     `json:"displayName"`
	Description   string                     `json:"description,omitempty"`
	PlacementKind string                     `json:"placementKind"`
	Roles         []string                   `json:"roles"`
	Guidance      ProjectCatalogModeGuidance `json:"guidance"`
}
type ProjectCatalogModeGuidance struct {
	MinParticipants int                             `json:"minParticipants"`
	MaxParticipants *int                            `json:"maxParticipants,omitempty"`
	DistinctHosts   bool                            `json:"distinctHosts"`
	RoleCardinality []ProjectCatalogRoleCardinality `json:"roleCardinality,omitempty"`
}
type ProjectCatalogRoleCardinality struct {
	Role    string `json:"role"`
	Minimum int    `json:"minimum"`
	Maximum *int   `json:"maximum,omitempty"`
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
	return Result{Root: root, Classification: classificationEmpty, Project: &Project{ID: id, Name: name, Source: source.summary()}, Counts: Counts{}, Catalog: source.catalog.view(source.verified)}, nil
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
		result := Result{Root: root, Project: &Project{ID: manifest.Metadata.ID, Name: manifest.Metadata.Name, Source: CompatibilitySourceSummary{BundleDigest: manifest.ArtifactLock.Digest, CatalogDigest: manifest.CatalogLock.Digest}}, Counts: Counts{}, Catalog: s.resolveProjectCatalog(manifest)}
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
		ID          string `yaml:"id"`
		Version     string `yaml:"version"`
		DisplayName string `yaml:"displayName"`
		Description string `yaml:"description"`
		Category    string `yaml:"category"`
		UI          struct {
			Icon               string `yaml:"icon"`
			Order              *int   `yaml:"order"`
			DocumentationTopic string `yaml:"documentationTopic"`
		} `yaml:"ui"`
	} `yaml:"metadata"`
	Digest           string                 `yaml:"x-definitionDigest"`
	Modes            map[string]catalogMode `yaml:"modes"`
	EndpointConsumer map[string]any         `yaml:"endpointConsumer"`
	EndpointProvider map[string]any         `yaml:"endpointProvider"`
}

type catalogMode struct {
	DisplayName string   `yaml:"displayName"`
	Description string   `yaml:"description"`
	MemberRoles []string `yaml:"memberRoles"`
	Placement   struct {
		HostScoped      bool                       `yaml:"hostScoped"`
		MinMembers      int                        `yaml:"minMembers"`
		MaxMembers      *int                       `yaml:"maxMembers"`
		DistinctHosts   bool                       `yaml:"distinctHosts"`
		RoleCardinality map[string]roleCardinality `yaml:"roleCardinality"`
	} `yaml:"placement"`
}

type roleCardinality struct {
	Minimum int  `yaml:"minimum"`
	Maximum *int `yaml:"maximum"`
}

var catalogIdentifierPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)

func readCatalog(verified executionbundle.Verified) (catalog, error) {
	var value catalog
	data, err := executionbundle.ReadVerifiedCatalog(verified)
	if err != nil || duplicateYAMLKeys(data) || yaml.Unmarshal(data, &value) != nil || value.APIVersion != "platform.installer/catalog/v1alpha1" || value.Kind != "ServiceCatalog" || !validDigest(value.Digest) || len(value.Definitions) == 0 || len(value.Definitions) > 4096 {
		return catalog{}, errors.New("catalog invalid")
	}
	for id, definition := range value.Definitions {
		if !catalogIdentifierPattern.MatchString(id) || id != definition.Metadata.ID || definition.Metadata.Version == "" || definition.Metadata.DisplayName == "" || len(definition.Metadata.DisplayName) > 256 || len(definition.Metadata.Description) > 4096 || len(definition.Metadata.Category) > 128 || len(definition.Metadata.UI.Icon) > 256 || len(definition.Metadata.UI.DocumentationTopic) > 256 || !validDigest(definition.Digest) || len(definition.Modes) == 0 || len(definition.Modes) > 256 || !validEndpointCapability(definition.EndpointConsumer) || !validEndpointCapability(definition.EndpointProvider) {
			return catalog{}, errors.New("catalog definition invalid")
		}
		for modeID, mode := range definition.Modes {
			if !catalogIdentifierPattern.MatchString(modeID) || mode.DisplayName == "" || len(mode.DisplayName) > 256 || len(mode.Description) > 4096 || len(mode.MemberRoles) > 128 || mode.Placement.MinMembers < 0 || (mode.Placement.MaxMembers != nil && *mode.Placement.MaxMembers < mode.Placement.MinMembers) || !validCatalogRoles(mode.MemberRoles) || !validRoleCardinality(mode.Placement.RoleCardinality) {
				return catalog{}, errors.New("catalog mode invalid")
			}
		}
	}
	return value, nil
}

func validCatalogRoles(roles []string) bool {
	seen := map[string]bool{}
	for _, role := range roles {
		if !catalogIdentifierPattern.MatchString(role) || seen[role] {
			return false
		}
		seen[role] = true
	}
	return true
}

// Endpoint capability is the published genericEndpoint marker: it is absent
// or exactly an empty object. F1 deliberately assigns no inner semantics.
func validEndpointCapability(value map[string]any) bool { return value == nil || len(value) == 0 }
func validRoleCardinality(values map[string]roleCardinality) bool {
	if len(values) > 128 {
		return false
	}
	for role, value := range values {
		if !catalogIdentifierPattern.MatchString(role) || value.Minimum < 0 || (value.Maximum != nil && *value.Maximum < value.Minimum) {
			return false
		}
	}
	return true
}
func duplicateYAMLKeys(data []byte) bool {
	var root yaml.Node
	if yaml.Unmarshal(data, &root) != nil {
		return true
	}
	var walk func(*yaml.Node) bool
	walk = func(node *yaml.Node) bool {
		if node.Kind == yaml.MappingNode {
			seen := map[string]bool{}
			for index := 0; index < len(node.Content); index += 2 {
				key := node.Content[index]
				if key.Kind != yaml.ScalarNode || seen[key.Value] {
					return true
				}
				seen[key.Value] = true
				if walk(node.Content[index+1]) {
					return true
				}
			}
			return false
		}
		for _, child := range node.Content {
			if walk(child) {
				return true
			}
		}
		return false
	}
	return walk(&root)
}

func (s *Service) resolveProjectCatalog(project manifest) *ProjectCatalogView {
	view := &ProjectCatalogView{Status: "UNAVAILABLE", ExpectedBundleDigest: project.ArtifactLock.Digest, ExpectedCatalogDigest: project.CatalogLock.Digest, Error: &CatalogViewError{Code: "CATALOG_UNAVAILABLE", Message: "Compatible catalog is unavailable"}}
	ids := make([]string, 0, len(s.sources))
	for id := range s.sources {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	exactDeclared := false
	for _, id := range ids {
		entry := s.sources[id]
		verified, err := executionbundle.ValidateRoot(entry.root)
		if err != nil {
			exactDeclared = exactDeclared || executionbundle.DeclaresManifestIdentity(entry.root, project.ArtifactLock.Digest, project.CatalogLock.Digest)
			continue
		}
		if verified.Digest != project.ArtifactLock.Digest || verified.Manifest.CatalogDigest != project.CatalogLock.Digest {
			continue
		}
		exactDeclared = true
		catalog, readErr := readCatalog(verified)
		if readErr != nil || !catalogMatchesLock(catalog, project.CatalogLock) {
			continue
		}
		return catalog.view(verified)
	}
	if exactDeclared {
		view.Status = "INCOMPATIBLE"
	}
	return view
}

func catalogMatchesLock(value catalog, lock struct {
	APIVersion string                 `yaml:"apiVersion"`
	Digest     string                 `yaml:"digest"`
	Services   map[string]serviceLock `yaml:"services"`
}) bool {
	if value.Digest != lock.Digest || len(value.Definitions) != len(lock.Services) {
		return false
	}
	for id, definition := range value.Definitions {
		locked, ok := lock.Services[id]
		if !ok || definition.Metadata.Version != locked.DefinitionVersion || definition.Digest != locked.Digest {
			return false
		}
	}
	return true
}

func (value catalog) view(verified executionbundle.Verified) *ProjectCatalogView {
	services := make([]ProjectCatalogService, 0, len(value.Definitions))
	for id, definition := range value.Definitions {
		modes := make([]ProjectCatalogMode, 0, len(definition.Modes))
		for modeID, mode := range definition.Modes {
			roles := append([]string(nil), mode.MemberRoles...)
			kind := "MEMBER_SCOPED"
			if mode.Placement.HostScoped {
				kind = "HOST_SCOPED"
			}
			cardinality := make([]ProjectCatalogRoleCardinality, 0, len(mode.Placement.RoleCardinality))
			for role, rule := range mode.Placement.RoleCardinality {
				cardinality = append(cardinality, ProjectCatalogRoleCardinality{Role: role, Minimum: rule.Minimum, Maximum: rule.Maximum})
			}
			sort.Slice(cardinality, func(left, right int) bool { return cardinality[left].Role < cardinality[right].Role })
			modes = append(modes, ProjectCatalogMode{ID: modeID, DisplayName: mode.DisplayName, Description: mode.Description, Roles: roles, PlacementKind: kind, Guidance: ProjectCatalogModeGuidance{MinParticipants: mode.Placement.MinMembers, MaxParticipants: mode.Placement.MaxMembers, DistinctHosts: mode.Placement.DistinctHosts, RoleCardinality: cardinality}})
		}
		sort.Slice(modes, func(left, right int) bool {
			return catalogOrderLess(nil, modes[left].DisplayName, modes[left].ID, nil, modes[right].DisplayName, modes[right].ID)
		})
		services = append(services, ProjectCatalogService{ID: id, DefinitionVersion: definition.Metadata.Version, DisplayName: definition.Metadata.DisplayName, Description: definition.Metadata.Description, Category: definition.Metadata.Category, UI: ProjectCatalogUI{Icon: definition.Metadata.UI.Icon, Order: definition.Metadata.UI.Order, DocumentationTopic: definition.Metadata.UI.DocumentationTopic}, EndpointConsumer: definition.EndpointConsumer != nil, EndpointProvider: definition.EndpointProvider != nil, Modes: modes})
	}
	sort.Slice(services, func(left, right int) bool {
		return catalogOrderLess(services[left].UI.Order, services[left].DisplayName, services[left].ID, services[right].UI.Order, services[right].DisplayName, services[right].ID)
	})
	return &ProjectCatalogView{Status: "READY", ExpectedBundleDigest: verified.Digest, ExpectedCatalogDigest: verified.Manifest.CatalogDigest, BundleVersion: verified.Manifest.BundleVersion, Services: services}
}

func catalogOrderLess(leftOrder *int, leftName, leftID string, rightOrder *int, rightName, rightID string) bool {
	if leftOrder != nil || rightOrder != nil {
		if leftOrder == nil {
			return false
		}
		if rightOrder == nil {
			return true
		}
		if *leftOrder != *rightOrder {
			return *leftOrder < *rightOrder
		}
	}
	if leftName != rightName {
		return leftName < rightName
	}
	return leftID < rightID
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

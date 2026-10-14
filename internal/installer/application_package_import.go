package installer

import (
	"context"
	"encoding/json"
	"errors"
	"gopkg.in/yaml.v3"
	"io"
	"os"
	"path"
	"platform-installer/internal/projectlifecycle"
	"regexp"
	"sort"
	"strings"
)

const maxApplicationPackageFiles = 512
const maxApplicationPackageFileBytes = 1024 * 1024

var packageVersion = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`)
var packageComponent = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)
var packageEnvName = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// Fixed data-only destinations. Neither the caller nor a manifest can add
// tasks, plugins, hooks, roles from another package, or executable files.
func safeApplicationPackagePath(logical string) bool {
	if !safeExportLogicalPath(logical) {
		return false
	}
	p := strings.Split(logical, "/")
	if len(p) < 4 || (p[0] != "application-packages" && p[0] != "library-packages") || !validLibraryInputID(p[1]) || !packageVersion.MatchString(p[2]) {
		return false
	}
	for _, s := range p {
		if !packageComponent.MatchString(s) || s == "." || s == ".." || strings.HasSuffix(s, ".") || reservedExportDirectoryName(s) {
			return false
		}
	}
	kind := strings.TrimSuffix(p[0], "-packages")
	short := strings.Join(p[3:], "/")
	if short == kind+".yml" {
		return true
	}
	if kind == "library" && short == "files/.env" {
		return true
	}
	role := "roles/" + kind + "_" + p[1] + "/"
	if short == role+"defaults/main.yml" {
		return true
	}
	if !strings.HasPrefix(short, role+"templates/") && !strings.HasPrefix(short, "configuration/") && !strings.HasPrefix(short, "assets/") {
		return false
	}
	switch strings.ToLower(path.Ext(short)) {
	case ".j2", ".yml", ".yaml", ".json", ".conf", ".cfg", ".hcl", ".txt", ".properties", ".xml", ".crt", ".pem":
		return true
	}
	return false
}

func applicationPackageDocuments(root string) ([]exportRecord, error) {
	directory, err := openExportSourceDirectory(root)
	if err != nil {
		return nil, err
	}
	defer directory.close()
	result := exportObservation{}
	seen, folded := map[string]bool{}, map[string]bool{}
	for _, name := range []string{"application-packages", "library-packages"} {
		child, err := directory.openDirectory([]string{name})
		if isExportNotExist(err) {
			continue
		}
		if err != nil {
			return nil, err
		}
		err = collectExportDirectory(child, name, &result, seen, folded)
		child.close()
		if err != nil {
			return nil, err
		}
	}
	if len(result.documents) > maxApplicationPackageFiles {
		return nil, errors.New("APPLICATION_PACKAGE_LIMIT")
	}
	for _, r := range result.documents {
		if r.Size > maxApplicationPackageFileBytes {
			return nil, errors.New("APPLICATION_PACKAGE_LIMIT")
		}
	}
	return result.documents, nil
}

type applicationPackageManifest struct {
	APIVersion string            `yaml:"apiVersion"`
	Kind       string            `yaml:"kind"`
	Name       string            `yaml:"name"`
	Version    string            `yaml:"version"`
	Files      []string          `yaml:"files"`
	Render     map[string]string `yaml:"render,omitempty"`
}

func checkPackageManifest(records []exportRecord, kind, name, version string) (string, error) {
	invalid := errors.New("APPLICATION_PACKAGE_INVALID")
	prefix := kind + "-packages/" + name + "/" + version + "/"
	byPath := map[string][]byte{}
	for _, r := range records {
		byPath[strings.TrimPrefix(r.LogicalPath, prefix)] = r.content
	}
	var m applicationPackageManifest
	d := yaml.NewDecoder(strings.NewReader(string(byPath[kind+".yml"])))
	d.KnownFields(true)
	if d.Decode(&m) != nil || d.Decode(new(any)) != io.EOF || m.APIVersion != "platform.installer/application-package/v1alpha1" || m.Kind != strings.ToUpper(kind[:1])+kind[1:]+"Package" || m.Name != name || m.Version != version || len(m.Files) < 1 || len(m.Files) > maxApplicationPackageFiles-1 {
		return "", invalid
	}
	listed := map[string]bool{kind + ".yml": true}
	for _, file := range m.Files {
		if listed[strings.ToLower(file)] || !safeApplicationPackagePath(prefix+file) {
			return "", invalid
		}
		listed[strings.ToLower(file)] = true
		if _, ok := byPath[file]; !ok {
			return "", invalid
		}
	}
	if len(listed) != len(byPath) || !listed["roles/"+kind+"_"+name+"/defaults/main.yml"] {
		return "", invalid
	}
	for key, value := range m.Render {
		if key != "compose_template" && key != "agent_template" && key != "base_compose_template" && key != "base_compose_filename" && key != "base_service" {
			return "", invalid
		}
		if strings.HasSuffix(key, "template") && (!listed[strings.ToLower(value)] || !strings.HasSuffix(value, ".j2")) {
			return "", invalid
		}
	}
	// Identity/default namespace is checked locally; resolution and semantic
	// schema validation remain optional target-free Core Project Verify.
	var defaults map[string]any
	if yaml.Unmarshal(byPath["roles/"+kind+"_"+name+"/defaults/main.yml"], &defaults) != nil || len(defaults) != 1 {
		return "", invalid
	}
	definition := asMap(defaults["platform_"+kind+"_definition"])
	if definition["name"] != name || definition["version"] != version || safeApplicationInput(defaults, 0) != nil {
		return "", invalid
	}
	paths := make([]string, 0, len(byPath))
	for p := range byPath {
		paths = append(paths, p)
	}
	sort.Strings(paths)
	rows := make([][]string, 0, len(paths))
	for _, p := range paths {
		content := byPath[p]
		if len(content) > maxApplicationPackageFileBytes || strings.Contains(string(content), "PRIVATE KEY-----") {
			return "", invalid
		}
		if p == "files/.env" {
			keys := map[string]bool{}
			for _, line := range strings.Split(string(content), "\n") {
				line = strings.TrimSpace(line)
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				name, _, found := strings.Cut(line, "=")
				if !found || !packageEnvName.MatchString(name) || keys[name] || name == "SERVER_ID" {
					return "", invalid
				}
				keys[name] = true
			}
		}
		rows = append(rows, []string{p, strings.TrimPrefix(digestBytes(content), "sha256:")})
	}
	data, _ := json.Marshal(rows)
	return digestBytes(data), nil
}

func validateExportPackages(records []exportRecord) error {
	groups := map[string][]exportRecord{}
	for _, r := range records {
		if strings.HasPrefix(r.LogicalPath, "application-packages/") || strings.HasPrefix(r.LogicalPath, "library-packages/") {
			p := strings.Split(r.LogicalPath, "/")
			if len(p) < 4 {
				return errors.New("APPLICATION_PACKAGE_INVALID")
			}
			key := strings.Join(p[:3], "/")
			groups[key] = append(groups[key], r)
		}
	}
	for key, files := range groups {
		p := strings.Split(key, "/")
		if _, err := checkPackageManifest(files, strings.TrimSuffix(p[0], "-packages"), p[1], p[2]); err != nil {
			return err
		}
	}
	return nil
}

// Import retains the reviewed package bytes in the existing opaque plan store
// and publishes them through the same revision-guarded/recoverable transaction.
// Existing versions are immutable: changing a package requires a new version.
func (b *Backend) PlanApplicationPackageImport(ctx context.Context, projectRoot, sourceRoot, revision, kind, name, version, expectedDigest string) (*StructuralEditPlan, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	invalid := blocked("APPLICATION_PACKAGE_INVALID", "Package metadata, paths or content are invalid", "package")
	if (kind != "application" && kind != "library") || !validLibraryInputID(name) || !packageVersion.MatchString(version) || !validSHA256(expectedDigest) {
		return blockedStructuralPlan(revision, invalid), nil
	}
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	current, err := ProjectRevision(root)
	if err != nil || current != revision {
		return blockedStructuralPlan(revision, blocked("PROJECT_CHANGED", "Project changed before package review", "project")), nil
	}
	if _, err := loadStructuralCandidate(root, projectlifecycle.ClassificationManaged); err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	source, err := openExportSourceDirectory(sourceRoot)
	if err != nil {
		return blockedStructuralPlan(revision, invalid), nil
	}
	defer source.close()
	prefix := kind + "-packages/" + name + "/" + version
	versionRoot, pathErr := safeProjectPath(root, prefix, true)
	if pathErr != nil {
		return blockedStructuralPlan(revision, pathErr), nil
	}
	if _, statErr := os.Lstat(versionRoot); !errors.Is(statErr, os.ErrNotExist) {
		return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_EXISTS", "Package version already exists", "package")), nil
	}
	observation := exportObservation{}
	if err := collectExportDirectory(source, prefix, &observation, map[string]bool{}, map[string]bool{}); err != nil || len(observation.documents) > maxApplicationPackageFiles {
		return blockedStructuralPlan(revision, invalid), nil
	}
	digest, err := checkPackageManifest(observation.documents, kind, name, version)
	if err != nil || digest != expectedDigest {
		return blockedStructuralPlan(revision, invalid), nil
	}
	existing, err := applicationPackageDocuments(root)
	if err != nil {
		return blockedStructuralPlan(revision, invalid), nil
	}
	total := observation.total
	for _, record := range existing {
		total += record.Size
	}
	if len(existing)+len(observation.documents) > maxApplicationPackageFiles || total > maxExportTotalBytes {
		return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_LIMIT", "Combined project package closure exceeds its limit", "package")), nil
	}
	documents := make([]storedDocument, 0, len(observation.documents))
	for _, r := range observation.documents {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		destination, err := safeProjectPath(root, r.LogicalPath, true)
		if err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
		if _, statErr := os.Lstat(destination); !errors.Is(statErr, os.ErrNotExist) {
			return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_EXISTS", "Package version already exists", "package")), nil
		}
		documents = append(documents, storedDocument{LogicalPath: r.LogicalPath, After: r.content, Existed: false})
	}
	if latest, err := ProjectRevision(root); err != nil || latest != revision {
		return blockedStructuralPlan(revision, blocked("PROJECT_CHANGED", "Project changed during package review", "project")), nil
	}
	return b.storeStructuralPlan(root, revision, []SemanticChange{{Operation: "ImportApplicationPackage", EntityID: name + "@" + version, SafeSummary: "Import reviewed data-only package"}}, documents)
}

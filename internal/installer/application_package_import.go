package installer

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"gopkg.in/yaml.v3"
	"io"
	"platform-installer/internal/projectlifecycle"
	"regexp"
	"sort"
	"strings"
)

const maxApplicationPackageFiles = 512

// Package assets may consume the existing aggregate project budget. There is
// no separate per-file ceiling for declared configuration archives.
const maxApplicationPackageFileBytes = 64 * 1024 * 1024

var packageVersion = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`)
var packageComponent = regexp.MustCompile(`^[A-Za-z0-9_.-]+$`)
var packageEnvName = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// Fixed data-only destinations. Neither the caller nor a manifest can add
// tasks, plugins, hooks or roles from another package. JARs are application
// inputs; they are never executed on the controller.
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
	return true
}

// ApplicationPackagePathAllowed exposes the existing data-only package path
// contract to the guarded project transport; it does not authorize execution.
func ApplicationPackagePathAllowed(logical string) bool {
	return safeApplicationPackagePath(logical)
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
	Scripts    []map[string]any  `yaml:"scripts,omitempty"`
}

func packageImportError(path, reason string) *writerError {
	return blocked("APPLICATION_PACKAGE_INVALID", "Пакет «"+path+"»: "+reason, path)
}

func checkPackageManifest(records []exportRecord, kind, name, version string) (string, error) {
	prefix := kind + "-packages/" + name + "/" + version + "/"
	byPath := map[string][]byte{}
	for _, r := range records {
		byPath[strings.TrimPrefix(r.LogicalPath, prefix)] = r.content
	}
	var m applicationPackageManifest
	if _, ok := byPath[kind+".yml"]; !ok {
		return "", packageImportError(prefix+kind+".yml", "Не найден файл описания пакета.")
	}
	d := yaml.NewDecoder(strings.NewReader(string(byPath[kind+".yml"])))
	d.KnownFields(true)
	if d.Decode(&m) != nil {
		return "", packageImportError(prefix+kind+".yml", "Описание пакета не соответствует формату манифеста.")
	}
	if d.Decode(new(any)) != io.EOF {
		return "", packageImportError(prefix+kind+".yml", "Ожидается один YAML-документ описания пакета.")
	}
	if m.APIVersion != "platform.installer/application-package/v1alpha1" && m.APIVersion != "platform.installer/application-package/v1alpha2" && m.APIVersion != "platform.installer/application-package/v1alpha3" && m.APIVersion != "platform.installer/application-package/v1alpha4" {
		return "", packageImportError(prefix+kind+".yml", "Неподдерживаемая apiVersion описания пакета.")
	}
	if m.Kind != strings.ToUpper(kind[:1])+kind[1:]+"Package" {
		return "", packageImportError(prefix+kind+".yml", "Поле kind не соответствует выбранному типу пакета.")
	}
	if m.Name != name {
		return "", packageImportError(prefix+kind+".yml", "Поле name не соответствует имени папки «"+name+"».")
	}
	if m.Version != version {
		return "", packageImportError(prefix+kind+".yml", "Поле version не соответствует папке версии «"+version+"».")
	}
	if len(m.Files) < 1 || len(m.Files) > maxApplicationPackageFiles-1 {
		return "", packageImportError(prefix+kind+".yml", "Список files должен содержать от 1 до 511 записей.")
	}
	listed := map[string]bool{kind + ".yml": true}
	declared := map[string]bool{}
	for _, file := range m.Files {
		folded := strings.ToLower(file)
		if declared[folded] {
			return "", packageImportError(prefix+file, "Повторная запись в списке files.")
		}
		declared[folded] = true
		if strings.HasSuffix(file, "/") {
			// A trailing slash is one allowlist entry for all files below it.
			// Validate the directory as a package data path; records remain files.
			if !safeApplicationPackagePath(prefix + file + "member") {
				return "", packageImportError(prefix+file, "Каталог из files не разрешён для импорта.")
			}
			for member := range byPath {
				if strings.HasPrefix(member, file) {
					listed[strings.ToLower(member)] = true
				}
			}
			continue
		}
		if !safeApplicationPackagePath(prefix + file) {
			return "", packageImportError(prefix+file, "Путь из files не разрешён для импорта.")
		}
		listed[folded] = true
		if _, ok := byPath[file]; !ok {
			return "", packageImportError(prefix+file, "Файл указан в files, но отсутствует в выбранной папке.")
		}
	}
	paths := make([]string, 0, len(byPath))
	for path := range byPath {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		if !listed[strings.ToLower(path)] {
			return "", packageImportError(prefix+path, "Файл не объявлен в списке files описания пакета.")
		}
	}
	defaultsPath := "roles/" + kind + "_" + name + "/defaults/main.yml"
	if !listed[defaultsPath] {
		return "", packageImportError(prefix+defaultsPath, "Файл defaults не объявлен в списке files.")
	}
	for key, value := range m.Render {
		if key != "compose_template" && key != "agent_template" && key != "base_compose_template" && key != "base_compose_filename" && key != "base_service" {
			return "", packageImportError(prefix+kind+".yml", "Неподдерживаемый параметр раздела render.")
		}
		if strings.HasSuffix(key, "template") {
			if !listed[strings.ToLower(value)] {
				return "", packageImportError(prefix+value, "Шаблон из render не объявлен в files.")
			}
			if !strings.HasSuffix(value, ".j2") && !(key == "agent_template" && strings.HasSuffix(value, ".hcl")) {
				return "", packageImportError(prefix+value, "Недопустимое расширение шаблона в render.")
			}
		}
	}
	// Identity/default namespace is checked locally; resolution and semantic
	// schema validation remain optional target-free Core Project Verify.
	var defaults map[string]any
	if yaml.Unmarshal(byPath["roles/"+kind+"_"+name+"/defaults/main.yml"], &defaults) != nil {
		return "", packageImportError(prefix+defaultsPath, "Некорректный YAML defaults.")
	}
	if len(defaults) != 1 {
		return "", packageImportError(prefix+defaultsPath, "В defaults ожидается единственный корневой раздел platform_"+kind+"_definition.")
	}
	definition := asMap(defaults["platform_"+kind+"_definition"])
	if definition["name"] != name {
		return "", packageImportError(prefix+defaultsPath, "Имя в defaults не соответствует описанию пакета.")
	}
	if definition["version"] != version {
		return "", packageImportError(prefix+defaultsPath, "Версия в defaults не соответствует описанию пакета.")
	}
	if safeApplicationInput(defaults, 0) != nil {
		return "", packageImportError(prefix+defaultsPath, "Структура defaults содержит недопустимые данные.")
	}
	rows := make([][]string, 0, len(paths))
	for _, p := range paths {
		content := byPath[p]
		if len(content) > maxApplicationPackageFileBytes {
			return "", packageImportError(prefix+p, "Файл превышает допустимый размер.")
		}
		if strings.Contains(string(content), "PRIVATE KEY-----") {
			return "", packageImportError(prefix+p, "Файл содержит приватный ключ; импорт запрещён.")
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
					return "", packageImportError(prefix+p, "Некорректная запись .env: требуется уникальное допустимое имя переменной; SERVER_ID задаётся автоматически.")
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
	keys := make([]string, 0, len(groups))
	for key := range groups {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		p := strings.Split(key, "/")
		if _, err := checkPackageManifest(groups[key], strings.TrimSuffix(p[0], "-packages"), p[1], p[2]); err != nil {
			return err
		}
	}
	return nil
}

// Import retains the reviewed package bytes in the existing opaque plan store
// and publishes them through the same revision-guarded/recoverable transaction.
// Existing versions may be replaced through the same reviewed, guarded transaction.
func (b *Backend) PlanApplicationPackageImport(ctx context.Context, projectRoot, sourceRoot, revision, kind, name, version, _ string) (*StructuralEditPlan, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	invalid := packageImportError("package", "Некорректные параметры импорта пакета.")
	batch := kind == "application" && name == "" && version == ""
	if (kind != "application" && kind != "library") || (!batch && !validLibraryInputID(name)) || (version != "" && !packageVersion.MatchString(version)) {
		return blockedStructuralPlan(revision, invalid), nil
	}
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	current, err := ProjectRevision(root)
	if err != nil || current != revision {
		return blockedStructuralPlan(revision, blocked("PROJECT_CHANGED", "Проект изменился перед проверкой импорта. Повторите проверку.", "project")), nil
	}
	candidate, err := loadStructuralCandidate(root, projectlifecycle.ClassificationManaged)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	source, err := openExportSourceDirectory(sourceRoot)
	if err != nil {
		return blockedStructuralPlan(revision, packageImportError("source", "Не удалось безопасно открыть выбранную папку пакета.")), nil
	}
	defer source.close()
	prefix := "application-packages"
	var manifest []byte
	if !batch {
		manifest, _, err = source.readFile([]string{kind + ".yml"}, maxApplicationPackageFileBytes)
		if err != nil {
			return blockedStructuralPlan(revision, packageImportError(kind+".yml", "Не удалось прочитать описание пакета в выбранной папке.")), nil
		}
		var metadata applicationPackageManifest
		if yaml.Unmarshal(manifest, &metadata) != nil || !packageVersion.MatchString(metadata.Version) || (version != "" && version != metadata.Version) {
			return blockedStructuralPlan(revision, packageImportError(kind+".yml", "Некорректная версия в описании пакета; ожидается версия выбранного приложения в формате X.Y.Z.")), nil
		}
		version = metadata.Version
		prefix = kind + "-packages/" + name + "/" + version
	}
	observation := exportObservation{}
	if err := collectExportDirectory(source, prefix, &observation, map[string]bool{}, map[string]bool{}); err != nil {
		if _, ok := err.(*writerError); ok {
			return blockedStructuralPlan(revision, err), nil
		}
		return blockedStructuralPlan(revision, packageImportError(prefix, "Не удалось безопасно прочитать состав пакетов.")), nil
	}
	if len(observation.documents) == 0 {
		return blockedStructuralPlan(revision, packageImportError(prefix, "В выбранной папке не найдены файлы пакетов. Ожидается структура <имя>/<версия>/application.yml.")), nil
	}
	if len(observation.documents) > maxApplicationPackageFiles {
		return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_LIMIT", "Превышен лимит импорта: 512 файлов пакетов.", prefix)), nil
	}
	// Validate the captured package, without requiring an operator-supplied SHA.
	// The manifest used to derive the destination must be the reviewed bytes.
	for _, record := range observation.documents {
		if !batch && record.LogicalPath == prefix+"/"+kind+".yml" && string(record.content) != string(manifest) {
			return blockedStructuralPlan(revision, packageImportError(record.LogicalPath, "Описание пакета изменилось во время проверки. Повторите импорт.")), nil
		}
	}
	err = validateExportPackages(observation.documents)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	existing, err := applicationPackageDocuments(root)
	if err != nil {
		if _, ok := err.(*writerError); ok {
			return blockedStructuralPlan(revision, err), nil
		}
		return blockedStructuralPlan(revision, packageImportError("project", "Не удалось проверить файлы пакетов, уже находящихся в проекте.")), nil
	}

	// Reimport replaces exactly the reviewed versions; other packages are retained.
	versions := map[string]bool{}
	incoming := map[string]exportRecord{}
	for _, record := range observation.documents {
		versions[strings.Join(strings.Split(record.LogicalPath, "/")[:3], "/")] = true
		incoming[record.LogicalPath] = record
	}
	existingByPath := map[string]exportRecord{}
	retained := []exportRecord{}
	total := observation.total
	documents := []storedDocument{}
	for _, record := range existing {
		existingByPath[record.LogicalPath] = record
		versionPath := strings.Join(strings.Split(record.LogicalPath, "/")[:3], "/")
		if !versions[versionPath] {
			retained = append(retained, record)
			total += record.Size
		} else if _, present := incoming[record.LogicalPath]; !present {
			documents = append(documents, storedDocument{LogicalPath: record.LogicalPath, Before: record.content, Existed: true, Deleted: true})
		}
	}
	if len(retained)+len(observation.documents) > maxApplicationPackageFiles {
		return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_LIMIT", "После импорта будет превышен лимит 512 файлов пакетов в проекте.", "package")), nil
	}
	if total > maxExportTotalBytes {
		return blockedStructuralPlan(revision, blocked("APPLICATION_PACKAGE_LIMIT", "После импорта будет превышен общий размер пакетов проекта: 64 МиБ.", "package")), nil
	}
	for _, record := range observation.documents {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		if _, err := safeProjectPath(root, record.LogicalPath, true); err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
		previous, existed := existingByPath[record.LogicalPath]
		if existed && bytes.Equal(previous.content, record.content) {
			continue
		}
		documents = append(documents, storedDocument{LogicalPath: record.LogicalPath, Before: previous.content, After: record.content, Existed: existed})
	}
	changes := []SemanticChange{}
	if kind == "application" {
		packages, err := managedApplicationPackages(append(retained, observation.documents...))
		if err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
		imported := map[string]bool{}
		for path := range versions {
			parts := strings.Split(path, "/")
			imported[parts[1]+"@"+parts[2]] = true
		}
		changes, err = candidate.includeImportedApplicationSlots(packages, imported)
		if err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
		managedDocuments, err := candidate.storedDocuments()
		if err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
		documents = append(documents, managedDocuments...)
	}
	if latest, err := ProjectRevision(root); err != nil || latest != revision {
		return blockedStructuralPlan(revision, blocked("PROJECT_CHANGED", "Проект изменился во время проверки импорта. Повторите проверку.", "project")), nil
	}
	entityID := name + "@" + version
	if batch {
		entityID = "application-packages"
	}
	changes = append([]SemanticChange{{Operation: "ImportApplicationPackage", EntityID: entityID, SafeSummary: "Импорт / замена пакетов приложений или библиотеки"}}, changes...)
	return b.storeStructuralPlan(root, revision, changes, documents)
}

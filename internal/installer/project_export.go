package installer

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"path"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const (
	projectExportAPIVersion   = "platform.installer/project-export/v1alpha1"
	maxExportFiles            = 4096
	maxExportDirectoryEntries = maxExportFiles
	maxExportFileBytes        = int64(4 * 1024 * 1024)
	maxExportTotalBytes       = int64(64 * 1024 * 1024)
	maxExportLogicalBytes     = 512
)

// ProjectExportDocument is bounded metadata for one portable desired-state
// document. Content is intentionally never returned across the App/Wails seam.
type ProjectExportDocument struct {
	LogicalPath string `json:"logicalPath"`
	Size        int64  `json:"size"`
	Digest      string `json:"digest"`
}

// ProjectExportPlan is an in-memory capability summary, not portable desired
// state and not a public/versioned project contract.
type ProjectExportPlan struct {
	APIVersion            string                  `json:"apiVersion"`
	Kind                  string                  `json:"kind"`
	SourceProjectRoot     string                  `json:"sourceProjectRoot"`
	SourceProjectRevision string                  `json:"sourceProjectRevision"`
	DestinationParent     string                  `json:"destinationParent"`
	DirectoryName         string                  `json:"directoryName"`
	DestinationRoot       string                  `json:"destinationRoot"`
	Documents             []ProjectExportDocument `json:"documents"`
	AggregateSize         int64                   `json:"aggregateSize"`
	ExcludedCategories    []string                `json:"excludedCategories"`
	PlanDigest            string                  `json:"planDigest"`
}

type ProjectExportResult struct {
	APIVersion            string `json:"apiVersion"`
	Kind                  string `json:"kind"`
	Status                string `json:"status"`
	DestinationRoot       string `json:"destinationRoot,omitempty"`
	SourceProjectRevision string `json:"sourceProjectRevision,omitempty"`
	DocumentCount         int    `json:"documentCount"`
	AggregateSize         int64  `json:"aggregateSize"`
	ErrorCode             string `json:"errorCode,omitempty"`
}

// ProjectExport retains the two opened filesystem authorities for one preview
// and exactly one commit attempt. It must be closed when the App invalidates
// the preview or shuts down.
type ProjectExport struct {
	source           *exportDirectory
	destination      *exportDirectory
	sourceIdentity   exportIdentity
	destIdentity     exportIdentity
	sourceDisplay    string
	destDisplay      string
	directoryName    string
	plan             ProjectExportPlan
	manifest         exportObservation
	writeObservation func(*exportDirectory, exportObservation) error
	closed           bool
}

func PlanProjectExport(sourceRoot, destinationParent, directoryName string) (*ProjectExport, ProjectExportPlan, error) {
	name, err := ValidateExportDirectoryName(directoryName)
	if err != nil {
		return nil, ProjectExportPlan{}, err
	}
	sourceDisplay, err := absoluteExportDisplayPath(sourceRoot)
	if err != nil {
		return nil, ProjectExportPlan{}, errors.New("EXPORT_SOURCE_UNSAFE")
	}
	destDisplay, err := absoluteExportDisplayPath(destinationParent)
	if err != nil {
		return nil, ProjectExportPlan{}, errors.New("EXPORT_DESTINATION_INVALID")
	}
	if rootsOverlap(sourceDisplay, filepath.Join(destDisplay, name)) {
		return nil, ProjectExportPlan{}, errors.New("EXPORT_DESTINATION_INVALID")
	}
	source, err := openExportSourceDirectory(sourceDisplay)
	if err != nil {
		return nil, ProjectExportPlan{}, errors.New("EXPORT_SOURCE_UNSAFE")
	}
	destination, err := openExportDestinationDirectory(destDisplay)
	if err != nil {
		source.close()
		return nil, ProjectExportPlan{}, errors.New("EXPORT_DESTINATION_UNSAFE")
	}
	capability := &ProjectExport{source: source, destination: destination, sourceIdentity: source.identity(), destIdentity: destination.identity(), sourceDisplay: sourceDisplay, destDisplay: destDisplay, directoryName: name}
	observation, err := stableExportObservation(source)
	if err != nil {
		capability.Close()
		return nil, ProjectExportPlan{}, errors.New(exportErrorCode(err, "EXPORT_SOURCE_UNSAFE"))
	}
	if exists, existErr := destination.exists(name); existErr != nil || exists {
		capability.Close()
		if existErr != nil {
			return nil, ProjectExportPlan{}, errors.New("EXPORT_DESTINATION_UNSAFE")
		}
		return nil, ProjectExportPlan{}, errors.New("EXPORT_DESTINATION_EXISTS")
	}
	output, err := namedExportObservation(observation, name)
	if err != nil {
		capability.Close()
		return nil, ProjectExportPlan{}, err
	}
	plan := projectExportPlan(sourceDisplay, destDisplay, name, capability.sourceIdentity, capability.destIdentity, output, observation.revision)
	// The capability retains only integrity metadata between preview and
	// commit. Exact bytes are re-read through the held source authority during
	// Commit, after the source has been proven unchanged.
	capability.plan, capability.manifest = plan, exportObservationMetadata(observation)
	return capability, cloneProjectExportPlan(plan), nil
}

func (export *ProjectExport) Plan() ProjectExportPlan { return cloneProjectExportPlan(export.plan) }

func (export *ProjectExport) Close() {
	if export == nil || export.closed {
		return
	}
	export.closed = true
	if export.source != nil {
		export.source.close()
	}
	if export.destination != nil {
		export.destination.close()
	}
}

func (export *ProjectExport) Commit(planDigest string) (result ProjectExportResult) {
	result = ProjectExportResult{APIVersion: projectExportAPIVersion, Kind: "ProjectExportResult", Status: "FAILED", ErrorCode: "EXPORT_PLAN_STALE"}
	if export == nil || export.closed || planDigest == "" || planDigest != export.plan.PlanDigest {
		return result
	}
	defer export.Close()
	if export.source.identity() != export.sourceIdentity || export.destination.identity() != export.destIdentity {
		result.ErrorCode = "PROJECT_CHANGED"
		return result
	}
	observation, err := stableExportObservation(export.source)
	if err != nil {
		result.ErrorCode = exportErrorCode(err, "PROJECT_CHANGED")
		return result
	}
	if !sameExportObservation(observation, export.manifest) {
		result.ErrorCode = "EXPORT_PLAN_STALE"
		return result
	}
	output, err := namedExportObservation(observation, export.directoryName)
	if err != nil {
		result.ErrorCode = exportErrorCode(err, "EXPORT_SOURCE_UNSAFE")
		return result
	}
	if exists, existErr := export.destination.exists(export.directoryName); existErr != nil || exists {
		if existErr != nil {
			result.ErrorCode = "EXPORT_DESTINATION_UNSAFE"
		} else {
			result.ErrorCode = "EXPORT_DESTINATION_EXISTS"
		}
		return result
	}
	staging, stagingName, err := export.destination.createStaging(export.directoryName)
	if err != nil {
		result.ErrorCode = "EXPORT_WRITE_FAILED"
		return result
	}
	published := false
	defer func() {
		if !published {
			if cleanupErr := export.destination.removeOwnedTree(staging, stagingName); cleanupErr != nil {
				result.ErrorCode = exportErrorCode(cleanupErr, "EXPORT_STAGING_RETAINED")
			}
		}
		staging.close()
	}()
	write := writeExportObservation
	if export.writeObservation != nil {
		write = export.writeObservation
	}
	if err := write(staging, output); err != nil {
		result.ErrorCode = exportErrorCode(err, "EXPORT_WRITE_FAILED")
		return result
	}
	if err := verifyExportObservation(staging, output); err != nil {
		result.ErrorCode = "EXPORT_WRITE_FAILED"
		return result
	}
	finalObservation, err := stableExportObservation(export.source)
	if err != nil || !sameExportObservation(finalObservation, export.manifest) || export.source.identity() != export.sourceIdentity {
		result.ErrorCode = "PROJECT_CHANGED"
		return result
	}
	if exists, existErr := export.destination.exists(export.directoryName); existErr != nil || exists {
		if existErr != nil {
			result.ErrorCode = "EXPORT_DESTINATION_UNSAFE"
		} else {
			result.ErrorCode = "EXPORT_DESTINATION_EXISTS"
		}
		return result
	}
	if err := export.destination.publish(staging, stagingName, export.directoryName); err != nil {
		result.ErrorCode = "EXPORT_PUBLISH_FAILED"
		return result
	}
	published = true
	return ProjectExportResult{APIVersion: projectExportAPIVersion, Kind: "ProjectExportResult", Status: "EXPORTED", DestinationRoot: filepath.Join(export.destDisplay, export.directoryName), SourceProjectRevision: observation.revision, DocumentCount: len(output.documents), AggregateSize: output.total}
}

type exportRecord struct {
	ProjectExportDocument
	identity exportFileIdentity
	content  []byte
}

type exportObservation struct {
	documents []exportRecord
	revision  string
	total     int64
}

func exportObservationMetadata(observation exportObservation) exportObservation {
	metadata := exportObservation{
		documents: make([]exportRecord, len(observation.documents)),
		revision:  observation.revision,
		total:     observation.total,
	}
	for index, record := range observation.documents {
		metadata.documents[index] = exportRecord{
			ProjectExportDocument: record.ProjectExportDocument,
			identity:              record.identity,
		}
	}
	return metadata
}

func stableExportObservation(root *exportDirectory) (exportObservation, error) {
	first, err := observeExportProject(root)
	if err != nil {
		return exportObservation{}, err
	}
	second, err := observeExportProject(root)
	if err != nil {
		return exportObservation{}, err
	}
	if !sameExportObservation(first, second) {
		return exportObservation{}, errors.New("PROJECT_CHANGED")
	}
	return second, nil
}

func observeExportProject(root *exportDirectory) (exportObservation, error) {
	if root == nil || root.identity().empty() {
		return exportObservation{}, errors.New("EXPORT_SOURCE_UNSAFE")
	}
	result := exportObservation{}
	seen := map[string]bool{}
	caseFolded := map[string]bool{}
	for _, logical := range []string{"project.yml", "ansible.cfg", "inventory/hosts.yml"} {
		if err := addExportDocument(root, logical, &result, seen, caseFolded); err != nil {
			if isExportNotExist(err) {
				continue
			}
			return exportObservation{}, err
		}
	}
	for _, logical := range []string{"inventory/group_vars", "inventory/host_vars", "application-packages", "library-packages"} {
		directory, err := root.openDirectory(strings.Split(logical, "/"))
		if isExportNotExist(err) {
			continue
		}
		if err != nil {
			return exportObservation{}, errors.New("EXPORT_SOURCE_UNSAFE")
		}
		err = collectExportDirectory(directory, logical, &result, seen, caseFolded)
		directory.close()
		if err != nil {
			return exportObservation{}, err
		}
	}
	if err := validateExportPackages(result.documents); err != nil {
		return exportObservation{}, err
	}
	sort.Slice(result.documents, func(left, right int) bool {
		return result.documents[left].LogicalPath < result.documents[right].LogicalPath
	})
	result.revision = exportContentRevision(result.documents)
	return result, nil
}

func exportContentRevision(documents []exportRecord) string {
	var revisionInput []byte
	for _, document := range documents {
		if document.LogicalPath == generatedDocument {
			continue
		}
		revisionInput = append(revisionInput, []byte(document.LogicalPath)...)
		revisionInput = append(revisionInput, 0)
		revisionInput = append(revisionInput, []byte(document.Digest)...)
		revisionInput = append(revisionInput, 0)
	}
	return digestBytes(revisionInput)
}

func collectExportDirectory(directory *exportDirectory, prefix string, result *exportObservation, seen, caseFolded map[string]bool) error {
	entries, err := directory.entries()
	if err != nil {
		return errors.New("EXPORT_SOURCE_UNSAFE")
	}
	for _, entry := range entries {
		logical := prefix + "/" + entry.name
		if !safeExportLogicalPath(logical) {
			return errors.New("EXPORT_SOURCE_UNSAFE")
		}
		switch entry.kind {
		case exportEntryDirectory:
			child, openErr := directory.openDirectory([]string{entry.name})
			if openErr != nil {
				return errors.New("EXPORT_SOURCE_UNSAFE")
			}
			recurseErr := collectExportDirectory(child, logical, result, seen, caseFolded)
			child.close()
			if recurseErr != nil {
				return recurseErr
			}
		case exportEntryRegular:
			if logical == generatedDocument {
				continue
			}
			extension := strings.ToLower(path.Ext(entry.name))
			if strings.HasPrefix(logical, "application-packages/") || strings.HasPrefix(logical, "library-packages/") || extension == ".yml" || extension == ".yaml" || extension == ".json" {
				if strings.HasPrefix(logical, "application-packages/") || strings.HasPrefix(logical, "library-packages/") {
					if !safeApplicationPackagePath(logical) {
						return errors.New("APPLICATION_PACKAGE_PATH_INVALID")
					}
				}
				if err := addExportDocument(directory, entry.name, result, seen, caseFolded, logical); err != nil {
					return err
				}
			}
		default:
			return errors.New("EXPORT_SOURCE_UNSAFE")
		}
	}
	return nil
}

func addExportDocument(root *exportDirectory, logical string, result *exportObservation, seen, caseFolded map[string]bool, explicit ...string) error {
	parts := strings.Split(logical, "/")
	storedLogical := logical
	if len(explicit) == 1 {
		storedLogical = explicit[0]
	}
	if !safeExportLogicalPath(storedLogical) {
		return errors.New("EXPORT_SOURCE_UNSAFE")
	}
	if seen[storedLogical] || caseFolded[strings.ToLower(storedLogical)] {
		return errors.New("EXPORT_SOURCE_UNSAFE")
	}
	content, identity, err := root.readFile(parts, maxExportFileBytes)
	if err != nil {
		return err
	}
	if len(result.documents) >= maxExportFiles || result.total > maxExportTotalBytes-int64(len(content)) {
		return errors.New("EXPORT_LIMIT_EXCEEDED")
	}
	seen[storedLogical], caseFolded[strings.ToLower(storedLogical)] = true, true
	record := exportRecord{ProjectExportDocument: ProjectExportDocument{LogicalPath: storedLogical, Size: int64(len(content)), Digest: digestBytes(content)}, identity: identity, content: content}
	result.documents = append(result.documents, record)
	result.total += int64(len(content))
	return nil
}

func safeExportLogicalPath(logical string) bool {
	if logical == "" || len([]byte(logical)) > maxExportLogicalBytes || strings.Contains(logical, "\\") || path.Clean(logical) != logical || strings.HasPrefix(logical, "/") {
		return false
	}
	for _, part := range strings.Split(logical, "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	return true
}

func sameExportObservation(left, right exportObservation) bool {
	if left.revision != right.revision || left.total != right.total || len(left.documents) != len(right.documents) {
		return false
	}
	for index := range left.documents {
		leftDocument, rightDocument := left.documents[index], right.documents[index]
		if leftDocument.LogicalPath != rightDocument.LogicalPath || leftDocument.Size != rightDocument.Size || leftDocument.Digest != rightDocument.Digest || leftDocument.identity != rightDocument.identity {
			return false
		}
	}
	return true
}

func sameExportContentObservation(left, right exportObservation) bool {
	if left.revision != right.revision || left.total != right.total || len(left.documents) != len(right.documents) {
		return false
	}
	for index := range left.documents {
		leftDocument, rightDocument := left.documents[index], right.documents[index]
		if leftDocument.LogicalPath != rightDocument.LogicalPath || leftDocument.Size != rightDocument.Size || leftDocument.Digest != rightDocument.Digest {
			return false
		}
	}
	return true
}

func projectExportPlan(sourceRoot, destinationParent, name string, sourceIdentity, destinationIdentity exportIdentity, observation exportObservation, sourceRevision string) ProjectExportPlan {
	documents := make([]ProjectExportDocument, len(observation.documents))
	for index, document := range observation.documents {
		documents[index] = document.ProjectExportDocument
	}
	plan := ProjectExportPlan{APIVersion: projectExportAPIVersion, Kind: "ProjectExportPlan", SourceProjectRoot: sourceRoot, SourceProjectRevision: sourceRevision, DestinationParent: destinationParent, DirectoryName: name, DestinationRoot: filepath.Join(destinationParent, name), Documents: documents, AggregateSize: observation.total, ExcludedCategories: []string{"DRAFT", "RUNTIME_CREDENTIALS", "GENERATED_STATE", "RUNTIME_STATE", "PLANS", "FACTS", "LOGS", "RESULTS", "VERIFICATION_EVIDENCE"}}
	input := []byte(plan.APIVersion + "\x00" + sourceIdentity.String() + "\x00" + destinationIdentity.String() + "\x00" + plan.SourceProjectRevision + "\x00" + plan.DestinationRoot + "\x00")
	for _, document := range documents {
		input = append(input, []byte(document.LogicalPath)...)
		input = append(input, 0)
		input = append(input, []byte(document.Digest)...)
		input = append(input, 0)
		input = append(input, []byte(strconv.FormatInt(document.Size, 10))...)
		input = append(input, 0)
	}
	sum := sha256.Sum256(input)
	plan.PlanDigest = "sha256:" + hex.EncodeToString(sum[:])
	return plan
}

func cloneProjectExportPlan(plan ProjectExportPlan) ProjectExportPlan {
	plan.Documents = append([]ProjectExportDocument(nil), plan.Documents...)
	plan.ExcludedCategories = append([]string(nil), plan.ExcludedCategories...)
	return plan
}

func absoluteExportDisplayPath(value string) (string, error) {
	if value == "" {
		return "", errors.New("invalid path")
	}
	absolute, err := filepath.Abs(value)
	if err != nil {
		return "", err
	}
	return filepath.Clean(absolute), nil
}

func rootsOverlap(left, right string) bool {
	leftToRight, leftErr := filepath.Rel(left, right)
	rightToLeft, rightErr := filepath.Rel(right, left)
	leftContainsRight := leftErr == nil && (leftToRight == "." || (leftToRight != ".." && !strings.HasPrefix(leftToRight, ".."+string(filepath.Separator))))
	rightContainsLeft := rightErr == nil && (rightToLeft == "." || (rightToLeft != ".." && !strings.HasPrefix(rightToLeft, ".."+string(filepath.Separator))))
	return leftContainsRight || rightContainsLeft
}

func writeExportObservation(staging *exportDirectory, observation exportObservation) error {
	created := map[string]*exportDirectory{"": staging}
	defer func() {
		for logical, directory := range created {
			if logical != "" {
				directory.close()
			}
		}
	}()
	for _, document := range observation.documents {
		parent := path.Dir(document.LogicalPath)
		directory, err := ensureExportDirectory(staging, parent, created)
		if err != nil {
			return err
		}
		if err := directory.writeFile(path.Base(document.LogicalPath), document.content); err != nil {
			return err
		}
	}
	return nil
}

func ensureExportDirectory(root *exportDirectory, logical string, created map[string]*exportDirectory) (*exportDirectory, error) {
	if logical == "." || logical == "" {
		return root, nil
	}
	current, currentLogical := root, ""
	for _, part := range strings.Split(logical, "/") {
		if currentLogical == "" {
			currentLogical = part
		} else {
			currentLogical += "/" + part
		}
		if known, ok := created[currentLogical]; ok {
			current = known
			continue
		}
		next, err := current.createDirectory(part)
		if err != nil {
			return nil, err
		}
		created[currentLogical], current = next, next
	}
	return current, nil
}

func verifyExportObservation(staging *exportDirectory, expected exportObservation) error {
	actual, err := observeExportProject(staging)
	if err != nil || !sameExportContentObservation(actual, expected) {
		return errors.New("EXPORT_WRITE_FAILED")
	}
	return nil
}

func exportErrorCode(err error, fallback string) string {
	if err == nil {
		return fallback
	}
	for _, code := range []string{"PROJECT_CHANGED", "EXPORT_LIMIT_EXCEEDED", "EXPORT_SOURCE_UNSAFE", "EXPORT_DESTINATION_UNSAFE", "EXPORT_WRITE_FAILED", "EXPORT_STAGING_RETAINED"} {
		if err.Error() == code {
			return code
		}
	}
	return fallback
}

package executionnode

import (
	"archive/tar"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"unicode/utf8"

	"gopkg.in/yaml.v3"
	"platform-installer/internal/installer"
)

const (
	maxPreviewDependencyBytes = 2 << 20
	maxPreviewScanBytes       = 16 << 20
)

var (
	previewExpressionStart = regexp.MustCompile(`\{[{%#]`)
	previewVariable        = regexp.MustCompile(`^\s*[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\s*$`)
	previewLiteralLookup   = regexp.MustCompile(`^\s*(?:lookup|query|q)\s*\(\s*('(?:ansible\.builtin\.)?(?:file|template)'|"(?:ansible\.builtin\.)?(?:file|template)")\s*,\s*('[A-Za-z0-9_.@/-]+'|"[A-Za-z0-9_.@/-]+")\s*\)\s*$`)
)

type previewProjectFiles struct {
	all          map[string]string
	omitted      map[string]bool
	scanned      map[string][]byte
	scannedBytes int
}

func walkPreviewArchive(root string, visit func(string, os.FileInfo, *tar.Header) error) error {
	return visitProjectArchive(root, func(source string) error {
		return visitTarPath(root, source, visit)
	})
}

// Service preview evaluates infrastructure inputs. Package defaults and
// templates enter the dependency scan only if one of those inputs refers to
// them. Retained package documents still contribute to the staged revision.
func previewAssetFiles(root string) (*previewProjectFiles, error) {
	files := &previewProjectFiles{all: map[string]string{}, omitted: map[string]bool{}, scanned: map[string][]byte{}}
	var sources []string
	eligible := true
	err := walkPreviewArchive(root, func(path string, info os.FileInfo, header *tar.Header) error {
		if info.IsDir() {
			return nil
		}
		logical := header.Name
		files.all[logical] = path
		parts := strings.Split(logical, "/")
		switch {
		case len(parts) > 4 && (parts[0] == "application-packages" || parts[0] == "library-packages") && parts[3] == "assets":
			files.omitted[logical] = true
		case logical == "inventory/hosts.yml" || logical == "project.yml":
			eligible = eligible && (logical != "inventory/hosts.yml" || info.Mode()&0111 == 0)
			sources = append(sources, logical)
		case strings.HasPrefix(logical, "inventory/"):
			eligible = eligible && len(parts) >= 3 && (parts[1] == "group_vars" || parts[1] == "host_vars") && previewYAMLFile(logical)
			sources = append(sources, logical)
		}
		return nil
	})
	if err != nil || !eligible || len(files.omitted) == 0 || files.all["inventory/hosts.yml"] == "" {
		return nil, err
	}
	for _, source := range sources {
		if !files.scan(source) {
			return nil, nil
		}
	}
	if len(files.omitted) == 0 {
		return nil, nil
	}
	return files, nil
}

func previewYAMLFile(name string) bool {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".yml", ".yaml", ".json":
		return true
	}
	return false
}

func (files *previewProjectFiles) scan(logical string) bool {
	if _, ok := files.scanned[logical]; ok {
		return true
	}
	f, err := os.Open(files.all[logical])
	if err != nil {
		return false
	}
	limit := min(maxPreviewDependencyBytes, maxPreviewScanBytes-files.scannedBytes)
	data, err := io.ReadAll(io.LimitReader(f, int64(limit)+1))
	closeErr := f.Close()
	if err != nil || closeErr != nil || len(data) > limit || !utf8.Valid(data) {
		return false
	}
	files.scanned[logical] = data
	files.scannedBytes += len(data)
	if !previewYAMLFile(logical) {
		return files.scanExpressions(string(data))
	}
	var document yaml.Node
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	if decoder.Decode(&document) != nil || decoder.Decode(new(yaml.Node)) != io.EOF {
		return false
	}
	if logical == "inventory/hosts.yml" {
		if len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode {
			return false
		}
		mapping := document.Content[0]
		for i := 0; i < len(mapping.Content); i += 2 {
			if mapping.Content[i].Value == "plugin" {
				return false
			}
		}
	}
	return files.scanYAML(&document)
}

func (files *previewProjectFiles) scanYAML(node *yaml.Node) bool {
	switch node.ShortTag() {
	case "", "!!str", "!!null", "!!bool", "!!int", "!!float", "!!timestamp", "!!map", "!!seq":
	default:
		return false
	}
	if node.Kind == yaml.AliasNode || (node.Kind == yaml.ScalarNode && !files.scanExpressions(node.Value)) {
		return false
	}
	for _, child := range node.Content {
		if !files.scanYAML(child) {
			return false
		}
	}
	return true
}

func (files *previewProjectFiles) scanExpressions(text string) bool {
	for start := previewExpressionStart.FindStringIndex(text); start != nil; start = previewExpressionStart.FindStringIndex(text) {
		if text[start[0]:start[1]] != "{{" {
			return false
		}
		text = text[start[1]:]
		end := strings.Index(text, "}}")
		if end < 0 {
			return false
		}
		expression := text[:end]
		text = text[end+2:]
		if previewVariable.MatchString(expression) {
			continue
		}
		match := previewLiteralLookup.FindStringSubmatch(expression)
		if match == nil {
			return false
		}
		name := strings.ToLower(match[2][1 : len(match[2])-1])
		if name == "." || !fs.ValidPath(name) {
			return false
		}
		found := false
		for logical := range files.all {
			path := strings.ToLower(logical)
			if path == name || strings.HasSuffix(path, "/"+name) {
				found = true
				delete(files.omitted, logical)
				if !files.scan(logical) {
					return false
				}
			}
		}
		if !found {
			return false
		}
	}
	return true
}

func (files *previewProjectFiles) writeArchive(root string, writer *tar.Writer) error {
	return walkPreviewArchive(root, func(path string, info os.FileInfo, header *tar.Header) error {
		if files.omitted[header.Name] {
			return nil
		}
		if !info.IsDir() && files.all[header.Name] != path {
			return errors.New("PROJECT_REVISION_CHANGED")
		}
		if data, ok := files.scanned[header.Name]; ok {
			// Send the same bytes used to classify dependencies.
			header.Size = int64(len(data))
			if err := writer.WriteHeader(header); err != nil {
				return err
			}
			_, err := writer.Write(data)
			return err
		}
		return appendTarEntry(writer, path, info, header)
	})
}

func (t OpenSSHTransport) stageServicePreviewProject(ctx context.Context, node Node, root, runID string) (full, projected string, err error) {
	root, err = filepath.Abs(root)
	if err != nil {
		return "", "", err
	}
	files, err := previewAssetFiles(root)
	if err != nil {
		return "", "", err
	}
	if files == nil {
		return "", "", t.stageProjectWithIdentity(ctx, node, root, runID, "snapshot", previewTransferIdentity)
	}
	full, projected, err = installer.PreviewProjectRevisions(root, files.omitted)
	if err != nil {
		return "", "", err
	}
	archive, err := writeTemporaryProjectArchive(func(writer *tar.Writer) error {
		return files.writeArchive(root, writer)
	})
	if err != nil {
		return "", "", err
	}
	defer os.Remove(archive)
	file, err := os.Open(archive)
	if err != nil {
		return "", "", err
	}
	hash := sha256.New()
	_, copyErr := io.Copy(hash, file)
	if err = errors.Join(copyErr, file.Close()); err != nil {
		return "", "", err
	}
	digest := "sha256:" + hex.EncodeToString(hash.Sum(nil))
	slot := sha256.Sum256([]byte("service-preview\x00" + root))
	key := hex.EncodeToString(slot[:])
	hit, err := t.projectArchiveCache(ctx, node, key, digest, "lookup", runID, "snapshot", "")
	if err != nil {
		return "", "", &ExecutionError{Code: "PROJECT_TRANSFER_FAILED"}
	}
	if !hit {
		if _, err = t.stageProjectArchive(ctx, node, archive, runID, "snapshot", "", key, digest); err != nil {
			return "", "", err
		}
	}
	return full, projected, nil
}

package installer

import (
	"bytes"
	"errors"
	"io"
	"strings"

	"gopkg.in/yaml.v3"
)

// The only export mutation is the copied manifest's display name. Source
// records are borrowed read-only; publication validates the derived bytes.
func namedExportObservation(source exportObservation, name string) (exportObservation, error) {
	output := source
	output.documents = append([]exportRecord(nil), source.documents...)
	for i := range output.documents {
		record := &output.documents[i]
		if record.LogicalPath != "project.yml" {
			continue
		}
		content, err := exportManifestName(record.content, name)
		if err != nil {
			return exportObservation{}, err
		}
		size := int64(len(content))
		if size > maxExportFileBytes || output.total-record.Size > maxExportTotalBytes-size {
			return exportObservation{}, errors.New("EXPORT_LIMIT_EXCEEDED")
		}
		output.total += size - record.Size
		record.content, record.Size, record.Digest = content, size, digestBytes(content)
	}
	output.revision = exportContentRevision(output.documents)
	return output, nil
}

func exportManifestName(content []byte, name string) ([]byte, error) {
	invalid := errors.New("EXPORT_SOURCE_UNSAFE")
	if name == "" || strings.TrimSpace(name) != name {
		return nil, errors.New("EXPORT_DESTINATION_INVALID")
	}
	decoder := yaml.NewDecoder(bytes.NewReader(content))
	var document, extra yaml.Node
	if err := decoder.Decode(&document); err != nil || len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode || !exportRenameYAMLSafe(&document) {
		return nil, invalid
	}
	if err := decoder.Decode(&extra); err != io.EOF {
		return nil, invalid
	}
	root := document.Content[0]
	metadata, present, _ := yamlMappingValue(root, "metadata")
	if !present {
		metadata = &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
		root.Content = append(root.Content, &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: "metadata"}, metadata)
	}
	if metadata.Kind != yaml.MappingNode || metadata.Tag != "!!map" {
		return nil, invalid
	}
	value, present, _ := yamlMappingValue(metadata, "name")
	if present {
		if value.Kind != yaml.ScalarNode || value.Tag != "!!str" {
			return nil, invalid
		}
		value.Value = name
	} else {
		metadata.Content = append(metadata.Content, &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: "name"}, &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: name})
	}
	result, err := yaml.Marshal(&document)
	if err != nil {
		return nil, invalid
	}
	return result, nil
}

func exportRenameYAMLSafe(node *yaml.Node) bool {
	if node.Anchor != "" || node.Kind == yaml.AliasNode || node.Tag == "!!merge" {
		return false
	}
	if node.Kind == yaml.MappingNode {
		seen := make(map[string]bool)
		for i := 0; i < len(node.Content); i += 2 {
			key := node.Content[i]
			if key.Kind != yaml.ScalarNode || key.Tag != "!!str" || seen[key.Value] {
				return false
			}
			seen[key.Value] = true
		}
	}
	for _, child := range node.Content {
		if !exportRenameYAMLSafe(child) {
			return false
		}
	}
	return true
}

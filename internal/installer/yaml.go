package installer

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"

	"gopkg.in/yaml.v3"
)

var managedHeader = []byte("# Managed by Platform Installer.\n# This is standard Ansible YAML; formatting may be normalized.\n")

func parseManagedYAML(content []byte) (map[string]any, error) {
	if !bytes.HasPrefix(content, managedHeader) {
		return nil, blocked("WRITE_NOT_ALLOWED", "Document is not explicitly Installer-owned", "document")
	}
	var node yaml.Node
	if err := yaml.Unmarshal(content, &node); err != nil || managedYAMLDuplicateKeys(&node) {
		return nil, blocked("MANAGED_DOCUMENT_INVALID", "Installer-owned document is invalid YAML", "document")
	}
	var document map[string]any
	if err := yaml.Unmarshal(content, &document); err != nil {
		return nil, blocked("MANAGED_DOCUMENT_INVALID", "Installer-owned document is invalid YAML", "document")
	}
	if document == nil {
		document = make(map[string]any)
	}
	return document, nil
}

func managedYAMLDuplicateKeys(node *yaml.Node) bool {
	if node.Kind == yaml.MappingNode {
		seen := map[string]bool{}
		for index := 0; index < len(node.Content); index += 2 {
			key := node.Content[index]
			if key.Kind != yaml.ScalarNode || seen[key.Value] || managedYAMLDuplicateKeys(node.Content[index+1]) {
				return true
			}
			seen[key.Value] = true
		}
		return false
	}
	for _, child := range node.Content {
		if managedYAMLDuplicateKeys(child) {
			return true
		}
	}
	return false
}

func scalarNode(value any) (*yaml.Node, error) {
	switch typed := value.(type) {
	case nil:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!null", Value: "null"}, nil
	case string:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: typed}, nil
	case bool:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!bool", Value: strconv.FormatBool(typed)}, nil
	case int:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!int", Value: strconv.Itoa(typed)}, nil
	case int64:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!int", Value: strconv.FormatInt(typed, 10)}, nil
	case uint64:
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!int", Value: strconv.FormatUint(typed, 10)}, nil
	case float64:
		if math.IsNaN(typed) || math.IsInf(typed, 0) {
			return nil, blocked("INVALID_VALUE", "Non-finite numbers are not supported", "command.value")
		}
		if math.Trunc(typed) == typed && math.Abs(typed) <= 1<<53 {
			return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!int", Value: strconv.FormatFloat(typed, 'f', -1, 64)}, nil
		}
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!float", Value: strconv.FormatFloat(typed, 'g', -1, 64)}, nil
	case json.Number:
		if _, err := typed.Int64(); err == nil {
			return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!int", Value: typed.String()}, nil
		}
		if _, err := typed.Float64(); err != nil {
			return nil, blocked("INVALID_VALUE", "Numeric value is invalid", "command.value")
		}
		return &yaml.Node{Kind: yaml.ScalarNode, Tag: "!!float", Value: typed.String()}, nil
	default:
		return nil, fmt.Errorf("unsupported scalar type %T", value)
	}
}

func valueNode(value any) (*yaml.Node, error) {
	switch typed := value.(type) {
	case map[string]any:
		keys := make([]string, 0, len(typed))
		for key := range typed {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		node := &yaml.Node{Kind: yaml.MappingNode, Tag: "!!map"}
		for _, key := range keys {
			child, err := valueNode(typed[key])
			if err != nil {
				return nil, err
			}
			node.Content = append(node.Content,
				&yaml.Node{Kind: yaml.ScalarNode, Tag: "!!str", Value: key}, child)
		}
		return node, nil
	case []any:
		node := &yaml.Node{Kind: yaml.SequenceNode, Tag: "!!seq"}
		for _, item := range typed {
			child, err := valueNode(item)
			if err != nil {
				return nil, err
			}
			node.Content = append(node.Content, child)
		}
		return node, nil
	default:
		return scalarNode(value)
	}
}

func deterministicYAML(document map[string]any) ([]byte, error) {
	node, err := valueNode(document)
	if err != nil {
		return nil, err
	}
	root := &yaml.Node{Kind: yaml.DocumentNode, Content: []*yaml.Node{node}}
	var output bytes.Buffer
	encoder := yaml.NewEncoder(&output)
	encoder.SetIndent(2)
	if err := encoder.Encode(root); err != nil {
		return nil, err
	}
	if err := encoder.Close(); err != nil {
		return nil, err
	}
	return append(append([]byte(nil), managedHeader...), output.Bytes()...), nil
}

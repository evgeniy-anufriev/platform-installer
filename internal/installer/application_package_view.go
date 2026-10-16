package installer

import (
	"gopkg.in/yaml.v3"
	"strings"
)

// Reuse the handle-bound package reader and validator. Only package definition
// data is exposed: templates and arbitrary file contents never enter UI models.
func readManagedApplicationPackages(root string) (map[string]ManagedApplicationPackage, error) {
	records, err := applicationPackageDocuments(root)
	if err != nil {
		return nil, err
	}
	groups := map[string][]exportRecord{}
	for _, record := range records {
		parts := strings.Split(record.LogicalPath, "/")
		if len(parts) < 4 {
			return nil, managedReadError("Invalid application package path", "package")
		}
		key := strings.Join(parts[:3], "/")
		groups[key] = append(groups[key], record)
	}
	result := map[string]ManagedApplicationPackage{}
	for key, group := range groups {
		parts := strings.Split(key, "/")
		kind := strings.TrimSuffix(parts[0], "-packages")
		digest, err := checkPackageManifest(group, kind, parts[1], parts[2])
		if err != nil {
			return nil, managedReadError("Application package validation failed", key)
		}
		for _, r := range group {
			if r.LogicalPath != key+"/roles/"+kind+"_"+parts[1]+"/defaults/main.yml" {
				continue
			}
			var doc map[string]any
			if yaml.Unmarshal(r.content, &doc) != nil {
				return nil, managedReadError("Invalid package definition", key)
			}
			ref := parts[1] + "@" + parts[2]
			result[kind+":"+ref] = ManagedApplicationPackage{Kind: kind, Ref: ref, Digest: digest, Definition: asMap(doc["platform_"+kind+"_definition"])}
		}
	}
	return result, nil
}

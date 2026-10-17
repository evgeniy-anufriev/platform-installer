package installer

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestSDKUImportPackageBytes(t *testing.T) {
	root := filepath.Join("..", "..", "examples", "sdku")
	data, err := os.ReadFile(filepath.Join(root, "import-catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	var entries []struct{ Kind, Name, Version, Digest string }
	if err = json.Unmarshal(data, &entries); err != nil {
		t.Fatal(err)
	}
	for _, entry := range entries {
		t.Run(entry.Name, func(t *testing.T) {
			prefix := entry.Kind + "-packages/" + entry.Name + "/" + entry.Version
			var records []exportRecord
			err := filepath.WalkDir(filepath.Join(root, filepath.FromSlash(prefix)), func(path string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.IsDir() {
					return nil
				}
				content, err := os.ReadFile(path)
				if err != nil {
					return err
				}
				rel, err := filepath.Rel(root, path)
				if err != nil {
					return err
				}
				records = append(records, exportRecord{ProjectExportDocument: ProjectExportDocument{LogicalPath: filepath.ToSlash(rel)}, content: content})
				return nil
			})
			if err != nil {
				t.Fatal(err)
			}
			digest, err := checkPackageManifest(records, entry.Kind, entry.Name, entry.Version)
			if err != nil || digest != entry.Digest {
				t.Fatalf("package not importable: %v, digest match %v", err, digest == entry.Digest)
			}
		})
	}
}

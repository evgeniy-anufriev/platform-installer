package installer

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"gopkg.in/yaml.v3"
)

func TestExportNameChangesOnlyCopyAndMatchesPreview(t *testing.T) {
	parent := t.TempDir()
	source := filepath.Join(parent, "source")
	if err := os.Mkdir(source, 0o700); err != nil {
		t.Fatal(err)
	}
	original := "apiVersion: platform.installer/v2alpha1\nmetadata:\n  id: project-original\n  name: si11-path-after\nx-extension:\n  value: kept\n"
	writeExportFixture(t, source, "project.yml", original)
	export, plan, err := PlanProjectExport(source, parent, "feull-service-install")
	if err != nil {
		t.Fatal(err)
	}
	result := export.Commit(plan.PlanDigest)
	if result.Status != "EXPORTED" || result.SourceProjectRevision != plan.SourceProjectRevision || result.AggregateSize != plan.AggregateSize {
		t.Fatalf("result=%+v plan=%+v", result, plan)
	}
	before, err := os.ReadFile(filepath.Join(source, "project.yml"))
	if err != nil || !bytes.Equal(before, []byte(original)) {
		t.Fatal("source modified")
	}
	after, err := os.ReadFile(filepath.Join(result.DestinationRoot, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	var got struct {
		Metadata  struct{ ID, Name string }
		Extension map[string]string `yaml:"x-extension"`
	}
	if err := yaml.Unmarshal(after, &got); err != nil || got.Metadata.ID != "project-original" || got.Metadata.Name != "feull-service-install" || got.Extension["value"] != "kept" {
		t.Fatalf("renamed metadata/extension incorrect: %+v %v", got, err)
	}
	if len(plan.Documents) != 1 || plan.Documents[0].Digest != digestBytes(after) || plan.Documents[0].Size != int64(len(after)) || plan.AggregateSize != int64(len(after)) {
		t.Fatal("preview does not describe output")
	}
	directory, err := openExportSourceDirectory(result.DestinationRoot)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	output, err := stableExportObservation(directory)
	if err != nil || output.revision == plan.SourceProjectRevision {
		t.Fatal("source/output revision conflated")
	}
}

func TestExportManifestNameRejectsAmbiguousYAML(t *testing.T) {
	for _, content := range []string{
		"metadata: {name: old, name: second}",
		"metadata: {name: old}\n---\nx: other",
		"metadata: {name: &shared old}\nx: *shared",
		"metadata: {<<: {name: old}}",
		"metadata: {name: true}",
		"metadata: []",
		"true: value",
		"[value]",
	} {
		if _, err := exportManifestName([]byte(content), "new-name"); err == nil || err.Error() != "EXPORT_SOURCE_UNSAFE" {
			t.Fatalf("ambiguous input accepted: %v", err)
		}
	}
	for _, name := range []string{"true", "123", "a#b", "a:b", "line\nbreak"} {
		content, err := exportManifestName([]byte("metadata: {id: original, name: old}\nx: kept"), name)
		var got map[string]any
		if err != nil || yaml.Unmarshal(content, &got) != nil || got["metadata"].(map[string]any)["name"] != name || got["x"] != "kept" {
			t.Fatalf("string name roundtrip: %v", err)
		}
	}
}

func TestExportWithoutManifestDoesNotCreateOne(t *testing.T) {
	source := exportObservation{documents: []exportRecord{{ProjectExportDocument: ProjectExportDocument{LogicalPath: "ansible.cfg", Size: 3, Digest: digestBytes([]byte("cfg"))}, content: []byte("cfg")}}, total: 3}
	source.revision = exportContentRevision(source.documents)
	output, err := namedExportObservation(source, "new-name")
	if err != nil || !sameExportObservation(source, output) {
		t.Fatal("optional manifest fabricated")
	}
}

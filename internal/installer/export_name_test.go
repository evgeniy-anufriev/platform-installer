package installer

import (
	"strings"
	"testing"
)

func TestValidateExportDirectoryName(t *testing.T) {
	valid := []string{"project", "project.v2", "Проект-01", "x_y-z"}
	for _, value := range valid {
		if actual, err := ValidateExportDirectoryName(value); err != nil || actual != value {
			t.Fatalf("ValidateExportDirectoryName(%q) = %q, %v", value, actual, err)
		}
	}
	invalid := []string{"", ".", "..", "a/b", `a\\b`, "C:stream", "CON", "nul.txt", "LPT1", "COM9.cfg", "name.", "name ", "line\nname", strings.Repeat("a", 129)}
	for _, value := range invalid {
		if _, err := ValidateExportDirectoryName(value); err == nil {
			t.Fatalf("ValidateExportDirectoryName(%q) unexpectedly succeeded", value)
		}
	}
}

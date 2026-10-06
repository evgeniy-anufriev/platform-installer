package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestCLIHelpListsBundlePreparationAndAllCommands(t *testing.T) {
	var help bytes.Buffer
	writeCLIUsage(&help)
	for _, phrase := range []string{
		"validate-bundle", "publish-bundle", "import-artifact",
		"inspect", "acquire", "prepare", "probe-repository", "execution-watch",
		"build_execution_runtime_bundle.py", "--runtime-input", "--output",
		"--bundle-version", "--core-version", "desktop UI", "<project>/bundle", "explicit Bind",
	} {
		if !strings.Contains(help.String(), phrase) {
			t.Errorf("CLI help is missing %q", phrase)
		}
	}
}

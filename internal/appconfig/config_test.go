package appconfig

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeConfig(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "application.yml")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func errorCode(t *testing.T, err error) string {
	t.Helper()
	var typed *Error
	if !errors.As(err, &typed) {
		t.Fatalf("expected typed config error, got %v", err)
	}
	return typed.Code
}

func TestLoadValidApplicationConfig(t *testing.T) {
	config, err := Load(writeConfig(t, "schemaVersion: 1\nserverTypes:\n  - id: infra\n    displayName: Инфраструктура\n"))
	if err != nil || !config.HasServerType("infra") || config.HasServerType("missing") {
		t.Fatalf("config=%#v err=%v", config, err)
	}
}

func TestRepositoryApplicationConfigLoads(t *testing.T) {
	config, err := Load(filepath.Join("..", "..", "config", "application.yml"))
	if err != nil || len(config.ServerTypes) != 3 || !config.HasServerType("infra") || !config.HasServerType("app") || !config.HasServerType("db") {
		t.Fatalf("config=%#v err=%v", config, err)
	}
}

func TestResolveDevelopmentPath(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "go.mod"), []byte("module platform-installer\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "config", "application.yml")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("schemaVersion: 1\nserverTypes: [{id: infra, displayName: Infra}]\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	resolved, err := ResolveDevelopmentPath(root, "")
	if err != nil || resolved != path {
		t.Fatalf("resolved=%q err=%v", resolved, err)
	}
}

func TestResolveDevelopmentPathPrefersExecutableRelativeConfig(t *testing.T) {
	cwd := t.TempDir()
	if err := os.WriteFile(filepath.Join(cwd, "go.mod"), []byte("module platform-installer\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	for _, root := range []string{cwd, filepath.Join(t.TempDir(), "application")} {
		if err := os.MkdirAll(filepath.Join(root, "config"), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(root, "config", "application.yml"), []byte("schemaVersion: 1\nserverTypes: [{id: infra, displayName: Infra}]\n"), 0o600); err != nil {
			t.Fatal(err)
		}
		if root != cwd {
			executable := filepath.Join(root, "build", "bin", "installer.exe")
			resolved, err := ResolveDevelopmentPath(cwd, executable)
			if err != nil || resolved != filepath.Join(root, "config", "application.yml") {
				t.Fatalf("resolved=%q err=%v", resolved, err)
			}
		}
	}
}

func TestLoadRejectsNonRegularAndSymlinkConfig(t *testing.T) {
	root := t.TempDir()
	if _, err := Load(root); errorCode(t, err) != "APPLICATION_CONFIG_UNSAFE_PATH" {
		t.Fatalf("directory err=%v", err)
	}
	t.Run("file symlink", func(t *testing.T) {
		target := writeConfig(t, "schemaVersion: 1\nserverTypes: [{id: infra, displayName: Infra}]\n")
		link := filepath.Join(root, "application.yml")
		if err := os.Symlink(target, link); err != nil {
			t.Skipf("symlink creation is unavailable: %v", err)
		}
		if _, err := Load(link); errorCode(t, err) != "APPLICATION_CONFIG_UNSAFE_PATH" {
			t.Fatalf("symlink err=%v", err)
		}
	})
	t.Run("directory symlink", func(t *testing.T) {
		targetRoot := t.TempDir()
		target := filepath.Join(targetRoot, "application.yml")
		if err := os.WriteFile(target, []byte("schemaVersion: 1\nserverTypes: [{id: infra, displayName: Infra}]\n"), 0o600); err != nil {
			t.Fatal(err)
		}
		linkRoot := filepath.Join(root, "linked-config")
		if err := os.Symlink(targetRoot, linkRoot); err != nil {
			t.Skipf("directory symlink creation is unavailable: %v", err)
		}
		if _, err := Load(filepath.Join(linkRoot, "application.yml")); errorCode(t, err) != "APPLICATION_CONFIG_UNSAFE_PATH" {
			t.Fatalf("ancestor symlink err=%v", err)
		}
	})
}

func TestLoadRejectsMalformedUnsupportedDuplicateAndInvalid(t *testing.T) {
	tests := map[string]struct{ content, code string }{
		"malformed":     {"schemaVersion: [\n", "APPLICATION_CONFIG_INVALID"},
		"multiple docs": {"schemaVersion: 1\nserverTypes: [{id: infra, displayName: Infra}]\n---\nschemaVersion: 1\n", "APPLICATION_CONFIG_INVALID"},
		"unknown field": {"schemaVersion: 1\nserverTypes: []\nother: true\n", "APPLICATION_CONFIG_INVALID"},
		"version":       {"schemaVersion: 2\nserverTypes:\n  - {id: infra, displayName: Infra}\n", "APPLICATION_CONFIG_VERSION_UNSUPPORTED"},
		"empty":         {"schemaVersion: 1\nserverTypes: []\n", "APPLICATION_CONFIG_SERVER_TYPES_INVALID"},
		"duplicate":     {"schemaVersion: 1\nserverTypes:\n  - {id: infra, displayName: A}\n  - {id: infra, displayName: B}\n", "APPLICATION_CONFIG_SERVER_TYPE_DUPLICATE"},
		"grammar":       {"schemaVersion: 1\nserverTypes:\n  - {id: 'Infra type', displayName: Infra}\n", "APPLICATION_CONFIG_SERVER_TYPE_ID_INVALID"},
		"empty name":    {"schemaVersion: 1\nserverTypes:\n  - {id: infra, displayName: '   '}\n", "APPLICATION_CONFIG_SERVER_TYPE_NAME_INVALID"},
	}
	for name, test := range tests {
		t.Run(name, func(t *testing.T) {
			_, err := Load(writeConfig(t, test.content))
			if code := errorCode(t, err); code != test.code {
				t.Fatalf("code=%s want=%s", code, test.code)
			}
		})
	}
}

func TestValidateBounds(t *testing.T) {
	config := Config{SchemaVersion: 1}
	for index := 0; index < maxServerTypes+1; index++ {
		config.ServerTypes = append(config.ServerTypes, ServerType{ID: "t" + strings.Repeat("0", index%62), DisplayName: "Type"})
	}
	if code := errorCode(t, Validate(config)); code != "APPLICATION_CONFIG_SERVER_TYPES_INVALID" {
		t.Fatal(code)
	}
	if code := errorCode(t, Validate(Config{SchemaVersion: 1, ServerTypes: []ServerType{{ID: "infra", DisplayName: strings.Repeat("x", maxDisplayNameLength+1)}}})); code != "APPLICATION_CONFIG_SERVER_TYPE_NAME_INVALID" {
		t.Fatal(code)
	}
}

func TestMissingConfigIsTyped(t *testing.T) {
	_, err := Load(filepath.Join(t.TempDir(), "missing.yml"))
	if code := errorCode(t, err); code != "APPLICATION_CONFIG_NOT_FOUND" {
		t.Fatal(code)
	}
}

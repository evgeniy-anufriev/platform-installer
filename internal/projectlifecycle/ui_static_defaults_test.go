package projectlifecycle

import (
	"strings"
	"testing"
)

func TestUIStaticDefaultDisclosureIsClosed(t *testing.T) {
	minimum, maximum := 1.0, 65535.0
	minLength, maxLength, wideMaxLength := 1, 64, 4096
	cases := []struct {
		name    string
		setting ProjectCatalogSetting
		value   any
		want    bool
	}{
		{"port", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "INTEGER", Minimum: &minimum, Maximum: &maximum}, float64(8443), true},
		{"boolean", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOOLEAN"}, true, true},
		{"bounded string", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &maxLength}, "docker-user", true},
		{"enum", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "ENUM", Enum: []any{"repository", "offline"}}, "offline", true},
		{"numeric enum", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "ENUM", Enum: []any{1, 2}}, float64(2), true},
		{"unsafe numeric enum", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "ENUM", Enum: []any{int64(1<<53 + 1)}}, float64(1 << 53), false},
		{"wrong enum type", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "ENUM", Enum: []any{"1"}}, float64(1), false},
		{"newline", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &maxLength}, "line\nsecret", false},
		{"invalid UTF-8", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &maxLength}, string([]byte{0xff}), false},
		{"too many bytes", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &wideMaxLength}, strings.Repeat("é", 3000), false},
		{"secret reference", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "RUNTIME_SECRET_REFERENCE_OBJECT"}, map[string]any{"passwordSecretRef": "runtime:example"}, false},
		{"opaque", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "UNSUPPORTED"}, "value", false},
		{"advanced", ProjectCatalogSetting{Kind: "ADVANCED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &maxLength}, "value", false},
		{"oversize", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "BOUNDED_STRING", MinLength: &minLength, MaxLength: &maxLength}, "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz", false},
		{"invalid port", ProjectCatalogSetting{Kind: "MANAGED", EditorShape: "INTEGER", Minimum: &minimum, Maximum: &maximum}, float64(65536), false},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			if got := SafePresentationValue(test.setting, test.value); got != test.want {
				t.Fatalf("SafePresentationValue=%v want %v", got, test.want)
			}
		})
	}
}

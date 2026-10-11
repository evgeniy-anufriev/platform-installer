package installer

import (
	"testing"
)

func TestProjectSettingsReviewSaveAndReopen(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		{APIVersion: EditCommandAPIVersionV10, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "SetProjectSetting", Setting: "platform_data_root_directory", Value: "/data/services"},
		{APIVersion: EditCommandAPIVersionV10, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "SetProjectSetting", Setting: "platform_name_prefix", Value: "qa_platform"},
	}
	backend := f2Backend(nil)
	for _, command := range commands {
		if err := backend.validateCommand(command); err != nil {
			t.Fatal(err)
		}
	}
	result := commitStructuralForTest(t, backend, root, "EMPTY_MANAGED_PROJECT", revision, commands)
	if result.Managed.DataRootDirectory != "/data/services" || result.Managed.NamePrefix != "qa_platform" {
		t.Fatalf("saved settings: %#v", result.Managed)
	}
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if view.DataRootDirectory != "/data/services" || view.NamePrefix != "qa_platform" {
		t.Fatalf("reopened settings: %#v", view)
	}
}

func TestProjectSettingsRejectUnsafeValues(t *testing.T) {
	for _, test := range []struct{ setting, value string }{
		{"platform_data_root_directory", "/var/lib/../etc"},
		{"platform_data_root_directory", "/etc"},
		{"platform_name_prefix", "Bad-Name"},
		{"platform_name_prefix", "platform;rm"},
	} {
		if validProjectSetting(test.setting, test.value) {
			t.Fatalf("accepted %s=%q", test.setting, test.value)
		}
	}
}

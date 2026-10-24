package installer

import (
	"context"
	"os"
	"path/filepath"
	"platform-installer/internal/projectlifecycle"
	"testing"
)

func TestProvidedCredentialLiteralUsesPackageSensitivityNotItsName(t *testing.T) {
	root, backend, _ := b2Project(t)
	prefix := "library-packages/provider/1.0.0/"
	writeExportFixture(t, root, prefix+"library.yml", "apiVersion: platform.installer/application-package/v1alpha1\nkind: LibraryPackage\nname: provider\nversion: 1.0.0\nfiles: [roles/library_provider/defaults/main.yml]\n")
	writeExportFixture(t, root, prefix+"roles/library_provider/defaults/main.yml", "platform_library_definition:\n  name: provider\n  version: 1.0.0\n  provided_connections:\n    api:\n      credentials:\n        login:\n          sensitive: false\n        username:\n          sensitive: true\n")
	revision, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "provider@1.0.0", "runtimeRef": "kafka-main", "provided_connections": map[string]any{
		"api": map[string]any{"credentials": map[string]any{"login": map[string]any{"source": map[string]any{"kind": "literal", "value": "operator"}}}},
	}}
	result := commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	update := b2Command(result.NewProjectRevision, "UpdateApplicationLibraryDeployment")
	update.Entity = map[string]any{"provided_connections": map[string]any{"api": map[string]any{"credentials": map[string]any{
		"username": map[string]any{"source": map[string]any{"kind": "literal", "value": "fixture-forbidden"}},
	}}}}
	plan, _ := backend.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{update})
	if plan.Status != "BLOCKED" {
		t.Fatal("Sensitive credential accepted solely because it was named username")
	}
}

func TestProvidedConnectionsAndEnabledSaveStructurallyWithoutCore(t *testing.T) {
	root, backend, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main",
		"bindings": map[string]any{"identity": map[string]any{"providedConnectionRef": map[string]any{"libraryId": "provider", "name": "api"}}},
		"provided_connections": map[string]any{"api": map[string]any{"parameters": map[string]any{"tenant": "example", "options": []any{true, 42}},
			"credentials": map[string]any{"token": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "provider-token"}}}}}}
	result := commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	set := b2Command(result.NewProjectRevision, "SetApplicationLibraryOverride")
	set.EntityID, set.Property, set.Setting, set.Value = "gateway", "connections", "identity", map[string]any{"enabled": false}
	result = commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{set})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	overrides := asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])
	if asMap(asMap(overrides["connections"])["identity"])["enabled"] != false {
		t.Fatal("false connection override lost")
	}
	reset := b2Command(result.NewProjectRevision, "RemoveApplicationLibraryOverride")
	reset.EntityID, reset.Property, reset.Setting = "gateway", "connections", "identity"
	result = commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{reset})
	bad := b2Command(result.NewProjectRevision, "UpdateApplicationLibraryDeployment")
	bad.Entity = map[string]any{"provided_connections": map[string]any{"api": map[string]any{"credentials": map[string]any{
		"token": map[string]any{"source": map[string]any{"kind": "literal", "value": "fixture-forbidden"}}}}}}
	plan, _ := backend.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{bad})
	if plan.Status != "BLOCKED" {
		t.Fatal("plaintext provided credential accepted")
	}
}

func TestNamedTopicRolesSaveIncompleteAndResetWithoutCore(t *testing.T) {
	root, b, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "resources": map[string]any{
		"events": map[string]any{"kind": "kafka.topic", "binding": "messaging", "parameters": map[string]any{}},
	}}
	result := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	for _, resource := range []string{"events", ""} {
		set := b2Command(result.NewProjectRevision, "SetApplicationLibraryOverride")
		set.EntityID, set.Setting = "gateway", "topicBindings"
		set.Value = map[string]any{"kafka": map[string]any{"main": resource}}
		result = commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{set})
		view, err := ReadManagedProjectView(root)
		if err != nil {
			t.Fatal(err)
		}
		bindings := asMap(asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])["topicBindings"])
		if asMap(bindings["kafka"])["main"] != resource {
			t.Fatal("named role was not preserved")
		}
	}
	reset := b2Command(result.NewProjectRevision, "RemoveApplicationLibraryOverride")
	reset.EntityID, reset.Setting = "gateway", "topicBindings"
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{reset})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])["topicBindings"] != nil {
		t.Fatal("reset retained named role override")
	}
}

func TestLibraryRuntimeDirectorySaveAndDefault(t *testing.T) {
	root, b, revision := b2Project(t)
	c := b2Command(revision, "CreateApplicationLibraryDeployment")
	c.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "runtime_directory": "/data/scada/sdku"}
	r := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{c})
	v, err := ReadManagedProjectView(root)
	if err != nil || v.ApplicationLibraries["sdku"]["runtime_directory"] != "/data/scada/sdku" {
		t.Fatalf("directory save: %v", err)
	}
	c = b2Command(r.NewProjectRevision, "UpdateApplicationLibraryDeployment")
	c.Entity = map[string]any{"runtime_directory": ""}
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, r.NewProjectRevision, []EditCommand{c})
	v, err = ReadManagedProjectView(root)
	if err != nil || v.ApplicationLibraries["sdku"]["runtime_directory"] != "" {
		t.Fatalf("directory reset: %v", err)
	}
}

func TestLibraryCommonOverridesSaveAndReset(t *testing.T) {
	root, b, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	result := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	set := b2Command(result.NewProjectRevision, "SetApplicationLibraryOverride")
	set.Setting = "environment"
	set.Value = map[string]any{"COMMON": "library-instance"}
	result = commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{set})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	lib := view.ApplicationLibraries["sdku"]
	if asMap(asMap(lib["overrides"])["environment"])["COMMON"] != "library-instance" || lib["applications"] != nil {
		t.Fatal("common override written as an application slot")
	}
	reset := b2Command(result.NewProjectRevision, "RemoveApplicationLibraryOverride")
	reset.Setting = "environment"
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{reset})
	view, err = ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if asMap(view.ApplicationLibraries["sdku"]["overrides"])["environment"] != nil {
		t.Fatal("common reset retained override")
	}
	for _, setting := range []string{"image", "command", "provisioner"} {
		bad := b2Command(revision, "SetApplicationLibraryOverride")
		bad.Setting = setting
		bad.Value = "x"
		if validateApplicationEdit(bad) == nil {
			t.Fatalf("common %s accepted", setting)
		}
	}
}

func b2Project(t *testing.T) (string, *Backend, string) {
	t.Helper()
	root, revision := emptyManagedProject(t)
	b := f2Backend(f2Catalog())
	server := f2Command(revision, "CreateServer")
	server.HostID = "node1"
	server.ServerType = "infra"
	server.DesiredHostname = "node1.example.test"
	server.Address = "192.0.2.1"
	service := f2Command(revision, "CreateServiceDeployment")
	service.DeploymentID = "kafka-main"
	service.ServiceType = "kafka"
	service.Mode = "kraft"
	result := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{server, service})
	return root, b, result.NewProjectRevision
}
func b2Command(revision, op string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV11, Kind: "EditCommand", BaseProjectRevision: revision, Operation: op, DeploymentID: "sdku"}
}

func TestApplicationConfigurationTreeOverridesSaveAndReopen(t *testing.T) {
	root, backend, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	result := commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	for setting, descriptor := range map[string]map[string]any{
		"config_directories": {"source": "assets/providers", "destination": "providers", "file_mode": "0644", "directory_mode": "0755"},
		"config_archives":    {"source": "assets/themes.tar.gz", "format": "tar.gz", "destination": "themes"},
	} {
		command := b2Command(result.NewProjectRevision, "SetApplicationLibraryOverride")
		command.EntityID, command.Setting, command.Value = "gateway", setting, []any{descriptor}
		result = commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{command})
		view, err := ReadManagedProjectView(root)
		if err != nil {
			t.Fatal(err)
		}
		overrides := asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])
		values, ok := overrides[setting].([]any)
		if !ok || len(values) != 1 || asMap(values[0])["destination"] != descriptor["destination"] {
			t.Fatalf("configuration tree override not retained: %s", setting)
		}
	}
}

func TestLibraryFileOnlyResourceDefaultsSurviveUnrelatedUISave(t *testing.T) {
	root, b, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	path := filepath.Join(root, filepath.FromSlash(desiredDocument))
	document, err := parseManagedYAML(mustRead(t, path))
	if err != nil {
		t.Fatal(err)
	}
	library := asMap(asMap(asMap(document["platform_desired_state"])["applicationLibraryDeployments"])["sdku"])
	library["resource_defaults"] = map[string]any{"clickhouse": map[string]any{"tables": map[string]any{"records": map[string]any{"settings": map[string]any{"index_granularity": 4096}}}}}
	content, err := deterministicYAML(document)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, content, 0600); err != nil {
		t.Fatal(err)
	}
	revision, err = ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	update := b2Command(revision, "UpdateApplicationLibraryDeployment")
	update.Entity = map[string]any{"runtime_directory": "/data/sdk"}
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{update})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	settings := asMap(asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["resource_defaults"])["clickhouse"])["tables"])["records"])
	if asMap(settings["settings"])["index_granularity"] != 4096 {
		t.Fatal("file-only table override lost during unrelated Save")
	}
}

func TestApplicationTopicBindingSaveReopenAndReset(t *testing.T) {
	root, b, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main",
		"resources": map[string]any{"events": map[string]any{"kind": "kafka.topic", "binding": "messaging", "parameters": map[string]any{"name": "qa.events", "partitions": float64(3), "replication_factor": float64(2), "config": map[string]any{"min.insync.replicas": float64(1), "min.cleanable.dirty.ratio": 0.5}}}}}
	result := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	set := b2Command(result.NewProjectRevision, "SetApplicationLibraryOverride")
	set.EntityID, set.Setting = "gateway", "topicBindings"
	set.Value = map[string]any{"kafka": []any{"events"}}
	result = commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{set})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	bindings := asMap(asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])["topicBindings"])
	if len(asSlice(bindings["kafka"])) != 1 {
		t.Fatal("topic binding was not preserved")
	}
	parameters := asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["resources"])["events"])["parameters"])
	if parameters["partitions"] != 3 || parameters["replication_factor"] != 2 || asMap(parameters["config"])["min.insync.replicas"] != 1 || asMap(parameters["config"])["min.cleanable.dirty.ratio"] != 0.5 {
		t.Fatalf("JSON numeric types were not preserved: %v", parameters)
	}
	reset := b2Command(result.NewProjectRevision, "RemoveApplicationLibraryOverride")
	reset.EntityID, reset.Setting = "gateway", "topicBindings"
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{reset})
	view, err = ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])["topicBindings"] != nil {
		t.Fatal("reset retained topic override")
	}
}

func TestApplicationCreateGrantSaveReopenAndReset(t *testing.T) {
	root, b, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	result := commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create})
	slot := b2Command(result.NewProjectRevision, "SetApplicationLibrarySlot")
	slot.EntityID = "gateway"
	slot.Entity = map[string]any{"accounts": map[string]any{"postgres": map[string]any{"databaseAccess": []any{map[string]any{"databaseRef": "main", "privileges": []any{"CREATE", "SELECT"}}}}}}
	result = commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{slot})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	account := asMap(asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["accounts"])["postgres"])
	access := account["databaseAccess"].([]any)[0].(map[string]any)
	if rights := access["privileges"].([]any); len(rights) != 2 || rights[0] != "CREATE" || rights[1] != "SELECT" {
		t.Fatalf("saved rights changed: %v", rights)
	}
	slot.BaseProjectRevision = result.NewProjectRevision
	slot.Operation = "RemoveApplicationLibrarySlot"
	slot.Entity = nil
	commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{slot})
	view, err = ReadManagedProjectView(root)
	if err != nil || asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["accounts"]) != nil {
		t.Fatalf("account override reset failed: %v", err)
	}
}

func TestB2LibrarySaveResetReopenPreservesOpaqueFiles(t *testing.T) {
	root, b, revision := b2Project(t)
	opaque := []byte("# user opaque\ncustom: !!str unchanged\n")
	p := filepath.Join(root, "inventory/group_vars/all/opaque.yml")
	if err := os.WriteFile(p, opaque, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "bindings": map[string]any{}, "resources": map[string]any{}, "shared_secrets": map[string]any{"shared": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "shared-id"}}}}
	slot := b2Command(revision, "SetApplicationLibrarySlot")
	slot.EntityID = "gateway"
	slot.Entity = map[string]any{"accounts": map[string]any{"db": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "vault_ref", "binding": "vault", "mount": "kv", "document": "app", "field": "password"}}}}}, "credentials": map[string]any{"vault_binding": "vault"}, "overrides": map[string]any{"parameters": map[string]any{"keep": "yes", "reset": "remove", "PASSWORD": "password=synthetic-user-value", "source": "arbitrary-user-data"}}}
	place := b2Command(revision, "SetApplicationLibraryPlacement")
	place.HostID = "node1"
	place.Placement = map[string]any{}
	plan, err := b.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{create, slot, place})
	if err != nil || plan.Status != "READY" {
		t.Fatalf("plan=%+v err=%v", plan, err)
	}
	if current, _ := ProjectRevision(root); current != revision {
		t.Fatal("review wrote canonical bytes")
	}
	result := b.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" {
		t.Fatalf("%+v", result)
	}
	reset := b2Command(result.NewProjectRevision, "RemoveApplicationLibraryOverride")
	reset.EntityID = "gateway"
	reset.Property = "parameters"
	reset.Setting = "reset"
	result = commitStructuralForTest(t, b, root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{reset})
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	parameters := asMap(asMap(asMap(asMap(view.ApplicationLibraries["sdku"]["applications"])["gateway"])["overrides"])["parameters"])
	if parameters["keep"] != "yes" || parameters["reset"] != nil || view.ApplicationPlacements["node1"]["sdku"] == nil {
		t.Fatal("authored values or placement lost")
	}
	if data, _ := os.ReadFile(p); string(data) != string(opaque) {
		t.Fatal("user YAML changed")
	}
	badDelete := b2Command(result.NewProjectRevision, "DeleteApplicationLibraryDeployment")
	blockedPlan, _ := b.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{badDelete})
	if blockedPlan.Status != "BLOCKED" {
		t.Fatal("placed library deleted")
	}
}

func TestB2LibraryRejectsSecretsDerivedFieldsAndStaleCommit(t *testing.T) {
	root, b, revision := b2Project(t)
	for _, entity := range []map[string]any{{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "instanceId": "derived"}, {"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "applications": map[string]any{"gateway": map[string]any{"overrides": map[string]any{"accounts": map[string]any{"db": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "literal", "value": "synthetic"}}}}}}}}}} {
		c := b2Command(revision, "CreateApplicationLibraryDeployment")
		c.Entity = entity
		if err := validateApplicationEdit(c); err == nil {
			t.Fatal("unsafe library accepted")
		}
	}
	c := b2Command(revision, "CreateApplicationLibraryDeployment")
	c.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	plan, _ := b.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{c})
	if plan.Status != "READY" {
		t.Fatalf("%+v", plan)
	}
	if err := os.WriteFile(filepath.Join(root, "inventory/group_vars/all/concurrent.yml"), []byte("external: true\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if result := b.CommitStructuralSave(context.Background(), plan.PlanID); result.Changed {
		t.Fatal("stale library commit changed project")
	}
}

func TestB2UserParametersAndOverlappingWrites(t *testing.T) {
	_, _, revision := b2Project(t)
	c := b2Command(revision, "SetApplicationLibraryOverride")
	c.EntityID = "gateway"
	c.Property = "environment"
	c.Setting = "PASSWORD"
	c.Value = "password=synthetic"
	if err := validateApplicationEdit(c); err != nil {
		t.Fatal(err)
	}
	parent := b2Command(revision, "UpdateApplicationLibraryDeployment")
	parent.Entity = map[string]any{"applications": map[string]any{}}
	if err := validateStructuralCommandConflicts([]EditCommand{parent, c}); err == nil {
		t.Fatal("parent child overlap accepted")
	}
	slot := b2Command(revision, "SetApplicationLibrarySlot")
	slot.EntityID = "gateway"
	slot.Entity = map[string]any{"overrides": map[string]any{}}
	if err := validateStructuralCommandConflicts([]EditCommand{slot, c}); err == nil {
		t.Fatal("slot leaf overlap accepted")
	}
	other := slot
	other.EntityID = "other"
	if err := validateStructuralCommandConflicts([]EditCommand{slot, other}); err != nil {
		t.Fatal(err)
	}
	if err := safeApplicationInput(map[string]any{"environment": map[string]any{"PASSWORD": "synthetic", "source": "user-data", "credentials": map[string]any{"password": "user-data"}}}, 0); err != nil {
		t.Fatal(err)
	}
}

func TestB2TypedCredentialSourcesClosedWithoutRestrictingUserData(t *testing.T) {
	root, b, revision := b2Project(t)
	bad := []map[string]any{
		{"kind": "runtime_secret_ref", "ref": "runtime-id", "value": "synthetic-marker"},
		{"kind": "runtime_secret_ref"},
		{"kind": "runtime_secret_ref", "ref": 12},
		{"kind": "vault_ref", "binding": "vault", "mount": "kv", "document": "app", "field": "password", "value": "synthetic-marker"},
		{"kind": "vault_ref", "binding": "vault", "mount": "kv", "field": "password"},
		{"kind": "literal", "value": "synthetic-marker"},
	}
	for _, source := range bad {
		accounts := map[string]any{"db": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": source}}}}
		for _, op := range []string{"CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment", "SetApplicationLibrarySlot", "SetApplicationLibraryOverride"} {
			c := b2Command(revision, op)
			switch op {
			case "CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment":
				c.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "applications": map[string]any{"gateway": map[string]any{"accounts": accounts}}}
			case "SetApplicationLibrarySlot":
				c.EntityID = "gateway"
				c.Entity = map[string]any{"accounts": accounts}
			default:
				c.EntityID = "gateway"
				c.Setting = "accounts"
				c.Value = accounts
			}
			if err := validateApplicationEdit(c); err == nil {
				t.Fatalf("%s accepted malformed source", op)
			}
			plan, _ := b.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{c})
			if plan.Status != "BLOCKED" {
				t.Fatalf("%s plan=%s", op, plan.Status)
			}
			if current, err := ProjectRevision(root); err != nil || current != revision {
				t.Fatal("rejected descriptor changed canonical bytes")
			}
		}
		for _, op := range []string{"CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment"} {
			c := b2Command(revision, op)
			c.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "shared_secrets": map[string]any{"shared": map[string]any{"source": source}}}
			if err := validateApplicationEdit(c); err == nil {
				t.Fatal("shared secret accepted malformed source")
			}
		}
	}
	valid := []map[string]any{
		{"kind": "runtime_secret_ref", "ref": "runtime-id"},
		{"kind": "runtime_secret_ref", "ref": "{{ library_id }}-password"},
		{"kind": "vault_ref", "binding": "vault", "mount": "kv", "document": "app/credentials", "field": "password"},
		{"kind": "generated"},
		{"kind": "pki_credential", "binding": "pki", "credential": "client"},
	}
	for _, source := range valid {
		if !validApplicationCredential(map[string]any{"source": source}, false) {
			t.Fatal("valid declared source rejected")
		}
	}
	if validApplicationCredential(map[string]any{"source": valid[0], "value": "synthetic-marker"}, false) {
		t.Fatal("extra descriptor field accepted")
	}
	if !validApplicationCredential(map[string]any{"source": map[string]any{"kind": "literal", "value": "app-user"}}, true) {
		t.Fatal("literal username rejected")
	}
	free := map[string]any{"environment": map[string]any{"PASSWORD": "password=synthetic-marker", "accounts": map[string]any{"credentials": "arbitrary-user-data"}}, "parameters": map[string]any{"shared_secrets": "arbitrary-user-data"}}
	if err := safeApplicationInput(free, 0); err != nil {
		t.Fatal(err)
	}
}

func TestB2SlotCredentialShape(t *testing.T) {
	root, b, revision := b2Project(t)
	for _, credentials := range []map[string]any{
		{"password": "synthetic-marker"}, {"value": "synthetic-marker"},
		{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "runtime-id"}},
		{"vault_binding": 12}, {"vault_binding": ""}, {"vault_binding": "invalid/binding"},
	} {
		for _, op := range []string{"CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment", "SetApplicationLibrarySlot"} {
			c := b2Command(revision, op)
			slot := map[string]any{"credentials": credentials}
			if op == "SetApplicationLibrarySlot" {
				c.EntityID = "gateway"
				c.Entity = slot
			} else {
				c.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main", "applications": map[string]any{"gateway": slot}}
			}
			if err := validateApplicationEdit(c); err == nil {
				t.Fatalf("%s accepted invalid slot credentials", op)
			}
			plan, _ := b.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{c})
			if plan.Status != "BLOCKED" {
				t.Fatalf("%s did not block", op)
			}
			if current, err := ProjectRevision(root); err != nil || current != revision {
				t.Fatal("rejected slot changed canonical bytes")
			}
		}
	}
	for _, credentials := range []map[string]any{{}, {"vault_binding": "vault-main"}} {
		if !validLibrarySlot(map[string]any{"credentials": credentials}) {
			t.Fatal("valid slot credentials rejected")
		}
	}
}

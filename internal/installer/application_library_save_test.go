package installer

import (
	"context"
	"os"
	"path/filepath"
	"platform-installer/internal/projectlifecycle"
	"testing"
)

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

package installer

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestApplicationAmendExactTarget(t *testing.T) {
	store := NewEditSessionStore()
	backend := NewBackend(nil)
	session, err := store.Start("project-editor", t.TempDir(), "MANAGED_PROJECT", "sha256:"+strings.Repeat("a", 64))
	if err != nil {
		t.Fatal(err)
	}
	first := EditCommand{Operation: "SetApplicationLibraryOverride", DeploymentID: "sdku", EntityID: "gateway", Setting: "image", Value: "approved/image:1"}
	if _, err = store.Append(session.SessionID, first, backend); err != nil {
		t.Fatal(err)
	}
	changed := first
	changed.Value = "approved/image:2"
	if _, err = store.AmendConfiguration(session.SessionID, 0, first, &changed, backend); err == nil {
		t.Fatal("service amendment accepted application command")
	}
	if _, err = store.AmendApplication(session.SessionID, 0, first, &changed, backend); err != nil {
		t.Fatal(err)
	}
	if _, err = store.AmendApplication(session.SessionID, 0, first, nil, backend); err == nil {
		t.Fatal("stale expected accepted")
	}
	wrong := changed
	wrong.EntityID = "other"
	if _, err = store.AmendApplication(session.SessionID, 0, changed, &wrong, backend); err == nil {
		t.Fatal("changed target accepted")
	}
	reset := changed
	reset.Operation = "RemoveApplicationLibraryOverride"
	reset.Value = nil
	if _, err = store.AmendApplication(session.SessionID, 0, changed, &reset, backend); err != nil {
		t.Fatal(err)
	}
	if _, err = store.AmendApplication(session.SessionID, 0, reset, nil, backend); err != nil {
		t.Fatal(err)
	}
}

func TestApplicationAmendInvalidatesReviewedPlan(t *testing.T) {
	root, backend, revision := b2Project(t)
	create := b2Command(revision, "CreateApplicationLibraryDeployment")
	create.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "kafka-main"}
	committed := commitStructuralForTest(t, backend, root, "MANAGED_PROJECT", revision, []EditCommand{create})
	store := NewEditSessionStore()
	session, err := store.Start("project-editor", root, "MANAGED_PROJECT", committed.NewProjectRevision)
	if err != nil {
		t.Fatal(err)
	}
	command := EditCommand{Operation: "SetApplicationLibraryOverride", DeploymentID: "sdku", EntityID: "gateway", Setting: "image", Value: "approved/image:1"}
	if _, err = store.Append(session.SessionID, command, backend); err != nil {
		t.Fatal(err)
	}
	plan, err := store.ReviewStructural(context.Background(), backend, session.SessionID)
	if err != nil || !plan.SaveAllowed {
		t.Fatalf("%+v %v", plan, err)
	}
	changed := command
	changed.Value = "approved/image:2"
	state, err := store.AmendApplication(session.SessionID, 0, command, &changed, backend)
	if err != nil {
		t.Fatal(err)
	}
	if state.ReviewedPlanID != "" || state.Status != "EDITING" {
		t.Fatal("old preview remains current")
	}
	if _, err = store.BeginCommit(session.SessionID, plan.PlanID); err == nil {
		t.Fatal("old reviewed plan accepted")
	}
}

func TestApplicationImportSessionCannotMixEditsAndUsesNormalCommitGate(t *testing.T) {
	root, backend, revision := b2Project(t)
	source, digest := b2Package(t)
	store := NewEditSessionStore()
	session, err := store.Start("project-import", root, "MANAGED_PROJECT", revision)
	if err != nil {
		t.Fatal(err)
	}
	command := EditCommand{Operation: "SetApplicationLibraryOverride", DeploymentID: "sdku", EntityID: "gateway", Setting: "image", Value: "approved/image:1"}
	if _, err = store.Append(session.SessionID, command, backend); err != nil {
		t.Fatal(err)
	}
	if _, err = store.ReviewApplicationPackageImport(context.Background(), backend, session.SessionID, source, "application", "gateway", "1.0.0", digest); err == nil {
		t.Fatal("mixed import accepted")
	}
	if !store.Discard(session.SessionID, backend) {
		t.Fatal("discard failed")
	}
	session, err = store.Start("project-import", root, "MANAGED_PROJECT", revision)
	if err != nil {
		t.Fatal(err)
	}
	plan, err := store.ReviewApplicationPackageImport(context.Background(), backend, session.SessionID, source, "application", "gateway", "1.0.0", digest)
	if err != nil || !plan.SaveAllowed {
		t.Fatalf("%+v %v", plan, err)
	}
	if _, err = store.BeginCommit(session.SessionID, "wrong-plan"); err == nil {
		t.Fatal("foreign plan accepted")
	}
	if _, err = store.BeginCommit(session.SessionID, plan.PlanID); err != nil {
		t.Fatal(err)
	}
	result := backend.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" {
		t.Fatalf("%+v", result)
	}
	if !store.FinishCommit(session.SessionID, plan.PlanID, true) {
		t.Fatal("commit did not close session")
	}
}

func TestApplicationPackageViewUsesReviewedDefinitionNotTemplates(t *testing.T) {
	root, backend, revision := b2Project(t)
	source, digest := b2Package(t)
	plan, err := backend.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if err != nil || plan.Status != "READY" {
		t.Fatalf("%+v %v", plan, err)
	}
	// Editing the external source cannot replace the bytes already reviewed.
	if err = os.WriteFile(filepath.Join(source, "roles/application_gateway/defaults/main.yml"), []byte("invalid: replacement"), 0600); err != nil {
		t.Fatal(err)
	}
	result := backend.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" {
		t.Fatalf("%+v", result)
	}
	view, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	p := view.ApplicationPackages["application:gateway@1.0.0"]
	if p.Digest != digest || asMap(p.Definition["defaults"])["image"] != "probe" {
		t.Fatalf("unexpected projection %+v", p)
	}
	if len(p.Definition) != 3 {
		t.Fatal("unexpected definition data")
	}
	// A tampered package does not produce a trusted editor definition.
	if err = os.WriteFile(filepath.Join(root, "application-packages/gateway/1.0.0/roles/application_gateway/defaults/main.yml"), []byte("platform_application_definition: {name: wrong}"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = ReadManagedProjectView(root); err == nil {
		t.Fatal("invalid package accepted")
	}
}

func TestApplicationPackageAgentHCLRemainsDataOnly(t *testing.T) {
	for _, tc := range []struct {
		key, ext string
		valid    bool
	}{{"agent_template", ".hcl", true}, {"agent_template", ".sh", false}, {"compose_template", ".hcl", false}} {
		t.Run(tc.key+tc.ext, func(t *testing.T) {
			prefix := "application-packages/gateway/1.0.0/"
			file := "roles/application_gateway/templates/agent" + tc.ext
			manifest := "apiVersion: platform.installer/application-package/v1alpha1\nkind: ApplicationPackage\nname: gateway\nversion: 1.0.0\nfiles:\n  - roles/application_gateway/defaults/main.yml\n  - " + file + "\nrender:\n  " + tc.key + ": " + file + "\n"
			records := []exportRecord{
				{ProjectExportDocument: ProjectExportDocument{LogicalPath: prefix + "application.yml"}, content: []byte(manifest)},
				{ProjectExportDocument: ProjectExportDocument{LogicalPath: prefix + "roles/application_gateway/defaults/main.yml"}, content: []byte("platform_application_definition: {name: gateway, version: 1.0.0}\n")},
				{ProjectExportDocument: ProjectExportDocument{LogicalPath: prefix + file}, content: []byte("exit_after_auth = false\n")},
			}
			_, err := checkPackageManifest(records, "application", "gateway", "1.0.0")
			if (err == nil) != tc.valid {
				t.Fatalf("unexpected manifest validity: %v", err)
			}
		})
	}
}

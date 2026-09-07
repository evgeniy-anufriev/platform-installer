package installer

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestValidateCommandRejectsCrossOperationFieldsAndNonRuntimeRefs(t *testing.T) {
	base := EditCommand{APIVersion: EditCommandAPIVersionV2, Kind: "EditCommand", BaseProjectRevision: "sha256:" + strings.Repeat("a", 64), Operation: "CreateServer", HostID: "node1", Address: "192.0.2.1"}
	cross := base
	cross.DeploymentID = "kafka"
	if err := validateCommand(cross); err == nil {
		t.Fatal("cross-operation field accepted")
	}
	secret := EditCommand{APIVersion: EditCommandAPIVersionV2, Kind: "EditCommand", BaseProjectRevision: base.BaseProjectRevision, Operation: "SetServiceConfigurationValue", DeploymentID: "kafka", Setting: "auth", Value: map[string]any{"passwordSecretRef": "file:/tmp/secret"}}
	if err := validateCommand(secret); err == nil {
		t.Fatal("non-runtime secret reference accepted")
	}
	secret.Value = map[string]any{"passwordSecretRef": "runtime:kafka-password"}
	if err := validateCommand(secret); err != nil {
		t.Fatalf("runtime reference rejected: %v", err)
	}
}

func TestValidateV2CreateServerRejectsUnknownDecodedFields(t *testing.T) {
	baseRevision := "sha256:" + strings.Repeat("a", 64)
	content := `{"apiVersion":"platform.installer/edit-command/v1alpha2","kind":"EditCommand","baseProjectRevision":"` + baseRevision + `","operation":"CreateServer","hostId":"node1","address":"192.0.2.1","rawYaml":"unsafe"}`
	var command EditCommand
	if err := json.Unmarshal([]byte(content), &command); err != nil {
		t.Fatal(err)
	}
	if err := validateCommand(command); err == nil {
		t.Fatal("unknown decoded field was silently discarded")
	}
}

func TestValidateV2ServerCommandsPreserveOptionalFieldPresence(t *testing.T) {
	baseRevision := "sha256:" + strings.Repeat("a", 64)
	invalid := []string{
		`{"apiVersion":"platform.installer/edit-command/v1alpha2","kind":"EditCommand","baseProjectRevision":"` + baseRevision + `","operation":"CreateServer","hostId":"node1","address":"192.0.2.1","sshPort":0}`,
		`{"apiVersion":"platform.installer/edit-command/v1alpha2","kind":"EditCommand","baseProjectRevision":"` + baseRevision + `","operation":"UpdateServer","hostId":"node1","sshPort":0}`,
		`{"apiVersion":"platform.installer/edit-command/v1alpha2","kind":"EditCommand","baseProjectRevision":"` + baseRevision + `","operation":"UpdateServer","hostId":"node1","address":"192.0.2.2","clearSSHPort":false}`,
	}
	for _, content := range invalid {
		var command EditCommand
		if err := json.Unmarshal([]byte(content), &command); err != nil {
			t.Fatal(err)
		}
		if err := validateCommand(command); err == nil {
			t.Fatalf("schema-invalid optional field was accepted: %s", content)
		}
	}
}

func TestValidateV2CommandRejectsNonCanonicalBaseRevision(t *testing.T) {
	content := `{"apiVersion":"platform.installer/edit-command/v1alpha2","kind":"EditCommand","baseProjectRevision":"sha256:` + strings.Repeat("A", 64) + `","operation":"CreateServer","hostId":"node1","address":"192.0.2.1"}`
	var command EditCommand
	if err := json.Unmarshal([]byte(content), &command); err != nil {
		t.Fatal(err)
	}
	if err := validateCommand(command); err == nil {
		t.Fatal("non-canonical v1alpha2 base revision was accepted")
	}
}

func TestValidateCommandRejectsScalarSecretSettings(t *testing.T) {
	base := EditCommand{APIVersion: EditCommandAPIVersionV2, Kind: "EditCommand", BaseProjectRevision: "sha256:" + strings.Repeat("a", 64), Operation: "SetServiceConfigurationValue", DeploymentID: "kafka-main"}
	for _, command := range []EditCommand{
		func() EditCommand { value := base; value.Setting, value.Value = "password", "plaintext"; return value }(),
		func() EditCommand {
			value := base
			value.Setting, value.Value = "passwordSecretRef", "file:/tmp/secret"
			return value
		}(),
	} {
		if err := validateCommand(command); err == nil {
			t.Fatalf("scalar secret setting %q was accepted", command.Setting)
		}
	}
	allowed := base
	allowed.Setting, allowed.Value = "passwordSecretRef", "runtime:kafka-password"
	if err := validateCommand(allowed); err != nil {
		t.Fatalf("runtime secret reference rejected: %v", err)
	}
}

func createServerCommand(host, address string) EditCommand {
	return EditCommand{Operation: "CreateServer", HostID: host, Address: address}
}

func TestSessionAppendInvalidatesReviewedPlan(t *testing.T) {
	root, revision := emptyManagedProject(t)
	backend := NewBackend(&firstWriteAdapter{})
	store := NewEditSessionStore()
	session, err := store.Start("project-aaaaaaaaaaaaaaaa", root, "EMPTY_MANAGED_PROJECT", revision)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Append(session.SessionID, createServerCommand("node1", "192.0.2.10"), backend); err != nil {
		t.Fatal(err)
	}
	plan, err := store.Review(context.Background(), backend, session.SessionID)
	if err != nil || !plan.CommitAllowed {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
	if _, found := backend.plans.Get(plan.PlanID); !found {
		t.Fatal("review plan missing")
	}
	if _, err := store.Append(session.SessionID, createServerCommand("node2", "192.0.2.11"), backend); err != nil {
		t.Fatal(err)
	}
	if _, found := backend.plans.Get(plan.PlanID); found {
		t.Fatal("superseded review plan remains committable")
	}
}

func TestSessionLimitsAndExpiryDoNotMutateDraft(t *testing.T) {
	store := NewEditSessionStore()
	now := time.Date(2026, 9, 7, 0, 0, 0, 0, time.UTC)
	store.now = func() time.Time { return now }
	session, err := store.Start("project", t.TempDir(), "MANAGED_PROJECT", "sha256:"+strings.Repeat("a", 64))
	if err != nil {
		t.Fatal(err)
	}
	state := store.sessions[session.SessionID]
	state.public.EncodedBytes = maxSessionBytes
	if _, err := store.Append(session.SessionID, createServerCommand("node1", "192.0.2.10"), nil); err == nil || err.Error() != "EDIT_SESSION_LIMIT" {
		t.Fatalf("limit err=%v", err)
	}
	if state.public.CommandCount != 0 || len(state.commands) != 0 {
		t.Fatal("rejected append changed draft")
	}
	now = now.Add(defaultSessionTTL + time.Second)
	if _, err := store.Append(session.SessionID, createServerCommand("node1", "192.0.2.10"), nil); err == nil || err.Error() != "EDIT_SESSION_EXPIRED" {
		t.Fatalf("expiry err=%v", err)
	}
}

func TestSessionRejectsInvalidBaseRevision(t *testing.T) {
	store := NewEditSessionStore()
	if _, err := store.Start("project", t.TempDir(), "MANAGED_PROJECT", "sha256:not-a-digest"); err == nil {
		t.Fatal("expected invalid revision to be rejected")
	}
}

package installer

import (
	"context"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/projectlifecycle"
)

func h1Catalog() *projectlifecycle.ProjectCatalogView {
	minimumPort, maximumPort := float64(1), float64(65535)
	minimumText, maximumText := 0, 32
	return &projectlifecycle.ProjectCatalogView{Status: "READY", Services: []projectlifecycle.ProjectCatalogService{{
		ID: "kafka", Modes: []projectlifecycle.ProjectCatalogMode{{ID: "kraft", PlacementKind: "MEMBER_SCOPED", Roles: []string{"broker"}}},
		ConfigurationSettings: []projectlifecycle.ProjectCatalogSetting{
			{ID: "enabled", Kind: "MANAGED", Scopes: []string{"deployment"}, EditorShape: "BOOLEAN"},
			{ID: "port", Kind: "MANAGED", Scopes: []string{"deployment", "member"}, EditorShape: "INTEGER", Minimum: &minimumPort, Maximum: &maximumPort},
			{ID: "label", Kind: "MANAGED", Scopes: []string{"deployment"}, EditorShape: "BOUNDED_STRING", MinLength: &minimumText, MaxLength: &maximumText},
			{ID: "quorumMode", Kind: "MANAGED", Scopes: []string{"deployment"}, EditorShape: "ENUM", Enum: []any{"dynamic", "static"}},
			{ID: "tlsProfile", Kind: "MANAGED", Scopes: []string{"deployment", "member"}, EditorShape: "TLS_PROFILE", ReferenceKind: "TLS_PROFILE"},
			{ID: "freeText", Kind: "MANAGED", Scopes: []string{"deployment"}, EditorShape: "UNSUPPORTED"},
			{ID: "listeners", Kind: "MANAGED", Scopes: []string{"deployment", "member"}, EditorShape: "UNSUPPORTED"},
		},
	}}}
}

func h1CatalogWithTLSProfileSetting(settingID string) *projectlifecycle.ProjectCatalogView {
	catalog := h1Catalog()
	for index := range catalog.Services[0].ConfigurationSettings {
		setting := &catalog.Services[0].ConfigurationSettings[index]
		if setting.ReferenceKind == "TLS_PROFILE" {
			setting.ID = settingID
		}
	}
	return catalog
}

func h1CatalogWithUnannotatedTLSProfileSetting() *projectlifecycle.ProjectCatalogView {
	catalog := h1Catalog()
	for index := range catalog.Services[0].ConfigurationSettings {
		setting := &catalog.Services[0].ConfigurationSettings[index]
		if setting.ID == "tlsProfile" {
			minimum, maximum := 0, 32
			setting.EditorShape, setting.ReferenceKind = "BOUNDED_STRING", ""
			setting.MinLength, setting.MaxLength = &minimum, &maximum
		}
	}
	return catalog
}

func h1Command(revision, operation string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV8, Kind: "EditCommand", BaseProjectRevision: revision, Operation: operation}
}

func h1TopologyCommands(revision string) []EditCommand {
	server := h1Command(revision, "CreateServer")
	server.HostID, server.ServerType, server.DesiredHostname, server.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
	deployment := h1Command(revision, "CreateServiceDeployment")
	deployment.DeploymentID, deployment.ServiceType, deployment.Mode = "kafka-main", "kafka", "kraft"
	placement := h1Command(revision, "ReconcileDeploymentPlacement")
	placement.DeploymentID = "kafka-main"
	placement.Members = []PlacementMember{{MemberID: "kafka-1", HostID: "node1", Roles: []string{"broker"}}}
	return []EditCommand{server, deployment, placement}
}

func TestH1V8DeploymentAndMemberConfigurationSaveReopen(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := h1TopologyCommands(revision)
	setDeployment := h1Command(revision, "SetServiceConfigurationValue")
	setDeployment.DeploymentID, setDeployment.Scope, setDeployment.Setting, setDeployment.Value = "kafka-main", "DEPLOYMENT", "port", 9092
	setMember := h1Command(revision, "SetServiceConfigurationValue")
	setMember.DeploymentID, setMember.Scope, setMember.MemberID, setMember.Setting, setMember.Value = "kafka-main", "MEMBER", "kafka-1", "port", 9093
	commands = append(commands, setDeployment, setMember)
	result := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)

	view, err := ReadManagedProjectViewWithCatalog(root, h1Catalog())
	if err != nil {
		t.Fatal(err)
	}
	if got := view.Deployments["kafka-main"].Configuration; len(got) != 1 || got[0].State != "EDITABLE" || got[0].Value != 9092 {
		t.Fatalf("deployment configuration=%#v", got)
	}
	if got := view.MemberPlacements[0].Configuration; len(got) != 1 || got[0].State != "EDITABLE" || got[0].Value != 9093 {
		t.Fatalf("member configuration=%#v", got)
	}
	withoutCatalog, err := ReadManagedProjectView(root)
	if err != nil {
		t.Fatal(err)
	}
	if got := withoutCatalog.Deployments["kafka-main"].Configuration[0]; got.State != "UNKNOWN" || got.Value != nil || !got.OverridePresent {
		t.Fatalf("catalog-free projection leaked or lost value: %#v", got)
	}
	if result.NewProjectRevision != view.ProjectRevision {
		t.Fatalf("revision mismatch")
	}
	createNode := h1Command(result.NewProjectRevision, "CreateServer")
	createNode.HostID, createNode.ServerType, createNode.DesiredHostname, createNode.Address = "node2", "infra", "node2.example.test", "192.0.2.11"
	move := h1Command(result.NewProjectRevision, "ReconcileDeploymentPlacement")
	move.DeploymentID = "kafka-main"
	move.Members = []PlacementMember{{MemberID: "kafka-1", HostID: "node2", Roles: []string{"broker"}}}
	moved := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{createNode, move})
	if len(moved.Managed.MemberPlacements) != 1 || moved.Managed.MemberPlacements[0].HostID != "node2" || len(moved.Managed.MemberPlacements[0].Configuration) != 1 {
		t.Fatalf("member move lost configuration: %#v", moved.Managed.MemberPlacements)
	}
}

func TestH1FalseZeroEmptyAndRemoveRemainDistinct(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := h1TopologyCommands(revision)
	for setting, value := range map[string]any{"enabled": false, "label": "", "port": 1} {
		command := h1Command(revision, "SetServiceConfigurationValue")
		command.DeploymentID, command.Scope, command.Setting, command.Value = "kafka-main", "DEPLOYMENT", setting, value
		commands = append(commands, command)
	}
	result := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)
	same := h1Command(result.NewProjectRevision, "SetServiceConfigurationValue")
	same.DeploymentID, same.Scope, same.Setting, same.Value = "kafka-main", "DEPLOYMENT", "label", ""
	noChange, err := f2Backend(h1Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{same})
	if err != nil || noChange.Status != "NO_CHANGE" || noChange.SaveAllowed {
		t.Fatalf("same-value plan=%#v err=%v", noChange, err)
	}
	remove := h1Command(result.NewProjectRevision, "RemoveServiceConfigurationOverride")
	remove.DeploymentID, remove.Scope, remove.Setting = "kafka-main", "DEPLOYMENT", "enabled"
	result = commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{remove})
	content := string(mustRead(t, filepath.Join(root, filepath.FromSlash(desiredDocument))))
	if strings.Contains(content, "enabled:") || !strings.Contains(content, "label: \"\"") || !strings.Contains(content, "port: 1") {
		t.Fatalf("absence/value semantics were lost:\n%s", content)
	}
	plan, err := f2Backend(h1Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{remove})
	if err != nil || plan.Status != "NO_CHANGE" || plan.SaveAllowed {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestH1RejectsUnsupportedScopeValueAndMissingMember(t *testing.T) {
	root, revision := emptyManagedProject(t)
	base := h1TopologyCommands(revision)
	result := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationEmpty, revision, base)
	tests := []struct {
		name    string
		command EditCommand
		code    string
	}{
		{"unsupported", func() EditCommand {
			c := h1Command(result.NewProjectRevision, "SetServiceConfigurationValue")
			c.DeploymentID, c.Scope, c.Setting, c.Value = "kafka-main", "DEPLOYMENT", "freeText", "unsafe"
			return c
		}(), "SETTING_UNSUPPORTED"},
		{"fractional integer", func() EditCommand {
			c := h1Command(result.NewProjectRevision, "SetServiceConfigurationValue")
			c.DeploymentID, c.Scope, c.Setting, c.Value = "kafka-main", "DEPLOYMENT", "port", 9092.5
			return c
		}(), "INVALID_VALUE"},
		{"missing member", func() EditCommand {
			c := h1Command(result.NewProjectRevision, "SetServiceConfigurationValue")
			c.DeploymentID, c.Scope, c.MemberID, c.Setting, c.Value = "kafka-main", "MEMBER", "missing", "port", 9092
			return c
		}(), "REFERENCE_NOT_FOUND"},
		{"scope", func() EditCommand {
			c := h1Command(result.NewProjectRevision, "SetServiceConfigurationValue")
			c.DeploymentID, c.Scope, c.Setting, c.Value = "kafka-main", "MEMBER", "port", 9092
			return c
		}(), "INVALID_EDIT_COMMAND"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			plan, err := f2Backend(h1Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{test.command})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != test.code {
				t.Fatalf("plan=%#v err=%v", plan, err)
			}
		})
	}
}

func TestH1PreservesUnsupportedSiblingConfiguration(t *testing.T) {
	root, revision := emptyManagedProject(t)
	result := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationEmpty, revision, h1TopologyCommands(revision))
	desiredPath := filepath.Join(root, filepath.FromSlash(desiredDocument))
	document, err := parseManagedYAML(mustRead(t, desiredPath))
	if err != nil {
		t.Fatal(err)
	}
	deployment := asMap(asMap(asMap(document["platform_desired_state"])["serviceDeployments"])["kafka-main"])
	deployment["configuration"] = map[string]any{"listeners": map[string]any{"opaque": "preserve"}}
	content, err := deterministicYAML(document)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(desiredPath, content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, err = ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	set := h1Command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Scope, set.Setting, set.Value = "kafka-main", "DEPLOYMENT", "port", 9092
	commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{set})
	after := string(mustRead(t, desiredPath))
	if !strings.Contains(after, "opaque: preserve") || !strings.Contains(after, "port: 9092") {
		t.Fatalf("unsupported sibling was lost:\n%s", after)
	}
	view, err := ReadManagedProjectViewWithCatalog(root, h1Catalog())
	if err != nil {
		t.Fatal(err)
	}
	configuration := view.Deployments["kafka-main"].Configuration
	if len(configuration) != 2 || configuration[0].Setting != "listeners" || configuration[0].State != "UNSUPPORTED" || configuration[0].Value != nil {
		t.Fatalf("projection=%#v", configuration)
	}
	_ = result
}

func TestH1TLSReferenceIntegrityCoversMemberConfiguration(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := h1TopologyCommands(revision)
	commands = append(commands,
		pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
		pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
		pkiCommand(revision, "CreateTLSProfile", "tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
	)
	set := h1Command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Scope, set.MemberID, set.Setting, set.Value = "kafka-main", "MEMBER", "kafka-1", "tlsProfile", "tls"
	commands = append(commands, set)
	result := commitStructuralForTest(t, f2Backend(h1Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)
	deleteTLS := h1Command(result.NewProjectRevision, "DeleteTLSProfile")
	deleteTLS.EntityID = "tls"
	plan, err := f2Backend(h1Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{deleteTLS})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestH1TLSProfileDeleteUsesCatalogReferenceMetadata(t *testing.T) {
	for _, scope := range []struct {
		name     string
		scope    string
		memberID string
	}{
		{name: "deployment", scope: "DEPLOYMENT"},
		{name: "member", scope: "MEMBER", memberID: "kafka-1"},
	} {
		t.Run(scope.name, func(t *testing.T) {
			catalog := h1CatalogWithTLSProfileSetting("securityProfile")
			root, revision := emptyManagedProject(t)
			commands := append(h1TopologyCommands(revision),
				pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
				pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
				pkiCommand(revision, "CreateTLSProfile", "tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
			)
			set := h1Command(revision, "SetServiceConfigurationValue")
			set.DeploymentID, set.Scope, set.MemberID, set.Setting, set.Value = "kafka-main", scope.scope, scope.memberID, "securityProfile", "tls"
			result := commitStructuralForTest(t, f2Backend(catalog), root, projectlifecycle.ClassificationEmpty, revision, append(commands, set))
			deleteTLS := h1Command(result.NewProjectRevision, "DeleteTLSProfile")
			deleteTLS.EntityID = "tls"
			plan, err := f2Backend(catalog).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{deleteTLS})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" {
				t.Fatalf("plan=%#v err=%v", plan, err)
			}
		})
	}
}

func TestH1TLSProfileDeleteAllowsFinalStateReferenceRemoval(t *testing.T) {
	catalog := h1CatalogWithTLSProfileSetting("securityProfile")
	root, revision := emptyManagedProject(t)
	commands := append(h1TopologyCommands(revision),
		pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
		pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
		pkiCommand(revision, "CreateTLSProfile", "tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
	)
	set := h1Command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Scope, set.Setting, set.Value = "kafka-main", "DEPLOYMENT", "securityProfile", "tls"
	result := commitStructuralForTest(t, f2Backend(catalog), root, projectlifecycle.ClassificationEmpty, revision, append(commands, set))
	remove := h1Command(result.NewProjectRevision, "RemoveServiceConfigurationOverride")
	remove.DeploymentID, remove.Scope, remove.Setting = "kafka-main", "DEPLOYMENT", "securityProfile"
	deleteTLS := h1Command(result.NewProjectRevision, "DeleteTLSProfile")
	deleteTLS.EntityID = "tls"
	plan, err := f2Backend(catalog).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{remove, deleteTLS})
	if err != nil || plan.Status != "READY" || !plan.SaveAllowed {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestH1TLSProfileDeleteFailsClosedWithoutExactCatalog(t *testing.T) {
	root, revision := emptyManagedProject(t)
	deleteTLS := h1Command(revision, "DeleteTLSProfile")
	deleteTLS.EntityID = "tls"
	for name, backend := range map[string]*Backend{
		"unavailable":  f2Backend(nil),
		"incompatible": f2Backend(&projectlifecycle.ProjectCatalogView{Status: "INCOMPATIBLE"}),
	} {
		t.Run(name, func(t *testing.T) {
			plan, err := backend.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{deleteTLS})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || (plan.Finding.Code != "PROJECT_CATALOG_UNAVAILABLE" && plan.Finding.Code != "PROJECT_CATALOG_INCOMPATIBLE") {
				t.Fatalf("plan=%#v err=%v", plan, err)
			}
		})
	}
}

func TestH1UnannotatedTLSProfileNamedSettingIsNotTLSProfileReference(t *testing.T) {
	catalog := h1CatalogWithUnannotatedTLSProfileSetting()
	root, revision := emptyManagedProject(t)
	commands := append(h1TopologyCommands(revision),
		pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
		pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
		pkiCommand(revision, "CreateTLSProfile", "tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
	)
	set := h1Command(revision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Scope, set.Setting, set.Value = "kafka-main", "DEPLOYMENT", "tlsProfile", "tls"
	result := commitStructuralForTest(t, f2Backend(catalog), root, projectlifecycle.ClassificationEmpty, revision, append(commands, set))
	deleteTLS := h1Command(result.NewProjectRevision, "DeleteTLSProfile")
	deleteTLS.EntityID = "tls"
	plan, err := f2Backend(catalog).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{deleteTLS})
	if err != nil || plan.Status != "READY" || !plan.SaveAllowed {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestH1ConfigurationValidatorKeepsExactEnumAndIntegerSemantics(t *testing.T) {
	minimum, maximum := float64(-2), float64(2)
	integer := &projectlifecycle.ProjectCatalogSetting{EditorShape: "INTEGER", Minimum: &minimum, Maximum: &maximum}
	for name, value := range map[string]any{"minimum": -2, "maximum": int64(2), "json integral": float64(1)} {
		t.Run(name, func(t *testing.T) {
			if err := validateConfigurationValue(integer, value); err != nil {
				t.Fatalf("value=%#v err=%v", value, err)
			}
		})
	}
	for name, value := range map[string]any{"below": -3, "above": int64(3), "fractional": 1.5, "unsafe native": int64(1<<53 + 1), "nan": math.NaN(), "infinity": math.Inf(1)} {
		t.Run(name, func(t *testing.T) {
			if err := validateConfigurationValue(integer, value); err == nil {
				t.Fatalf("value=%#v was accepted", value)
			}
		})
	}
	stringsEnum := &projectlifecycle.ProjectCatalogSetting{EditorShape: "ENUM", Enum: []any{"1"}}
	for name, value := range map[string]any{"integer": 1, "boolean": true, "string": "1"} {
		t.Run("enum "+name, func(t *testing.T) {
			err := validateConfigurationValue(stringsEnum, value)
			if name == "string" && err != nil {
				t.Fatal(err)
			}
			if name != "string" && err == nil {
				t.Fatalf("value=%#v was accepted", value)
			}
		})
	}
}

func TestConfigurationValidatorAcceptsOnlyClosedDNSDomainShape(t *testing.T) {
	setting := &projectlifecycle.ProjectCatalogSetting{EditorShape: "DNS_DOMAIN"}
	for _, value := range []any{"scada.local", "site-1.scada.local"} {
		if err := validateConfigurationValue(setting, value); err != nil {
			t.Fatalf("valid value=%#v err=%v", value, err)
		}
	}
	for _, value := range []any{"SCADA.local", "scada", "scada..local", 42} {
		if err := validateConfigurationValue(setting, value); err == nil {
			t.Fatalf("invalid value accepted: %#v", value)
		}
	}
}

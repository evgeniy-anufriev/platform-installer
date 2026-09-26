package projectlifecycle

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
)

func testBundle(t *testing.T) string {
	t.Helper()
	return testBundleWithCatalog(t, "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata:\n      id: kafka\n      version: 1.0.0\n      displayName: Kafka\n    modes:\n      single:\n        displayName: Single\n        memberRoles: [broker]\n        placement:\n          minMembers: 1\n          distinctHosts: false\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
}

func testBundleWithCatalog(t *testing.T, catalog string) string {
	t.Helper()
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "catalog"), 0o755); err != nil {
		t.Fatal(err)
	}
	catalogPath := filepath.Join(root, "catalog", "service-catalog.yml")
	if err := os.WriteFile(catalogPath, []byte(catalog), 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(catalog))
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: test\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: catalog/service-catalog.yml\n    sha256: sha256:" + hex.EncodeToString(sum[:]) + "\n    size: " + strconv.Itoa(len(catalog)) + "\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	return root
}

func TestCreateProjectPublishesOneManagedManifest(t *testing.T) {
	bundle := testBundle(t)
	parent := t.TempDir()
	service := NewService(map[string]string{DefaultCompatibilitySourceID: bundle})
	result, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(parent, "new-project"), DisplayName: "Production", CompatibilitySourceID: DefaultCompatibilitySourceID})
	if err != nil {
		t.Fatal(err)
	}
	if result.Classification != classificationEmpty || result.Project == nil || !validProjectID(result.Project.ID) {
		t.Fatalf("result=%+v", result)
	}
	if result.Catalog == nil || result.Catalog.Status != "READY" || len(result.Catalog.Services) != 1 || result.Catalog.Services[0].ID != "kafka" {
		t.Fatalf("catalog=%#v", result.Catalog)
	}
	entries, err := os.ReadDir(result.Root)
	if err != nil || len(entries) != 1 || entries[0].Name() != "project.yml" {
		t.Fatalf("entries=%v err=%v", entries, err)
	}
	data, err := os.ReadFile(filepath.Join(result.Root, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), "desiredState:") || !strings.Contains(string(data), managedProjectLabel) || !strings.Contains(string(data), "catalogLock:") || !strings.Contains(string(data), "artifactLock:") {
		t.Fatalf("unexpected manifest: %s", data)
	}
	reopened, err := service.OpenProject(t.Context(), result.Root)
	if err != nil || reopened.Classification != classificationEmpty || reopened.Project.ID != result.Project.ID || reopened.Project.Name != "Production" || reopened.Catalog == nil || reopened.Catalog.Status != "READY" {
		t.Fatalf("reopened=%+v err=%v", reopened, err)
	}
}

func TestProjectCatalogViewIsClosedStableAndPreservesRoleOrder(t *testing.T) {
	bundle := testBundleWithCatalog(t, "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  zeta:\n    metadata: {id: zeta, version: 1.0.0, displayName: Zeta, category: test}\n    modes:\n      mode:\n        displayName: Mode\n        memberRoles: [second, first]\n        placement:\n          minMembers: 1\n          distinctHosts: true\n          roleCardinality:\n            first: {minimum: 1}\n            second: {minimum: 1, maximum: 2}\n    endpointConsumer: {}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n  alpha:\n    metadata: {id: alpha, version: 1.0.0, displayName: Alpha}\n    modes:\n      mode:\n        displayName: Mode\n        memberRoles: []\n        placement: {hostScoped: true, minMembers: 0, distinctHosts: false}\n    endpointProvider: {}\n    x-definitionDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n")
	verified, err := executionbundle.ValidateRoot(bundle)
	if err != nil {
		t.Fatal(err)
	}
	catalog, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	view := catalog.view(verified)
	if view.Status != "READY" || view.BundleVersion != "test" || len(view.Services) != 2 || view.Services[0].ID != "alpha" || view.Services[1].ID != "zeta" {
		t.Fatalf("view=%#v", view)
	}
	mode := view.Services[1].Modes[0]
	if !view.Services[0].EndpointProvider || !view.Services[1].EndpointConsumer || mode.PlacementKind != "MEMBER_SCOPED" || strings.Join(mode.Roles, ",") != "second,first" || len(mode.Guidance.RoleCardinality) != 2 || mode.Guidance.RoleCardinality[0].Role != "first" {
		t.Fatalf("view=%#v", view)
	}
}

func TestProjectCatalogModeProjectsOnlyTrustedRequiredRuntimeSecretSettings(t *testing.T) {
	catalogText := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  redis:\n    metadata: {id: redis, version: 1.0.0, displayName: Redis}\n    modes:\n      standalone:\n        displayName: Standalone\n        memberRoles: [redis]\n        x-requiredRuntimeSecretSettings: [redisCredential]\n        placement: {minMembers: 1, distinctHosts: false}\n    configuration:\n      settings:\n        redisCredential:\n          kind: MANAGED\n          roleVariable: platform_redis_credential\n          type: object\n          scopes: [deployment]\n          validation: {required: [passwordSecretRef]}\n          schema:\n            type: object\n            additionalProperties: false\n            required: [passwordSecretRef]\n            properties:\n              passwordSecretRef: {type: string, minLength: 1}\n          ui:\n            x-runtimeSecretRequirement: {requirementRef: redis-password, purpose: SERVICE_PASSWORD}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, catalogText))
	if err != nil {
		t.Fatal(err)
	}
	value, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	mode := value.view(verified).Services[0].Modes[0]
	if got := strings.Join(mode.RequiredRuntimeSecretSettings, ","); got != "redisCredential" {
		t.Fatalf("required secrets=%q", got)
	}
	for _, invalid := range []string{"missing setting", "non-secret setting", "duplicate setting"} {
		t.Run(invalid, func(t *testing.T) {
			candidate := catalogText
			switch invalid {
			case "missing setting":
				candidate = strings.Replace(candidate, "[redisCredential]", "[notThere]", 1)
			case "non-secret setting":
				candidate = strings.Replace(candidate, "x-runtimeSecretRequirement: {requirementRef: redis-password, purpose: SERVICE_PASSWORD}", "label: ordinary", 1)
			case "duplicate setting":
				candidate = strings.Replace(candidate, "[redisCredential]", "[redisCredential, redisCredential]", 1)
			}
			bundle := testBundleWithCatalog(t, candidate)
			verified, err := executionbundle.ValidateRoot(bundle)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := readCatalog(verified); err == nil {
				t.Fatal("invalid mode secret metadata accepted")
			}
		})
	}
}

func TestProjectCatalogProjectsClosedSecretInputMetadata(t *testing.T) {
	catalogText := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  vault:\n    metadata: {id: vault, version: 1.21.2, displayName: Vault}\n    modes:\n      standalone: {displayName: Standalone, memberRoles: [vault], placement: {minMembers: 1}}\n    x-secretInputs:\n      apiVersion: ServiceSecretInputs/v1alpha1\n      inputs:\n        - {requirementRef: vault-admin-token, purpose: SERVICE_ADMIN_TOKEN, displayLabel: Administrative token, requiredWhen: INITIALIZED, operations: [SERVICE_APPLY, SERVICE_VERIFY]}\n        - {requirementRef: vault-unseal-shares, purpose: SERVICE_UNSEAL_SHARES, displayLabel: Unseal keys, requiredWhen: SEALED, operations: [SERVICE_APPLY]}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, catalogText))
	if err != nil {
		t.Fatal(err)
	}
	value, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	inputs := value.view(verified).Services[0].SecretInputs
	if len(inputs) != 2 || inputs[0].RequirementRef != "vault-admin-token" || inputs[0].Purpose != "SERVICE_ADMIN_TOKEN" || inputs[1].Purpose != "SERVICE_UNSEAL_SHARES" || len(inputs[1].Operations) != 1 || inputs[1].Operations[0] != "SERVICE_APPLY" {
		t.Fatalf("unexpected safe input projection: %#v", inputs)
	}

	invalids := []string{
		strings.Replace(catalogText, "apiVersion: ServiceSecretInputs/v1alpha1", "apiVersion: ServiceSecretInputs/v1alpha9", 1),
		strings.Replace(catalogText, "operations: [SERVICE_APPLY]", "operations: [SERVICE_VERIFY]", 1),
		strings.Replace(catalogText, "requiredWhen: SEALED", "requiredWhen: ALWAYS", 1),
		strings.Replace(catalogText, "requirementRef: vault-unseal-shares", "requirementRef: vault-admin-token", 1),
		strings.Replace(catalogText, "displayLabel: Unseal keys,", "displayLabel: Unseal keys, unexpected: true,", 1),
	}
	for index, candidate := range invalids {
		t.Run(strconv.Itoa(index), func(t *testing.T) {
			bundle, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, candidate))
			if err != nil {
				t.Fatal(err)
			}
			if _, err := readCatalog(bundle); err == nil {
				t.Fatal("malformed secret input metadata accepted")
			}
		})
	}
}

func TestCatalogSecretOutputProjectionAcceptsOnlyFixedProtocolEntries(t *testing.T) {
	valid := map[string]any{"protocol": "SecretOutputDelivery/v1alpha1", "entries": []any{"admin-token", "unseal-shares"}}
	if !validCatalogSecretOutputs(valid) || strings.Join(projectCatalogSecretOutputEntries(valid), ",") != "admin-token,unseal-shares" {
		t.Fatal("approved output metadata was not projected")
	}
	for _, invalid := range []map[string]any{
		{"protocol": "SecretOutputDelivery/v1alpha2", "entries": []any{"admin-token", "unseal-shares"}},
		{"protocol": "SecretOutputDelivery/v1alpha1", "entries": []any{"admin-token", "unseal-shares", "extra"}},
		{"protocol": "SecretOutputDelivery/v1alpha1", "entries": []any{"../token", "unseal-shares"}},
		{"protocol": "SecretOutputDelivery/v1alpha1", "entries": []any{"admin-token", "unseal-shares"}, "path": "/tmp"},
	} {
		if validCatalogSecretOutputs(invalid) {
			t.Fatalf("unsafe output metadata admitted: %#v", invalid)
		}
	}
	if !validCatalogSecretOutputs(nil) || projectCatalogSecretOutputEntries(nil) != nil {
		t.Fatal("absent optional declaration changed semantics")
	}
}

func TestReadCatalogAcceptsPublishedIdentifierGrammar(t *testing.T) {
	bundle := testBundleWithCatalog(t, "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  postgresql:\n    metadata: {id: postgresql, version: 1.0.0, displayName: PostgreSQL}\n    modes:\n      pg_auto_failover:\n        displayName: pg_auto_failover\n        memberRoles: [data_member]\n        placement:\n          minMembers: 1\n          roleCardinality:\n            data_member: {minimum: 1}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n")
	verified, err := executionbundle.ValidateRoot(bundle)
	if err != nil {
		t.Fatal(err)
	}
	value, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	if got := value.view(verified).Services[0].Modes[0].ID; got != "pg_auto_failover" {
		t.Fatalf("mode=%q", got)
	}
}

func TestH1CatalogSettingProjectionIsClosedAndMetadataDriven(t *testing.T) {
	minimum, maximum := 1, 10
	settings := map[string]catalogSetting{}
	boolean := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_enabled", Type: "boolean", Scopes: []string{"deployment"}, Validation: map[string]any{}}
	boolean.UI.Label = "Enabled"
	integer := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_port", Type: "integer", Scopes: []string{"member", "deployment"}, Validation: map[string]any{"minimum": minimum, "maximum": maximum}}
	freeString := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_password_secret_ref", Type: "string", Scopes: []string{"deployment"}, Validation: map[string]any{"minLength": 1}}
	freeString.UI.Label = "Looks like a secret"
	tls := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_profile", Type: "string", Scopes: []string{"deployment"}, Validation: map[string]any{"minLength": 1}}
	tls.UI.XReferenceKind = "TLS_PROFILE"
	unknownReference := tls
	unknownReference.UI.XReferenceKind = "SERVICE_DEPLOYMENT"
	objectNamedBoolean := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_boolean", Type: "object", Scopes: []string{"deployment"}, Validation: map[string]any{}}
	settings["enabled"], settings["port"], settings["passwordSecretRef"], settings["opaqueName"], settings["tlsChoice"], settings["otherRef"] = boolean, integer, freeString, objectNamedBoolean, tls, unknownReference

	want := map[string]string{"enabled": "BOOLEAN", "port": "INTEGER", "passwordSecretRef": "UNSUPPORTED", "opaqueName": "UNSUPPORTED", "tlsChoice": "TLS_PROFILE", "otherRef": "SERVICE_DEPLOYMENT"}
	for id, source := range settings {
		got := projectCatalogSetting(id, source)
		if got.EditorShape != want[id] {
			t.Fatalf("%s shape=%s want=%s", id, got.EditorShape, want[id])
		}
		if id == "tlsChoice" && got.ReferenceKind != "TLS_PROFILE" {
			t.Fatalf("tls descriptor=%#v", got)
		}
		if id == "otherRef" && got.ReferenceKind != "SERVICE_DEPLOYMENT" {
			t.Fatalf("service deployment descriptor=%#v", got)
		}
	}
}

func TestH1CatalogSettingProjectionRejectsIncompleteBoundsAndArbitraryPattern(t *testing.T) {
	for name, setting := range map[string]catalogSetting{
		"integer without maximum": {Kind: "MANAGED", RoleVariable: "platform_value", Type: "integer", Scopes: []string{"deployment"}, Validation: map[string]any{"minimum": 1}},
		"string without maximum":  {Kind: "MANAGED", RoleVariable: "platform_value", Type: "string", Scopes: []string{"deployment"}, Validation: map[string]any{"minLength": 1}},
		"pattern":                 {Kind: "MANAGED", RoleVariable: "platform_value", Type: "string", Scopes: []string{"deployment"}, Validation: map[string]any{"minLength": 1, "maxLength": 10, "pattern": ".*"}},
	} {
		t.Run(name, func(t *testing.T) {
			if got := projectCatalogSetting("value", setting); got.EditorShape != "UNSUPPORTED" {
				t.Fatalf("descriptor=%#v", got)
			}
		})
	}
}

func TestRuntimeSecretReferenceObjectProjectionRequiresExactTrustedShape(t *testing.T) {
	secretObject := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_postgresql_admin", Type: "object", Scopes: []string{"deployment"}, Validation: map[string]any{"required": []any{"username", "passwordSecretRef"}}, Schema: map[string]any{
		"type": "object", "additionalProperties": false, "required": []any{"username", "passwordSecretRef"},
		"properties": map[string]any{
			"username":          map[string]any{"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]{0,62}$"},
			"passwordSecretRef": map[string]any{"type": "string", "minLength": 1},
		},
	}}
	secretObject.UI.XRuntimeSecretRequirement = map[string]any{"requirementRef": "postgresql-admin-password", "purpose": "SERVICE_PASSWORD"}
	projected := projectCatalogSetting("adminSuperuser", secretObject)
	if projected.EditorShape != "RUNTIME_SECRET_REFERENCE_OBJECT" || projected.RuntimeSecretRequirementRef != "postgresql-admin-password" || !projected.RuntimeSecretUsernameRequired {
		t.Fatalf("descriptor=%#v", projected)
	}
	for name, mutate := range map[string]func(*catalogSetting){
		"unknown object property": func(value *catalogSetting) {
			value.Schema["properties"].(map[string]any)["other"] = map[string]any{"type": "string"}
		},
		"missing trusted metadata": func(value *catalogSetting) { value.UI.XRuntimeSecretRequirement = nil },
		"wrong purpose":            func(value *catalogSetting) { value.UI.XRuntimeSecretRequirement["purpose"] = "SECRET_REF" },
		"open object":              func(value *catalogSetting) { value.Schema["additionalProperties"] = true },
	} {
		t.Run(name, func(t *testing.T) {
			candidate := secretObject
			candidate.Validation = map[string]any{"required": []any{"username", "passwordSecretRef"}}
			candidate.Schema = map[string]any{"type": secretObject.Schema["type"], "additionalProperties": secretObject.Schema["additionalProperties"], "required": []any{"username", "passwordSecretRef"}, "properties": map[string]any{"username": map[string]any{"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]{0,62}$"}, "passwordSecretRef": map[string]any{"type": "string", "minLength": 1}}}
			candidate.UI.XRuntimeSecretRequirement = map[string]any{"requirementRef": "postgresql-admin-password", "purpose": "SERVICE_PASSWORD"}
			mutate(&candidate)
			if got := projectCatalogSetting("adminSuperuser", candidate); got.EditorShape != "UNSUPPORTED" {
				t.Fatalf("descriptor=%#v", got)
			}
		})
	}
}

func TestDNSDomainEditorShapeRequiresExactClosedMetadata(t *testing.T) {
	exact := catalogSetting{Kind: "MANAGED", RoleVariable: "platform_bind_zone", Type: "string", Scopes: []string{"deployment"}, Validation: map[string]any{"minLength": 4, "maxLength": 253, "pattern": dnsDomainValidationPattern}}
	projected := projectCatalogSetting("zone", exact)
	if projected.EditorShape != "DNS_DOMAIN" || projected.MinLength == nil || *projected.MinLength != 4 || projected.MaxLength == nil || *projected.MaxLength != 253 {
		t.Fatalf("exact descriptor=%#v", projected)
	}
	for name, validation := range map[string]map[string]any{
		"different pattern": {"minLength": 4, "maxLength": 253, "pattern": ".*"},
		"different lower":   {"minLength": 3, "maxLength": 253, "pattern": dnsDomainValidationPattern},
		"different upper":   {"minLength": 4, "maxLength": 254, "pattern": dnsDomainValidationPattern},
	} {
		t.Run(name, func(t *testing.T) {
			candidate := exact
			candidate.Validation = validation
			if got := projectCatalogSetting("zone", candidate); got.EditorShape != "UNSUPPORTED" {
				t.Fatalf("descriptor=%#v", got)
			}
		})
	}
}

func TestValidDNSDomainMatchesClosedCoreShape(t *testing.T) {
	valid := []string{"a.aa", "scada.local", "site-1.scada.local", strings.Repeat("a", 63) + "." + strings.Repeat("b", 63) + "." + strings.Repeat("c", 63) + "." + strings.Repeat("d", 61)}
	for _, value := range valid {
		if !ValidDNSDomain(value) {
			t.Fatalf("valid domain rejected: %q", value)
		}
	}
	for _, value := range []string{"", "abc", "SCADA.local", "-scada.local", "scada-.local", "scada..local", "scada.1ocal", strings.Repeat("a", 254) + ".zz"} {
		if ValidDNSDomain(value) {
			t.Fatalf("invalid domain accepted: %q", value)
		}
	}
}

func TestH1ClosedEnumRequiresExactDeclaredJSONTypeAndSafeIntegers(t *testing.T) {
	for name, input := range map[string]struct {
		valueType string
		values    []any
		accepted  bool
	}{
		"string accepts strings":                  {valueType: "string", values: []any{"1", "enabled"}, accepted: true},
		"string rejects integer":                  {valueType: "string", values: []any{1}},
		"string rejects boolean":                  {valueType: "string", values: []any{true}},
		"boolean rejects textual true":            {valueType: "boolean", values: []any{"true"}},
		"integer accepts signed safe boundary":    {valueType: "integer", values: []any{int64(-(1 << 53)), int64(1 << 53)}, accepted: true},
		"integer rejects fractional":              {valueType: "integer", values: []any{1.5}},
		"integer rejects unsafe native precision": {valueType: "integer", values: []any{int64(1<<53 + 1)}},
		"number accepts integral and decimal":     {valueType: "number", values: []any{1, 1.5}, accepted: true},
		"boolean accepts boolean":                 {valueType: "boolean", values: []any{true, false}, accepted: true},
	} {
		t.Run(name, func(t *testing.T) {
			_, ok := closedEnum(input.valueType, map[string]any{"enum": input.values})
			if ok != input.accepted {
				t.Fatalf("closedEnum(%q, %#v) accepted=%t", input.valueType, input.values, ok)
			}
		})
	}
}

func TestH1VerifiedCatalogProjectsStableBoundedSettingsWithoutRawSchema(t *testing.T) {
	catalogText := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      kraft: {displayName: KRaft, memberRoles: [broker], placement: {minMembers: 1}}\n    configuration:\n      settings:\n        tlsProfile:\n          kind: MANAGED\n          roleVariable: platform_kafka_tls_profile\n          type: string\n          scopes: [member, deployment]\n          validation: {minLength: 1}\n          ui: {label: TLS profile, section: TLS, order: 20, x-referenceKind: TLS_PROFILE}\n        port:\n          kind: MANAGED\n          roleVariable: platform_kafka_port\n          type: integer\n          scopes: [deployment]\n          validation: {minimum: 1, maximum: 65535}\n          ui: {label: Port, section: Network, order: 10}\n        listeners:\n          kind: MANAGED\n          roleVariable: platform_kafka_listeners\n          type: object\n          scopes: [deployment]\n          validation: {}\n          schema: {type: object, additionalProperties: true}\n          ui: {label: Listeners}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, catalogText))
	if err != nil {
		t.Fatal(err)
	}
	value, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	settings := value.view(verified).Services[0].ConfigurationSettings
	if len(settings) != 3 || settings[0].ID != "listeners" || settings[1].ID != "port" || settings[2].ID != "tlsProfile" || settings[1].EditorShape != "INTEGER" || settings[2].ReferenceKind != "TLS_PROFILE" {
		t.Fatalf("settings=%#v", settings)
	}
	encoded, err := json.Marshal(settings)
	if err != nil {
		t.Fatal(err)
	}
	text := string(encoded)
	if strings.Contains(text, "roleVariable") || strings.Contains(text, "platform_kafka") || strings.Contains(text, "additionalProperties") {
		t.Fatalf("raw catalog leaked: %s", text)
	}
}

func TestH1GeneratedCatalogSettingsAreAccepted(t *testing.T) {
	content, err := os.ReadFile(filepath.Join("..", "..", "examples", "catalog", "service-catalog.yml"))
	if err != nil {
		t.Fatal(err)
	}
	verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, string(content)))
	if err != nil {
		t.Fatal(err)
	}
	value, err := readCatalog(verified)
	if err != nil {
		t.Fatal(err)
	}
	view := value.view(verified)
	var kafka *ProjectCatalogService
	for index := range view.Services {
		if view.Services[index].ID == "kafka" {
			kafka = &view.Services[index]
		}
	}
	if kafka == nil || len(kafka.ConfigurationSettings) == 0 {
		t.Fatalf("kafka settings missing: %#v", kafka)
	}
	shapes := map[string]string{}
	for _, setting := range kafka.ConfigurationSettings {
		shapes[setting.ID] = setting.EditorShape
	}
	if shapes["quorumMode"] != "ENUM" || shapes["nodeId"] != "INTEGER" || shapes["tlsProfile"] != "TLS_PROFILE" || shapes["listeners"] != "UNSUPPORTED" || shapes["dataDirectory"] != "UNSUPPORTED" {
		t.Fatalf("shapes=%#v", shapes)
	}
}

func TestReadCatalogRejectsMalformedKnownFieldsAndDuplicateRoles(t *testing.T) {
	for name, catalogText := range map[string]string{
		"duplicate role":           "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [broker, broker], placement: {minMembers: 1}}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
		"duplicate known key":      "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [], placement: {minMembers: 1}}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
		"endpoint scalar":          "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [], placement: {minMembers: 1}}\n    endpointConsumer: true\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
		"endpoint one field":       "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [], placement: {minMembers: 1}}\n    endpointConsumer: {unexpected: true}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
		"endpoint multiple fields": "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [], placement: {minMembers: 1}}\n    endpointProvider: {unexpected: true, another: false}\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
	} {
		t.Run(name, func(t *testing.T) {
			verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, catalogText))
			if err != nil {
				t.Fatal(err)
			}
			if _, err := readCatalog(verified); err == nil || strings.Contains(err.Error(), "unexpected") {
				t.Fatalf("err=%v", err)
			}
		})
	}
}

func TestReadCatalogAcceptsEmptyOrAbsentGenericEndpoint(t *testing.T) {
	for name, capability := range map[string]string{"empty": "endpointConsumer: {}", "absent": ""} {
		t.Run(name, func(t *testing.T) {
			catalogText := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata: {id: kafka, version: 1.0.0, displayName: Kafka}\n    modes:\n      single: {displayName: Single, memberRoles: [], placement: {minMembers: 1}}\n    " + capability + "\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
			verified, err := executionbundle.ValidateRoot(testBundleWithCatalog(t, catalogText))
			if err != nil {
				t.Fatal(err)
			}
			catalog, err := readCatalog(verified)
			if err != nil {
				t.Fatal(err)
			}
			view := catalog.view(verified)
			if len(view.Services) != 1 || view.Services[0].EndpointConsumer != (capability != "") {
				t.Fatalf("view=%#v", view)
			}
		})
	}
}

func TestCreateProjectFailsClosedForSourceAndDestination(t *testing.T) {
	parent := t.TempDir()
	root := filepath.Join(parent, "new-project")
	service := NewService(map[string]string{})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("unexpected root: %v", err)
	}
	if err := os.Mkdir(root, 0o755); err != nil {
		t.Fatal(err)
	}
	service = NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_DESTINATION_EXISTS" {
		t.Fatalf("err=%v", err)
	}
}

func TestCreateProjectReverifiesCompatibilitySourceOnEveryCall(t *testing.T) {
	bundle := testBundle(t)
	service := NewService(map[string]string{DefaultCompatibilitySourceID: bundle})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(t.TempDir(), "first"), DisplayName: "First", CompatibilitySourceID: DefaultCompatibilitySourceID}); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(bundle, "catalog", "service-catalog.yml"), []byte("modified"), 0o644); err != nil {
		t.Fatal(err)
	}
	root := filepath.Join(t.TempDir(), "second")
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Second", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("source failure wrote project: %v", err)
	}
}

func TestCreateProjectRaceAndPublishFailureNeverReplaceDestination(t *testing.T) {
	parent := t.TempDir()
	root := filepath.Join(parent, "new-project")
	service := NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.beforePublish = func(destination string) error { return os.Mkdir(destination, 0o755) }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil {
		t.Fatal("race accepted")
	}
	if _, err := os.Stat(root); err != nil {
		t.Fatal(err)
	}
	root = filepath.Join(parent, "publish-failure")
	service = NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.publish = func(string, string) error { return errors.New("simulated") }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_PUBLISH_FAILED" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("published after failure: %v", err)
	}
}

func TestCreateProjectSurfacesOwnStagingCleanupFailure(t *testing.T) {
	parent := t.TempDir()
	service := NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.publish = func(string, string) error { return errors.New("simulated") }
	service.removeAll = func(string) error { return errors.New("simulated cleanup failure") }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(parent, "new-project"), DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_CREATE_CLEANUP_FAILED" {
		t.Fatalf("err=%v", err)
	}
}

func TestOpenNeverAdoptsExternalIncompleteOrMalformedManagedProject(t *testing.T) {
	service := NewService(nil)
	for _, test := range []struct{ name, content, want string }{
		{name: "external", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: external\n", want: classificationIncomplete},
		{name: "malformed", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  labels:\n    platform.installer/managed-project: v1alpha1\n", want: classificationInvalid},
		{name: "desired-state", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Incorrect empty project\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ndesiredState: {}\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services:\n    kafka:\n      definitionVersion: 1.0.0\n      digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n", want: classificationInvalid},
	} {
		root := filepath.Join(t.TempDir(), test.name)
		if err := os.Mkdir(root, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(test.content), 0o644); err != nil {
			t.Fatal(err)
		}
		result, _ := service.OpenProject(t.Context(), root)
		if result.Classification != test.want || result.Classification == classificationEmpty {
			t.Fatalf("%s: %+v", test.name, result)
		}
	}
}

func TestOpenClassifiesExternalCanonicalProjectWithoutAdoption(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("apiVersion: external/v1\nkind: External\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0o755); err != nil {
		t.Fatal(err)
	}
	result, err := NewService(nil).OpenProject(t.Context(), root)
	if err != nil || result.Classification != classificationExternal || result.Project != nil {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}

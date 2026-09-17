package installer

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"testing"

	"platform-installer/internal/projectlifecycle"
)

func pkiCommand(revision, operation, id string, entity map[string]any) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV7, Kind: "EditCommand", BaseProjectRevision: revision, Operation: operation, EntityID: id, Entity: entity}
}

func TestPKIStructuralSaveReopenPreservesCompleteScope(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
		pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
		pkiCommand(revision, "CreateTLSProfile", "infrastructure-tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
		pkiCommand(revision, "CreateCertificateScope", "infra", map[string]any{"displayName": "Infrastructure", "profile": "server", "scope": "DEPLOYMENT", "sources": map[string]any{"explicitDnsNames": []any{"edge.example.test"}, "explicitIpAddresses": []any{"192.0.2.10"}}}),
	}
	result := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationEmpty, revision, commands)
	scope := result.Managed.PKI.Scopes["infra"]
	if scope["displayName"] != "Infrastructure" || scope["scope"] != "DEPLOYMENT" || len(asSlice(asMap(scope["sources"])["explicitDnsNames"])) != 1 {
		t.Fatalf("scope=%#v", scope)
	}
	reopened, err := ReadManagedProjectView(root)
	if err != nil || reopened.PKI.TLSProfiles["infrastructure-tls"]["storePasswordSecretRef"] != "runtime:tls-store" || len(reopened.PKI.Scopes) != 1 {
		t.Fatalf("reopened=%#v err=%v", reopened, err)
	}
}

func TestPKIDeleteReferencedProfileIsBlocked(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Platform CA"}),
		pkiCommand(revision, "CreateCertificateProfile", "server", map[string]any{"authorityRef": "platform-ca", "sanPolicy": map[string]any{}}),
		pkiCommand(revision, "CreateTLSProfile", "tls", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "runtime:tls-store"}),
		pkiCommand(revision, "DeleteCertificateProfile", "server", nil),
	}
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, commands)
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestPKIUpdatePreservesSchemaExtension(t *testing.T) {
	root, revision := emptyManagedProject(t)
	created := pkiCommand(revision, "CreateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "Old CA", "x-owner": "preserve"})
	result := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{created})
	updated := pkiCommand(result.NewProjectRevision, "UpdateCertificateAuthority", "platform-ca", map[string]any{"mode": "MANAGED", "commonName": "New CA"})
	result = commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationManaged, result.NewProjectRevision, []EditCommand{updated})
	if result.Managed.PKI.Authorities["platform-ca"]["x-owner"] != "preserve" {
		t.Fatalf("authority=%#v", result.Managed.PKI.Authorities["platform-ca"])
	}
}

func TestPKIEntityValidatorAcceptsClosedSchemaBoundaries(t *testing.T) {
	tests := []struct {
		name      string
		operation string
		entity    map[string]any
	}{
		{"authority", "CreateCertificateAuthority", map[string]any{"mode": "MANAGED", "commonName": "a", "displayName": "d", "validityDays": 1, "x-keep": map[string]any{"opaque": true}}},
		{"profile", "CreateCertificateProfile", map[string]any{"authorityRef": "platform-ca", "keyAlgorithm": "RSA", "keySize": 2048, "validityDays": 1, "usages": []any{"serverAuth", "clientAuth"}, "sanPolicy": map[string]any{"includeHostDns": true}, "subject": map[string]any{"C": "RU", "OU": "platform"}}},
		{"tls", "CreateTLSProfile", map[string]any{"certificateProfileRef": "server", "scope": "DEPLOYMENT", "storePasswordSecretRef": "runtime:tls-store"}},
		{"scope", "CreateCertificateScope", map[string]any{"profile": "server", "scope": "MEMBER", "sources": map[string]any{"hosts": []any{"node1"}, "serviceDeployments": []any{"kafka-main"}, "members": []any{map[string]any{"deploymentId": "kafka-main", "memberId": "kafka-kafka-1"}}, "explicitDnsNames": []any{"edge.example.test"}, "explicitIpAddresses": []any{"192.0.2.10"}, "x-note": "opaque"}}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := validPKIEntity(test.operation, test.entity); err != nil {
				t.Fatalf("err=%v", err)
			}
		})
	}
}

func TestPKIEntityValidatorRejectsMalformedNestedFields(t *testing.T) {
	tests := []struct {
		name      string
		operation string
		entity    map[string]any
	}{
		{"authority empty display", "CreateCertificateAuthority", map[string]any{"mode": "MANAGED", "commonName": "ca", "displayName": ""}},
		{"profile unknown policy", "CreateCertificateProfile", map[string]any{"authorityRef": "ca", "sanPolicy": map[string]any{"surprise": true}}},
		{"profile duplicate usages", "CreateCertificateProfile", map[string]any{"authorityRef": "ca", "usages": []any{"serverAuth", "serverAuth"}, "sanPolicy": map[string]any{}}},
		{"profile malformed subject", "CreateCertificateProfile", map[string]any{"authorityRef": "ca", "sanPolicy": map[string]any{}, "subject": map[string]any{"C": true}}},
		{"tls malformed secret reference", "CreateTLSProfile", map[string]any{"certificateProfileRef": "server", "storePasswordSecretRef": "not-runtime"}},
		{"scope malformed member", "CreateCertificateScope", map[string]any{"profile": "server", "sources": map[string]any{"members": []any{map[string]any{"deploymentId": "d", "memberId": "m", "extra": true}}}}},
		{"scope duplicate dns", "CreateCertificateScope", map[string]any{"profile": "server", "sources": map[string]any{"explicitDnsNames": []any{"a.example", "a.example"}}}},
		{"scope malformed ip", "CreateCertificateScope", map[string]any{"profile": "server", "sources": map[string]any{"explicitIpAddresses": []any{"not-an-ip"}}}},
		{"scope null list", "CreateCertificateScope", map[string]any{"profile": "server", "sources": map[string]any{"hosts": nil}}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if err := validPKIEntity(test.operation, test.entity); err == nil {
				t.Fatal("expected rejection")
			}
		})
	}
}

func TestPKIEntityValidatorRejectsCollectionLimit(t *testing.T) {
	hosts := make([]any, maxManagedEntities+1)
	for index := range hosts {
		hosts[index] = fmt.Sprintf("node-%d", index)
	}
	err := validPKIEntity("CreateCertificateScope", map[string]any{"profile": "server", "sources": map[string]any{"hosts": hosts}})
	if err == nil {
		t.Fatal("expected bounded collection rejection")
	}
}

func TestPKIFinalReferencesFailWhenTargetRootIsAbsent(t *testing.T) {
	tests := []struct {
		name  string
		state map[string]any
	}{
		{"profile authority", map[string]any{"certificateProfiles": map[string]any{"server": map[string]any{"authorityRef": "missing-ca", "sanPolicy": map[string]any{}}}}},
		{"tls profile", map[string]any{"tlsProfiles": map[string]any{"tls": map[string]any{"certificateProfileRef": "missing-profile", "storePasswordSecretRef": "runtime:tls-store"}}}},
		{"scope profile", map[string]any{"certificateScopes": map[string]any{"scope": map[string]any{"profile": "missing-profile", "sources": map[string]any{}}}}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := validatePKIReferences(test.state, map[string]any{}, topologyMutationSet{})
			if err == nil || err.(*writerError).code != "REFERENCE_NOT_FOUND" {
				t.Fatalf("err=%v", err)
			}
		})
	}
}

func TestPKIValidatorUsesDesiredStateIdentifierGrammar(t *testing.T) {
	maximum := "a" + strings.Repeat("a", 127)
	validProfile := func(reference string) map[string]any {
		return map[string]any{"authorityRef": reference, "sanPolicy": map[string]any{}}
	}
	for _, reference := range []string{"authority.name_with-part", maximum} {
		if err := validPKIEntity("CreateCertificateProfile", validProfile(reference)); err != nil {
			t.Fatalf("valid desired-state identifier %q rejected: %v", reference, err)
		}
	}
	for _, reference := range []string{"1authority", "authority$bad", "a" + strings.Repeat("a", 128)} {
		if err := validPKIEntity("CreateCertificateProfile", validProfile(reference)); err == nil {
			t.Fatalf("invalid desired-state identifier %q accepted", reference)
		}
	}
	scope := map[string]any{"profile": "profile.name_with-part", "sources": map[string]any{"hosts": []any{"host.name_with-part"}, "serviceDeployments": []any{"deployment.name_with-part"}, "members": []any{map[string]any{"deploymentId": "deployment.name_with-part", "memberId": "member.name_with-part"}}}}
	if err := validPKIEntity("CreateCertificateScope", scope); err != nil {
		t.Fatalf("desired-state source identifiers rejected: %v", err)
	}
}

func TestPKIValidatorAcceptsJSONDecodedIntegersExactly(t *testing.T) {
	var entity map[string]any
	if err := json.Unmarshal([]byte(`{"authorityRef":"authority.name","keySize":2048,"validityDays":1,"sanPolicy":{}}`), &entity); err != nil {
		t.Fatal(err)
	}
	if err := validPKIEntity("CreateCertificateProfile", entity); err != nil {
		t.Fatalf("JSON integer values rejected: %v", err)
	}
	if err := validPKIEntity("CreateCertificateProfile", map[string]any{"authorityRef": "authority", "keySize": 2048, "validityDays": int64(1), "sanPolicy": map[string]any{}}); err != nil {
		t.Fatalf("native YAML integer values rejected: %v", err)
	}
	for name, value := range map[string]any{
		"fractional": 2048.5,
		"nan":        math.NaN(),
		"infinity":   math.Inf(1),
		"overflow":   float64(1 << 54),
		"below min":  2047.0,
	} {
		t.Run(name, func(t *testing.T) {
			if err := validPKIEntity("CreateCertificateProfile", map[string]any{"authorityRef": "authority", "keySize": value, "sanPolicy": map[string]any{}}); err == nil {
				t.Fatal("expected exact integer rejection")
			}
		})
	}
}

func TestPKIValidatorUsagesPresenceIsStrict(t *testing.T) {
	base := map[string]any{"authorityRef": "authority", "sanPolicy": map[string]any{}}
	if err := validPKIEntity("CreateCertificateProfile", base); err != nil {
		t.Fatalf("omitted usages rejected: %v", err)
	}
	for _, usages := range []any{[]any{}, []any{"serverAuth"}} {
		entity := deepCopy(base).(map[string]any)
		entity["usages"] = usages
		if err := validPKIEntity("CreateCertificateProfile", entity); err != nil {
			t.Fatalf("valid usages %#v rejected: %v", usages, err)
		}
	}
	for _, usages := range []any{nil, "serverAuth", map[string]any{"serverAuth": true}} {
		entity := deepCopy(base).(map[string]any)
		entity["usages"] = usages
		if err := validPKIEntity("CreateCertificateProfile", entity); err == nil {
			t.Fatalf("invalid usages %#v accepted", usages)
		}
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(`{"authorityRef":"authority","sanPolicy":{},"usages":null}`), &decoded); err != nil {
		t.Fatal(err)
	}
	if err := validPKIEntity("CreateCertificateProfile", decoded); err == nil {
		t.Fatal("JSON usages:null accepted")
	}
}

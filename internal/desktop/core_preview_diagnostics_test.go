package desktop

import (
	"errors"
	"os"
	"path/filepath"
	"platform-installer/internal/executionnode"
	"regexp"
	"strings"
	"testing"
	"unicode"
)

func TestProjectFindingRussianDescriptionsCoverPublishedCoreCodes(t *testing.T) {
	pattern := regexp.MustCompile(`(?:(?:_finding|_issue)\(\s*|["']code["']\s*:\s*)["']([A-Z][A-Z0-9_]+)["']`)
	count := 0
	for _, directory := range []string{"module_utils", "action"} {
		files, err := filepath.Glob(filepath.Join("..", "..", "ansible-core", "collections", "ansible_collections", "platform", "core", "plugins", directory, "*.py"))
		if err != nil || len(files) == 0 {
			t.Fatal("Core finding sources unavailable")
		}
		for _, path := range files {
			source, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			for _, match := range pattern.FindAllSubmatch(source, -1) {
				code := string(match[1])
				if projectFindingMessagesRU[code] == "" {
					t.Errorf("Core finding needs a Russian description: %s (%s)", code, filepath.Base(path))
				}
				count++
			}
		}
	}
	if count == 0 {
		t.Fatal("finding coverage check found no codes")
	}
	for code, message := range projectFindingMessagesRU {
		if len(message) > 512 || !strings.ContainsFunc(message, func(r rune) bool { return unicode.In(r, unicode.Cyrillic) }) {
			t.Errorf("invalid Russian description: %s", code)
		}
	}
}

func TestProjectFindingsKeepCodesAndSafeContextWithRussianDescriptions(t *testing.T) {
	for _, code := range []string{"DNS_CLIENT_SERVER_NOT_FOUND", "DNS_ZONE_INVALID", "HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED", "ENDPOINT_PROVIDER_FIELD_REQUIRED", "FUTURE_CORE_CODE"} {
		findings, _ := safeVerificationFindings([]map[string]any{{"code": code, "status": "BLOCKED", "safeMessage": "English diagnostic must not be rendered", "field": "serviceDeployments.vip.endpointGroupRef"}})
		if len(findings) != 1 || findings[0].Code != code || findings[0].Severity != "BLOCKED" ||
			strings.Contains(findings[0].Summary, "English diagnostic") || !strings.Contains(findings[0].Summary, "serviceDeployments.vip.endpointGroupRef") ||
			!strings.ContainsFunc(findings[0].Summary, func(r rune) bool { return unicode.In(r, unicode.Cyrillic) }) {
			t.Fatalf("localized finding lost code or safe context: %#v", findings)
		}
	}
	const reason = "Этап: чтение каталога. Отсутствует обязательный документ."
	if got := projectFindingMessageRU("PROJECT_SNAPSHOT_INPUT_INVALID", reason); got != reason {
		t.Fatal("existing concrete Russian cause was replaced")
	}
	if got := projectFindingMessageRU("DNS_ZONE_INVALID", "Managed DNS zone «пример» is invalid"); got != projectFindingMessagesRU["DNS_ZONE_INVALID"] {
		t.Fatal("Russian input inside an English sentence bypassed translation")
	}
	if got := projectFindingMessageRU("HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED", "Backend TLS identity is unavailable"); !strings.Contains(got, "Не удалось определить DNS-имя") {
		t.Fatal("endpoint identity failure was confused with certificate SAN mismatch")
	}
}

func TestCorePreviewPreservesSafeStructuredCauseAndRejectsRawErrors(t *testing.T) {
	err := &executionnode.ExecutionError{Code: "PROJECT_SNAPSHOT_INPUT_INVALID", Findings: []executionnode.Finding{{Code: "PROJECT_SNAPSHOT_INPUT_INVALID", SafeMessage: "Этап: загрузка каталога. Отсутствует обязательный документ."}}}
	finding := servicePreviewFailureFinding(err)
	if finding.Code != err.Code || finding.SafeMessage != err.Findings[0].SafeMessage {
		t.Fatalf("finding lost: %+v", finding)
	}
	finding = servicePreviewFailureFinding(errors.New("password=PRIVATE_VALUE"))
	if finding.Code != "SERVICE_CONFIGURATION_PREVIEW_UNAVAILABLE" || finding.SafeMessage == "password=PRIVATE_VALUE" {
		t.Fatal("raw error leaked")
	}
}

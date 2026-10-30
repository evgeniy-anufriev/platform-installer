package desktop

import (
	"errors"
	"platform-installer/internal/executionnode"
	"testing"
)

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

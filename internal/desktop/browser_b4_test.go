//go:build browser

package desktop

import (
	"encoding/json"
	"platform-installer/internal/executionnode"
	"testing"
)

func TestB4BrowserRoutesReuseModeLifecycle(t *testing.T) {
	app, _, client := installationPlanApp(t, false)
	app.infrastructureVerificationRoot = t.TempDir()
	builder := &modeInstallationBuilder{}
	app.binding.plans = executionnode.NewExecutionService(builder, client)
	ops := browserOperations()
	payload := []byte(`[{"executionMode":"APPLICATION_LIBRARIES_ONLY","deploymentOrder":[],"applicationVaultSources":{}}]`)
	raw, err := ops["createInstallationPlanForMode"](app, payload)
	if err != nil {
		t.Fatal(err)
	}
	result := raw.(InstallationPlanOperation)
	if result.Error != nil || result.Plan == nil || result.Plan.ExecutionMode != executionnode.ApplicationLibrariesOnly {
		t.Fatalf("%+v", result)
	}
	cached, err := ops["getInfrastructureVerification"](app, []byte(`[]`))
	if err != nil {
		t.Fatal(err)
	}
	if cached.(InfrastructureVerificationView).Availability != "UNKNOWN" {
		t.Fatal("cache granted admission")
	}
	if _, err = ops["getInfrastructureVerification"](app, []byte(`["extra"]`)); err == nil {
		t.Fatal("extra arguments accepted")
	}
	if _, err = ops["createInstallationPlanForMode"](app, []byte(`[{},{}]`)); err == nil {
		t.Fatal("extra arguments accepted")
	}
	data, _ := json.Marshal(raw)
	if len(data) == 0 {
		t.Fatal("mode result not serializable")
	}
}

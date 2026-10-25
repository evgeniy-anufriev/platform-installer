package executionnode

import "testing"

func TestPostInstallCapabilityClosedVersionedContract(t *testing.T) {
	c := map[string]any{"apiVersion": "platform.installer/execution-capabilities/v1alpha12", "applicationPostInstall": map[string]any{
		"protocol": "ApplicationPostInstall/v1alpha1", "packageManifestVersion": "platform.installer/application-package/v1alpha3",
		"planContract": "platform.installer/plan/v1alpha9", "manifestContract": "platform.installer/execution-manifest/v1alpha7"}}
	if !postInstallCapabilitySupported(c) {
		t.Fatal("current feature rejected")
	}
	c["applicationPostInstall"].(map[string]any)["arbitrary"] = true
	if postInstallCapabilitySupported(c) {
		t.Fatal("unknown feature fields accepted")
	}
}

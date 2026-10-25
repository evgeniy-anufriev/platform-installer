package executionnode

import (
	"context"
	"slices"
)

const selectionPlanRequestVersion = "platform.installer/execution-runtime/v1alpha7"

type librarySelectionKey struct{}

// WithApplicationLibrarySelection binds an invocation option, never project data.
func WithApplicationLibrarySelection(ctx context.Context, skipped []string) context.Context {
	return context.WithValue(ctx, librarySelectionKey{}, slices.Clone(skipped))
}

func applicationLibrarySelection(ctx context.Context) []string {
	value, _ := ctx.Value(librarySelectionKey{}).([]string)
	return slices.Clone(value)
}

func sameLibrarySelection(left, right []string) bool {
	left = slices.Clone(left)
	right = slices.Clone(right)
	slices.Sort(left)
	slices.Sort(right)
	return slices.Equal(left, right)
}

func selectionCapabilitySupported(c map[string]any) bool {
	selection, ok := c["applicationLibrarySelection"].(map[string]any)
	return ok && (c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha11" || postInstallCapabilitySupported(c)) &&
		contains(c["deploymentPlanRequestVersions"], selectionPlanRequestVersion) &&
		selection["protocol"] == "ApplicationLibrarySelection/v1alpha1"
}

func postInstallCapabilitySupported(c map[string]any) bool {
	feature, ok := c["applicationPostInstall"].(map[string]any)
	return ok && (c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha12" || c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha13") &&
		closedKeys(feature, "protocol", "packageManifestVersion", "planContract", "manifestContract") &&
		feature["protocol"] == "ApplicationPostInstall/v1alpha1" &&
		feature["packageManifestVersion"] == "platform.installer/application-package/v1alpha3" &&
		feature["planContract"] == "platform.installer/plan/v1alpha9" &&
		feature["manifestContract"] == "platform.installer/execution-manifest/v1alpha7"
}

func applicationProgressCapabilitySupported(c map[string]any) bool {
	feature, ok := c["applicationProgress"].(map[string]any)
	return ok && c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha13" &&
		closedKeys(feature, "protocol", "planContract") &&
		feature["protocol"] == "ApplicationProgress/v1alpha1" && feature["planContract"] == "platform.installer/plan/v1alpha10"
}

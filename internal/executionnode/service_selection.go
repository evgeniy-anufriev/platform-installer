package executionnode

import (
	"context"
	"slices"
)

const serviceSelectionRequestVersion = "platform.installer/execution-runtime/v1alpha8"

type serviceSelectionKey struct{}

// WithServiceSelection binds invocation selection without editing project data.
func WithServiceSelection(ctx context.Context, skipped []string) context.Context {
	return context.WithValue(ctx, serviceSelectionKey{}, slices.Clone(skipped))
}
func serviceSelection(ctx context.Context) []string {
	value, _ := ctx.Value(serviceSelectionKey{}).([]string)
	return slices.Clone(value)
}
func serviceSelectionCapabilitySupported(c map[string]any) bool {
	feature, ok := c["serviceSelection"].(map[string]any)
	return ok && c["apiVersion"] == "platform.installer/execution-capabilities/v1alpha14" &&
		contains(c["deploymentPlanRequestVersions"], serviceSelectionRequestVersion) &&
		closedKeys(feature, "protocol", "planContract", "manifestContract") &&
		feature["protocol"] == "ServiceSelection/v1alpha1" &&
		feature["planContract"] == "platform.installer/plan/v1alpha11" &&
		feature["manifestContract"] == "platform.installer/execution-manifest/v1alpha8"
}

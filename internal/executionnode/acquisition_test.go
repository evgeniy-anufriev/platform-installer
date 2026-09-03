package executionnode

import (
	"context"
	"errors"
	"platform-installer/internal/executionbundle"
	"strings"
	"testing"
)

type failingAcquisitionSource struct{}

func (failingAcquisitionSource) InspectAcquisitionSource(context.Context, Node) (AcquisitionEnvironment, error) {
	return AcquisitionEnvironment{OS: "redos", Version: "8.0", Architecture: "x86_64", RepositorySource: "approved", Trusted: true}, nil
}
func (failingAcquisitionSource) AcquireRuntimeClosure(context.Context, Node, AcquisitionEnvironment, string) error {
	return errors.New("repository unavailable")
}

type unusedBuilder struct{}

func (unusedBuilder) Build(context.Context, string, string, string, string) (executionbundle.Verified, error) {
	panic("builder must not run")
}

func TestAcquisitionFailureDoesNotPublishCache(t *testing.T) {
	cache := executionbundle.Cache{Root: t.TempDir()}
	service := NewAcquisitionService(failingAcquisitionSource{}, unusedBuilder{}, cache)
	if _, err := service.AcquireExecutionRuntime(context.Background(), testNode(), "1"); err == nil || !strings.HasPrefix(err.Error(), "EXECUTION_RUNTIME_CLOSURE_FAILED") {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, err := cache.Resolve("", executionbundle.Platform{OS: "redos", Version: "8.0", Architecture: "x86_64"}); err == nil {
		t.Fatal("failed acquisition published a bundle")
	}
}

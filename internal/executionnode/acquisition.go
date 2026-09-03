package executionnode

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"platform-installer/internal/executionbundle"
)

type AcquisitionEnvironment struct {
	OS               string
	Version          string
	Architecture     string
	RepositorySource string
	Trusted          bool
}

type RuntimeAcquisition struct {
	Environment   AcquisitionEnvironment
	BundleVersion string
	RuntimeInput  string
}

// AcquisitionSource owns repository-aware closure resolution. Its implementation
// is explicit and separate from Transport, so Prepare cannot reach it.
type AcquisitionSource interface {
	InspectAcquisitionSource(context.Context, Node) (AcquisitionEnvironment, error)
	AcquireRuntimeClosure(context.Context, Node, AcquisitionEnvironment, string) error
}

// BundleBuilder is intentionally capability-based. Production builders must
// implement RemoteBundleBuilder; the local Build capability remains only for
// isolated compatibility tests and is never selected by the CLI.
type BundleBuilder interface{}

type RemoteBundleBuilder interface {
	BuildOnExecutionNode(context.Context, Node, string, string, string) (string, error)
}

type AcquisitionService struct {
	source  AcquisitionSource
	builder BundleBuilder
	cache   executionbundle.Cache
}

func NewAcquisitionService(source AcquisitionSource, builder BundleBuilder, cache executionbundle.Cache) *AcquisitionService {
	return &AcquisitionService{source: source, builder: builder, cache: cache}
}

func (s *AcquisitionService) InspectAcquisitionSource(ctx context.Context, node Node) (AcquisitionEnvironment, error) {
	environment, err := s.source.InspectAcquisitionSource(ctx, node)
	if err != nil {
		return AcquisitionEnvironment{}, err
	}
	if !environment.Trusted || environment.RepositorySource == "" || environment.OS == "" || environment.Version == "" || environment.Architecture == "" {
		return AcquisitionEnvironment{}, errors.New("EXECUTION_ACQUISITION_SOURCE_UNTRUSTED")
	}
	return environment, nil
}

func (s *AcquisitionService) AcquireExecutionRuntime(ctx context.Context, node Node, bundleVersion string) (executionbundle.Verified, error) {
	environment, err := s.InspectAcquisitionSource(ctx, node)
	if err != nil {
		return executionbundle.Verified{}, err
	}
	if bundleVersion == "" {
		return executionbundle.Verified{}, errors.New("EXECUTION_ACQUISITION_VERSION_REQUIRED")
	}
	parent, err := os.MkdirTemp("", "platform-installer-acquire-")
	if err != nil {
		return executionbundle.Verified{}, err
	}
	defer os.RemoveAll(parent)
	input := filepath.Join(parent, "runtime-input")
	output := filepath.Join(parent, "bundle")
	if err := os.MkdirAll(input, 0o700); err != nil {
		return executionbundle.Verified{}, err
	}
	if err := s.source.AcquireRuntimeClosure(ctx, node, environment, input); err != nil {
		return executionbundle.Verified{}, fmt.Errorf("EXECUTION_RUNTIME_CLOSURE_FAILED: %w", err)
	}
	bundleRoot := output
	if remoteBuilder, ok := s.builder.(RemoteBundleBuilder); ok {
		bundleRoot, err = remoteBuilder.BuildOnExecutionNode(ctx, node, input, bundleVersion, "")
		if bundleRoot != "" {
			defer os.RemoveAll(bundleRoot)
		}
	} else {
		localBuilder, ok := s.builder.(interface {
			Build(context.Context, string, string, string, string) (executionbundle.Verified, error)
		})
		if !ok {
			return executionbundle.Verified{}, errors.New("EXECUTION_REMOTE_BUNDLE_BUILDER_REQUIRED")
		}
		_, err = localBuilder.Build(ctx, input, output, bundleVersion, "")
	}
	if err != nil {
		return executionbundle.Verified{}, fmt.Errorf("EXECUTION_BUNDLE_BUILD_FAILED: %w", err)
	}
	bundle, err := executionbundle.ValidateRoot(bundleRoot)
	if err != nil {
		return executionbundle.Verified{}, fmt.Errorf("EXECUTION_BUNDLE_BUILD_FAILED: %w", err)
	}
	published, err := s.cache.Publish(bundle.Root)
	if err != nil {
		return executionbundle.Verified{}, errors.New("EXECUTION_BUNDLE_PUBLICATION_FAILED")
	}
	return published, nil
}

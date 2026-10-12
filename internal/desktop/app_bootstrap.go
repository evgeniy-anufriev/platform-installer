package desktop

import (
	"context"
	"errors"
	"os"
	"path/filepath"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/projectlifecycle"
)

type LaunchSettings struct {
	Address, User, Identity, KnownHosts, Fingerprint string
	Port                                             uint
	Bundle                                           string
}

type desktopIdentity struct{ path string }

func (i desktopIdentity) IdentityFile(string) (string, error) {
	if i.path == "" {
		return "", errors.New("EXECUTION_NODE_NOT_CONFIGURED")
	}
	return i.path, nil
}

func newConfiguredApp(settings LaunchSettings, dialogs DialogProvider, events ApplicationEventPublisher) (*App, error) {
	bundleRoot := resolveBundleRoot(settings.Bundle)
	var reader interface {
		BuildSnapshot(context.Context, string) (*coreadapter.Snapshot, error)
	} = unavailableProjectReader{}
	appOptions := []AppOption{WithDialogProvider(dialogs), WithApplicationEventPublisher(events), WithAvailableExecutionBundle(bundleRoot)}
	if executable, err := os.Executable(); err == nil {
		appOptions = append(appOptions, WithBundleCacheRoot(bundleCacheDirectory(executable)))
	}
	sources := map[string]string{}
	if bundleRoot != "" {
		if _, err := executionbundle.ValidateRoot(bundleRoot); err == nil {
			sources[projectlifecycle.DefaultCompatibilitySourceID] = bundleRoot
		}
	}
	configuredNode := settings.Address != "" && settings.User != "" && settings.Identity != "" && settings.KnownHosts != "" && settings.Fingerprint != "" && bundleRoot != "" && settings.Port > 0 && settings.Port <= 65535
	if configuredNode {
		if verified, err := executionbundle.ValidateRoot(bundleRoot); err == nil {
			node := executionnode.Node{ID: "desktop-" + settings.Address, Address: settings.Address, User: settings.User, Port: uint16(settings.Port), CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: settings.KnownHosts, Fingerprint: settings.Fingerprint}}
			release := map[string]any{"bundleDigest": verified.Digest, "coreVersion": verified.Manifest.CoreVersion, "catalogDigest": verified.Manifest.CatalogDigest, "planningProtocol": executionbundle.ProtocolVersion}
			transport := executionnode.OpenSSHTransport{Identity: desktopIdentity{settings.Identity}}
			projectReadBinding := projectReader{transport: transport, node: node, runtimeRelease: release}
			planService := executionnode.NewExecutionService(transport, transport)
			reader = projectReadBinding
			appOptions = append(appOptions, WithTrustedExecutionNodeBinding(executionNodeBinding{node: node, reader: projectReadBinding, service: executionnode.NewService(transport), plans: planService, bundleRoot: bundleRoot}))
		}
		appOptions = append(appOptions, WithExplicitExecutionNode("desktop-"+settings.Address, settings.Address))
	}
	applicationConfig, applicationConfigErr := loadApplicationConfig()
	appOptions = append(appOptions, WithApplicationConfig(applicationConfig, applicationConfigErr))
	app := NewApp(reader, projectlifecycle.NewService(sources), appOptions...)
	if err := configureQASecretFileSelection(app); err != nil {
		return nil, err
	}
	return app, nil
}

func loadApplicationConfig() (appconfig.Config, error) {
	workingDirectory, _ := os.Getwd()
	executable, _ := os.Executable()
	path, err := appconfig.ResolveDevelopmentPath(workingDirectory, executable)
	if err != nil {
		return appconfig.Config{}, err
	}
	return appconfig.Load(path)
}

func resolveBundleRoot(explicit string) string {
	if explicit != "" {
		return explicit
	}
	executable, err := os.Executable()
	if err != nil {
		return ""
	}
	cacheRoot := bundleCacheDirectory(executable)
	if found := verifiedBundleInCache(cacheRoot); found != "" {
		return found
	}
	return verifiedBundleInCache(filepath.Join(filepath.Dir(cacheRoot), "bundle"))
}

func verifiedBundleInCache(cacheRoot string) string {
	entries, err := os.ReadDir(cacheRoot)
	if err != nil {
		return ""
	}
	var found string
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		candidate := filepath.Join(cacheRoot, entry.Name())
		if _, err := executionbundle.ValidateRoot(candidate); err != nil {
			continue
		}
		if found != "" {
			return ""
		}
		found = candidate
	}
	return found
}

func bundleCacheDirectory(executable string) string {
	return filepath.Clean(filepath.Join(filepath.Dir(executable), "..", "..", "cache"))
}

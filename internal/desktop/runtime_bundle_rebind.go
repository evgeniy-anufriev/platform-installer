package desktop

import (
	"crypto/rand"
	"encoding/hex"
	"os"
	"path/filepath"
	"time"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

// The source path and project root are private to Go. React receives only an
// opaque, short-lived confirmation token and integrity-checked metadata.
type runtimeBundlePreview struct {
	id, source, projectRoot, revision                string
	oldArtifact, oldCatalog, newArtifact, newCatalog string
	expires                                          time.Time
}

type RuntimeBundleUpdateResult struct {
	Status                string            `json:"status"`
	PreviewID             string            `json:"previewId,omitempty"`
	CurrentArtifactDigest string            `json:"currentArtifactDigest,omitempty"`
	CurrentCatalogDigest  string            `json:"currentCatalogDigest,omitempty"`
	NewArtifactDigest     string            `json:"newArtifactDigest,omitempty"`
	NewCatalogDigest      string            `json:"newCatalogDigest,omitempty"`
	BundleVersion         string            `json:"bundleVersion,omitempty"`
	CoreVersion           string            `json:"coreVersion,omitempty"`
	ProjectRevision       string            `json:"projectRevision,omitempty"`
	Error                 *ProjectOpenError `json:"error,omitempty"`
}

func bundleUpdateError(status, code string) RuntimeBundleUpdateResult {
	return RuntimeBundleUpdateResult{Status: status, Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func (a *App) ChooseRuntimeBundleUpdate() RuntimeBundleUpdateResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.bundlePreview = nil
	if a.current.Status != "OPEN" || a.current.Classification != projectlifecycle.ClassificationManaged || a.current.Project == nil || a.bundleCacheRoot == "" || a.activeSession != "" || a.startInFlight || a.startOutcomeUnknown || a.runtimeUpdateInFlight {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_UPDATE_UNAVAILABLE")
	}
	if !a.knownRunsTerminalLocked() {
		return bundleUpdateError("BLOCKED", "INSTALLATION_RUN_ACTIVE")
	}
	root := a.current.Root
	revision, err := installer.ProjectRevision(root)
	if err != nil || a.current.Managed == nil || revision != a.current.Managed.ProjectRevision {
		return bundleUpdateError("BLOCKED", "PROJECT_CHANGED")
	}
	old, err := installer.ReadRuntimeLockSet(root)
	if err != nil {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_UPDATE_UNAVAILABLE")
	}
	source := filepath.Join(root, "bundle")
	sourceInfo, err := os.Lstat(source)
	if os.IsNotExist(err) {
		return RuntimeBundleUpdateResult{Status: "NOT_FOUND"}
	} else if err != nil || !sourceInfo.IsDir() || sourceInfo.Mode()&os.ModeSymlink != 0 {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_INVALID")
	}
	verified, err := executionbundle.ValidateRoot(source)
	if err != nil {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_INVALID")
	}
	if verified.Digest == old.ArtifactDigest {
		return RuntimeBundleUpdateResult{Status: "UNCHANGED", CurrentArtifactDigest: old.ArtifactDigest, CurrentCatalogDigest: old.CatalogDigest}
	}
	var token [16]byte
	if _, err := rand.Read(token[:]); err != nil {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_UPDATE_UNAVAILABLE")
	}
	id := hex.EncodeToString(token[:])
	a.bundlePreview = &runtimeBundlePreview{id: id, source: verified.Root, projectRoot: root, revision: revision, oldArtifact: old.ArtifactDigest, oldCatalog: old.CatalogDigest, newArtifact: verified.Digest, newCatalog: verified.Manifest.CatalogDigest, expires: time.Now().Add(10 * time.Minute)}
	return RuntimeBundleUpdateResult{Status: "PREVIEW", PreviewID: id, CurrentArtifactDigest: old.ArtifactDigest, CurrentCatalogDigest: old.CatalogDigest, NewArtifactDigest: verified.Digest, NewCatalogDigest: verified.Manifest.CatalogDigest, BundleVersion: verified.Manifest.BundleVersion, CoreVersion: verified.Manifest.CoreVersion, ProjectRevision: revision}
}

func (a *App) ConfirmRuntimeBundleUpdate(previewID string) RuntimeBundleUpdateResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	p := a.bundlePreview
	a.bundlePreview = nil // one use, including a failed attempt
	if p == nil || previewID == "" || previewID != p.id || time.Now().After(p.expires) || a.current.Status != "OPEN" || a.current.Root != p.projectRoot || a.activeSession != "" || a.startInFlight || a.startOutcomeUnknown || a.runtimeUpdateInFlight || a.bundleCacheRoot == "" {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_PREVIEW_STALE")
	}
	if !a.knownRunsTerminalLocked() {
		return bundleUpdateError("BLOCKED", "INSTALLATION_RUN_ACTIVE")
	}
	revision, err := installer.ProjectRevision(p.projectRoot)
	if err != nil || revision != p.revision {
		return bundleUpdateError("BLOCKED", "PROJECT_CHANGED")
	}
	current, err := installer.ReadRuntimeLockSet(p.projectRoot)
	if err != nil || current.ArtifactDigest != p.oldArtifact || current.CatalogDigest != p.oldCatalog {
		return bundleUpdateError("BLOCKED", "PROJECT_CHANGED")
	}
	sourceInfo, err := os.Lstat(p.source)
	if err != nil || !sourceInfo.IsDir() || sourceInfo.Mode()&os.ModeSymlink != 0 {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_CHANGED")
	}
	verified, err := executionbundle.ValidateRoot(p.source)
	if err != nil || verified.Digest != p.newArtifact || verified.Manifest.CatalogDigest != p.newCatalog {
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_CHANGED")
	}
	a.runtimeUpdateInFlight = true
	defer func() { a.runtimeUpdateInFlight = false }()
	publish := a.bundlePublisher
	if publish == nil {
		publish = (executionbundle.Cache{Root: a.bundleCacheRoot}).Publish
	}
	published, publishErr := publish(verified.Root)
	if publishErr != nil {
		// Publish may have renamed a different valid source and pruned the
		// previous cache root before returning an error. Never retain a root
		// that no longer verifies, regardless of the digest now in the cache.
		if a.availableBundleRoot == "" {
			a.switchPublishedBundleLocked("")
		} else if _, err := executionbundle.ValidateRoot(a.availableBundleRoot); err != nil {
			a.switchPublishedBundleLocked("")
		}
		return bundleUpdateError("BLOCKED", "RUNTIME_BUNDLE_PUBLICATION_FAILED")
	}
	// The source can change during copy. Only the exact previewed, verified
	// bytes authorize the project CAS, even if another valid bundle got copied.
	a.switchPublishedBundleLocked(published.Root)
	if published.Digest != p.newArtifact || published.Manifest.CatalogDigest != p.newCatalog {
		return bundleUpdateError("PUBLISHED_NOT_BOUND", "RUNTIME_BUNDLE_CHANGED")
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	_, err = installer.NewBackend(nil).UpdateRuntimeLockSet(ctx, installer.RuntimeLockSetUpdateRequest{ProjectRoot: p.projectRoot, ExpectedProjectRevision: p.revision, ExpectedOldArtifactDigest: p.oldArtifact, ExpectedOldCatalogDigest: p.oldCatalog, NewDigest: p.newArtifact, NewBundleRoot: published.Root})
	if err != nil {
		return bundleUpdateError("PUBLISHED_NOT_BOUND", projectErrorCode(err))
	}
	// Never label an uncertain post-commit refresh as rollback. The on-disk
	// locks are authoritative and OpenProject can safely be retried.
	opened, err := a.lifecycle.OpenProject(ctx, p.projectRoot)
	if err != nil || opened.Project == nil || opened.Catalog == nil || opened.Catalog.Status != "READY" || opened.Project.Source.BundleDigest != p.newArtifact || opened.Project.Source.CatalogDigest != p.newCatalog {
		return bundleUpdateError("BOUND_REFRESH_REQUIRED", "RUNTIME_BUNDLE_REOPEN_FAILED")
	}
	managed, err := installer.ReadManagedProjectViewWithCatalog(p.projectRoot, opened.Catalog)
	if err != nil {
		return bundleUpdateError("BOUND_REFRESH_REQUIRED", "RUNTIME_BUNDLE_REOPEN_FAILED")
	}
	a.secrets.Clear()
	a.current = ProjectOpenResult{Status: "OPEN", Root: opened.Root, Classification: opened.Classification, Project: opened.Project, Catalog: opened.Catalog, Managed: managed, Verification: notVerified(), Counts: opened.Counts, Diagnostics: a.managedServerTypeDiagnostics(managed)}
	a.bindExecutionLocked(opened.Root, opened.Project, managedSnapshotHosts(managed))
	return RuntimeBundleUpdateResult{Status: "UPDATED", NewArtifactDigest: p.newArtifact, NewCatalogDigest: p.newCatalog, ProjectRevision: managed.ProjectRevision}
}

func (a *App) switchPublishedBundleLocked(root string) {
	a.invalidateDynamicBindingLocked()
	a.binding = nil // explicit startup release also names the previous bundle
	a.reader = unavailableProjectReader{}
	a.availableBundleRoot = root
	if root == "" {
		a.lifecycle = projectlifecycle.NewService(nil)
	} else {
		a.lifecycle = projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: root})
	}
	a.current.Catalog = nil
	a.current.Managed = nil
	a.current.Snapshot = nil
	a.execution.setStatus(executionNodeNotPrepared)
	a.continuation = nil
	a.installationPlanID = ""
	a.installationGeneration++
	a.clearInstallationRunsLocked()
	a.current.Verification = notVerified()
	a.clearRuntimeSecretDescriptorEvidenceLocked()
}

func (a *App) knownRunsTerminalLocked() bool {
	if a.recoveredCancelUnconfirmed && a.recoveredRun != nil {
		return false
	}
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return false
	}
	record, err := readLocalRunRecord(a.localRunRecordRoot, a.current.Root, a.current.Project.ID)
	if err != nil {
		return false
	}
	if record == nil {
		return len(a.installationRuns.runIDs()) == 0
	}
	if record.State == "TERMINAL" {
		return true
	}
	if record.State != "RUNNING" || record.RunID == "" {
		return false
	}
	binding, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil || !sameLocalRunNode(*record, binding.node) {
		return false
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return false
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	run, err := client.GetExecution(ctx, binding.node, record.RunID)
	if err != nil || run.RunID != record.RunID || run.ProjectIdentity != record.ProjectID || !rebindTerminalRun(run.State) {
		return false
	}
	record.State, record.TerminalState = "TERMINAL", run.State
	if writeLocalRunRecord(a.localRunRecordRoot, *record) != nil {
		return false
	}
	a.installationRuns.finishMonitor(record.RunID, &run)
	a.secrets.ReleaseExecutionIdentityForRun(record.RunID)
	return true
}

func sameLocalRunNode(record localRunRecord, node executionnode.Node) bool {
	return record.NodeID == node.ID && record.NodeAddress == node.Address && record.NodePort == node.Port && record.NodeUser == node.User && record.HostKeyFingerprint == node.HostKey.Fingerprint
}

func rebindTerminalRun(state string) bool {
	switch state {
	case "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "CORRUPT_ORPHANED":
		return true
	default:
		return false
	}
}

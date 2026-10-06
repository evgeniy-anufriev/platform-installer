package main

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func rebindTestBundle(t *testing.T, version string) string {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "catalog"), 0o700); err != nil {
		t.Fatal(err)
	}
	catalog := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata:\n      id: kafka\n      version: 1.0.0\n      displayName: Kafka\n    modes:\n      single:\n        displayName: Single\n        memberRoles: [broker]\n        placement:\n          minMembers: 1\n          distinctHosts: false\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	if err := os.WriteFile(filepath.Join(root, "catalog", "service-catalog.yml"), []byte(catalog), 0o600); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(catalog))
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: " + version + "\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: catalog/service-catalog.yml\n    sha256: sha256:" + hex.EncodeToString(sum[:]) + "\n    size: " + strconv.Itoa(len(catalog)) + "\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	return root
}

func rebindTestApp(t *testing.T) (*App, string, string) {
	t.Helper()
	oldBundleRoot := rebindTestBundle(t, "old")
	parent := t.TempDir()
	root := filepath.Join(parent, "project")
	service := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: oldBundleRoot})
	app := NewApp(unavailableProjectReader{}, service, testApplicationConfig(), WithAvailableExecutionBundle(oldBundleRoot), WithBundleCacheRoot(filepath.Join(t.TempDir(), "cache")), WithLocalRunRecordRoot(filepath.Join(t.TempDir(), "run-records")))
	created := app.CreateProject(projectlifecycle.CreateProjectRequest{ProjectRoot: root, DisplayName: "Rebind test", CompatibilitySourceID: projectlifecycle.DefaultCompatibilitySourceID})
	if created.Status != "OPEN" {
		t.Fatalf("create=%+v", created)
	}
	started := app.StartEditSession()
	if started.Session == nil {
		t.Fatalf("edit=%+v", started)
	}
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("append=%+v", appended)
	}
	reviewed := app.ReviewStructuralEditSession(started.Session.SessionID)
	if reviewed.Plan == nil || !reviewed.Plan.SaveAllowed {
		t.Fatalf("review=%+v", reviewed)
	}
	committed := app.CommitStructuralEditPlan(started.Session.SessionID, reviewed.Plan.PlanID)
	if committed.Commit == nil || committed.Status != "COMMITTED" {
		t.Fatalf("commit=%+v", committed)
	}
	return app, root, created.Project.Source.BundleDigest
}

func placeRebindTestBundle(t *testing.T, root string) {
	t.Helper()
	newBundleRoot := rebindTestBundle(t, "updated")
	if err := os.Rename(newBundleRoot, filepath.Join(root, "bundle")); err != nil {
		t.Fatal(err)
	}
}

func TestRuntimeBundlePreviewIsReadOnlyAndUsesProjectBundle(t *testing.T) {
	app, root, oldDigest := rebindTestApp(t)
	if got := app.ChooseRuntimeBundleUpdate(); got.Status != "NOT_FOUND" {
		t.Fatalf("no bundle=%+v", got)
	}
	placeRebindTestBundle(t, root)
	before, err := os.ReadFile(filepath.Join(root, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	preview := app.ChooseRuntimeBundleUpdate()
	if preview.Status != "PREVIEW" || preview.CurrentArtifactDigest != oldDigest || preview.NewArtifactDigest == oldDigest || preview.PreviewID == "" || preview.BundleVersion != "updated" {
		t.Fatalf("preview=%+v", preview)
	}
	after, err := os.ReadFile(filepath.Join(root, "project.yml"))
	if err != nil || string(after) != string(before) {
		t.Fatalf("preview mutated project: %v", err)
	}
	if got := app.ConfirmRuntimeBundleUpdate("wrong-token"); got.Status != "BLOCKED" {
		t.Fatalf("wrong token=%+v", got)
	}
}

func TestRuntimeBundleUpdateBlocksPendingStartAndUnsafeSource(t *testing.T) {
	app, root, _ := rebindTestApp(t)
	placeRebindTestBundle(t, root)
	app.startInFlight = true
	if got := app.ChooseRuntimeBundleUpdate(); got.Status != "BLOCKED" {
		t.Fatalf("pending start=%+v", got)
	}
	app.startInFlight = false
	storeRoot, record := testLocalRunRecord(t)
	app.localRunRecordRoot = storeRoot
	canonical, err := canonicalRunProjectRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	record.ProjectRoot, record.ProjectID = canonical, app.current.Project.ID
	if err := writeLocalRunRecord(storeRoot, record); err != nil {
		t.Fatal(err)
	}
	if got := app.ChooseRuntimeBundleUpdate(); got.Status != "BLOCKED" {
		t.Fatalf("unknown start=%+v", got)
	}
}

func TestOrphanRecoveryNeverOffersCancelForPendingWithoutRunID(t *testing.T) {
	app, root, _ := rebindTestApp(t)
	storeRoot, record := testLocalRunRecord(t)
	app.localRunRecordRoot = storeRoot
	canonical, err := canonicalRunProjectRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	record.ProjectRoot, record.ProjectID = canonical, app.current.Project.ID
	if err := writeLocalRunRecord(storeRoot, record); err != nil {
		t.Fatal(err)
	}
	if got := app.InspectOrphanRun(); got.Status != "UNKNOWN" || got.RecoveryID != "" {
		t.Fatalf("pending without run ID exposed cancellation: %+v", got)
	}
	if got := app.CancelOrphanRun("made-up-token"); got.Status != "BLOCKED" {
		t.Fatalf("unverified cancellation=%+v", got)
	}
}

func TestLocalRunNodeIdentityRequiresOriginalHostAndFingerprint(t *testing.T) {
	_, record := testLocalRunRecord(t)
	node := executionnode.Node{ID: record.NodeID, Address: record.NodeAddress, Port: record.NodePort, User: record.NodeUser, HostKey: executionnode.HostKeyPolicy{Fingerprint: record.HostKeyFingerprint}}
	if !sameLocalRunNode(record, node) {
		t.Fatal("original node rejected")
	}
	node.HostKey.Fingerprint = "SHA256:other"
	if sameLocalRunNode(record, node) {
		t.Fatal("changed host fingerprint accepted")
	}
	node.HostKey.Fingerprint = record.HostKeyFingerprint
	node.Address = "192.0.2.99"
	if sameLocalRunNode(record, node) {
		t.Fatal("changed node address accepted")
	}
}

func TestRuntimeBundleConfirmBindsOnlyThePreviewedDigest(t *testing.T) {
	app, root, oldDigest := rebindTestApp(t)
	placeRebindTestBundle(t, root)
	preview := app.ChooseRuntimeBundleUpdate()
	if preview.Status != "PREVIEW" {
		t.Fatalf("preview=%+v", preview)
	}
	result := app.ConfirmRuntimeBundleUpdate(preview.PreviewID)
	if result.Status != "UPDATED" {
		t.Fatalf("confirm=%+v error=%+v", result, result.Error)
	}
	lock, err := installer.ReadRuntimeLockSet(root)
	if err != nil || lock.ArtifactDigest != preview.NewArtifactDigest || lock.ArtifactDigest == oldDigest || lock.CatalogDigest != preview.NewCatalogDigest {
		t.Fatalf("new lock=%+v err=%v", lock, err)
	}
	if retry := app.ConfirmRuntimeBundleUpdate(preview.PreviewID); retry.Status != "BLOCKED" {
		t.Fatalf("one-use preview accepted twice: %+v", retry)
	}
}

func TestRuntimeBundleConfirmRejectsChangedSourceWithoutChangingProject(t *testing.T) {
	app, root, oldDigest := rebindTestApp(t)
	placeRebindTestBundle(t, root)
	preview := app.ChooseRuntimeBundleUpdate()
	if preview.Status != "PREVIEW" {
		t.Fatalf("preview=%+v", preview)
	}
	manifest := filepath.Join(root, "bundle", "manifest.yaml")
	content, err := os.ReadFile(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(manifest, []byte(strings.Replace(string(content), "bundleVersion: updated", "bundleVersion: changed", 1)), 0o600); err != nil {
		t.Fatal(err)
	}
	if result := app.ConfirmRuntimeBundleUpdate(preview.PreviewID); result.Status != "BLOCKED" {
		t.Fatalf("changed source=%+v", result)
	}
	lock, err := installer.ReadRuntimeLockSet(root)
	if err != nil || lock.ArtifactDigest != oldDigest {
		t.Fatalf("old lock changed=%+v err=%v", lock, err)
	}
}

func TestRuntimeBundlePublishFailureAfterDifferentDigestPrunesOldRoot(t *testing.T) {
	app, root, oldDigest := rebindTestApp(t)
	oldPublished, err := (executionbundle.Cache{Root: app.bundleCacheRoot}).Publish(app.availableBundleRoot)
	if err != nil {
		t.Fatal(err)
	}
	app.availableBundleRoot = oldPublished.Root
	app.lifecycle = projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: oldPublished.Root})
	placeRebindTestBundle(t, root)
	preview := app.ChooseRuntimeBundleUpdate()
	if preview.Status != "PREVIEW" {
		t.Fatalf("preview=%+v", preview)
	}
	app.bundlePublisher = func(source string) (executionbundle.Verified, error) {
		manifest := filepath.Join(source, "manifest.yaml")
		content, err := os.ReadFile(manifest)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(manifest, []byte(strings.Replace(string(content), "bundleVersion: updated", "bundleVersion: swapped", 1)), 0o600); err != nil {
			t.Fatal(err)
		}
		other, err := executionbundle.ValidateRoot(source)
		if err != nil || other.Digest == preview.NewArtifactDigest {
			t.Fatalf("replacement invalid or unchanged: %+v %v", other, err)
		}
		if err := os.Rename(source, filepath.Join(app.bundleCacheRoot, strings.TrimPrefix(other.Digest, "sha256:"))); err != nil {
			t.Fatal(err)
		}
		if err := os.Rename(oldPublished.Root, oldPublished.Root+".removed"); err != nil {
			t.Fatal(err)
		}
		return executionbundle.Verified{}, errors.New("injected post-publication cleanup failure")
	}
	result := app.ConfirmRuntimeBundleUpdate(preview.PreviewID)
	if result.Status != "BLOCKED" || result.Error == nil || result.Error.Code != "RUNTIME_BUNDLE_PUBLICATION_FAILED" {
		t.Fatalf("publish failure=%+v error=%+v", result, result.Error)
	}
	if app.availableBundleRoot != "" || app.current.Catalog != nil || app.current.Managed != nil || app.binding != nil {
		t.Fatalf("stale runtime binding retained after old root disappeared: root=%q", app.availableBundleRoot)
	}
	lock, err := installer.ReadRuntimeLockSet(root)
	if err != nil || lock.ArtifactDigest != oldDigest {
		t.Fatalf("project lock changed after failed publication: %+v %v", lock, err)
	}
	if got := app.OpenProject(root); got.Status != "OPEN" || got.Catalog == nil || got.Catalog.Status == "READY" {
		t.Fatalf("old project unexpectedly compatible after failed publish: %+v", got)
	}
}

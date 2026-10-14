package desktop

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"platform-installer/internal/executionnode"
)

// Separate from last-run: a library run must not erase the prior observation.
// No caller may use this record as execution authorization.
type localInfrastructureVerification struct {
	Version              int                                      `json:"version"`
	ProjectRoot          string                                   `json:"projectRoot"`
	ProjectID            string                                   `json:"projectId"`
	ExecutionNodeBinding string                                   `json:"executionNodeBinding"`
	RuntimeBundleDigest  string                                   `json:"runtimeBundleDigest"`
	ObservedAt           string                                   `json:"observedAt"`
	Verification         executionnode.InfrastructureVerification `json:"verification"`
}

const maxInfrastructureRecordBytes = 128 * 1024

// Cached observations always have UNKNOWN current availability. A fresh Core
// plan is returned separately by the adapter and is the only admission input.
type InfrastructureVerificationView struct {
	Availability string                                    `json:"availability"`
	ObservedAt   string                                    `json:"observedAt,omitempty"`
	Previous     *executionnode.InfrastructureVerification `json:"previous,omitempty"`
}

func infrastructureNodeBinding(node executionnode.Node) string {
	// Account changes cannot change infrastructure state. Host identity can.
	data, _ := json.Marshal([]any{node.ID, node.Address, node.Port, node.HostKey.Fingerprint})
	hash := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(hash[:])
}

func cachedInfrastructureVerification(store, root, projectID string, node executionnode.Node, bundle string) InfrastructureVerificationView {
	view := InfrastructureVerificationView{Availability: "UNKNOWN"}
	r, err := readLocalInfrastructureVerification(store, root, projectID, infrastructureNodeBinding(node), bundle)
	if err == nil && r != nil {
		view.ObservedAt, view.Previous = r.ObservedAt, &r.Verification
	}
	return view
}

func cacheInfrastructurePlan(store, root string, node executionnode.Node, plan executionnode.DeploymentPlan, observedAt time.Time) error {
	canonical, err := canonicalRunProjectRoot(root)
	if err != nil {
		return err
	}
	bundle, ok := plan.RuntimeRelease["bundleDigest"].(string)
	if !ok || plan.InfrastructureVerification == nil {
		return errors.New("INFRASTRUCTURE_CACHE_INVALID")
	}
	return writeLocalInfrastructureVerification(store, localInfrastructureVerification{Version: 1, ProjectRoot: canonical, ProjectID: plan.ProjectIdentity, ExecutionNodeBinding: infrastructureNodeBinding(node), RuntimeBundleDigest: bundle, ObservedAt: observedAt.UTC().Format(time.RFC3339Nano), Verification: *plan.InfrastructureVerification})
}

func defaultInfrastructureVerificationRoot() string {
	base, err := os.UserConfigDir()
	if err != nil || base == "" {
		return ""
	}
	return filepath.Join(base, "platform-installer", "infrastructure-verification")
}

func (r localInfrastructureVerification) valid() bool {
	if !strings.HasPrefix(r.RuntimeBundleDigest, "sha256:") || strings.ToLower(r.RuntimeBundleDigest) != r.RuntimeBundleDigest {
		return false
	}
	if _, err := hex.DecodeString(strings.TrimPrefix(r.RuntimeBundleDigest, "sha256:")); err != nil {
		return false
	}
	root, err := canonicalRunProjectRoot(r.ProjectRoot)
	if err != nil || root != r.ProjectRoot || r.Version != 1 || r.ProjectID == "" || len(r.ProjectID) > 128 || r.ExecutionNodeBinding == "" || len(r.ExecutionNodeBinding) > 256 || len(r.RuntimeBundleDigest) != 71 || !r.Verification.Validate() {
		return false
	}
	_, err = time.Parse(time.RFC3339, r.ObservedAt)
	return err == nil
}

func writeLocalInfrastructureVerification(store string, record localInfrastructureVerification) error {
	invalid := errors.New("INFRASTRUCTURE_CACHE_INVALID")
	if !record.valid() {
		return invalid
	}
	path, err := localRunRecordPath(store, record.ProjectRoot, record.ProjectID)
	if err != nil {
		return err
	}
	data, err := json.Marshal(record)
	if err != nil || len(data) > maxInfrastructureRecordBytes {
		return invalid
	}
	if err := os.MkdirAll(store, 0o700); err != nil {
		return errors.New("INFRASTRUCTURE_CACHE_UNAVAILABLE")
	}
	if err := safeLocalRunRecordRoot(store); err != nil {
		return err
	}
	if info, err := os.Lstat(path); err == nil && !info.Mode().IsRegular() {
		return invalid
	} else if err != nil && !errors.Is(err, os.ErrNotExist) {
		return invalid
	}
	return writeLocalOperationalRecord(store, path, data)
}

// A missing/corrupt record yields no observation. Availability is UNKNOWN even
// when the prior observation was PASS; refresh requires a new authoritative Build.
func readLocalInfrastructureVerification(store, projectRoot, projectID, nodeBinding, bundleDigest string) (*localInfrastructureVerification, error) {
	invalid := errors.New("INFRASTRUCTURE_CACHE_INVALID")
	path, err := localRunRecordPath(store, projectRoot, projectID)
	if err != nil {
		return nil, err
	}
	if err := safeLocalRunRecordRoot(store); err != nil {
		return nil, err
	}
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil || !info.Mode().IsRegular() || info.Size() < 2 || info.Size() > maxInfrastructureRecordBytes {
		return nil, invalid
	}
	data, err := os.ReadFile(path)
	if err != nil || len(data) > maxInfrastructureRecordBytes {
		return nil, invalid
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	var r localInfrastructureVerification
	root, rootErr := canonicalRunProjectRoot(projectRoot)
	if d.Decode(&r) != nil || d.Decode(new(any)) != io.EOF || !r.valid() || rootErr != nil || r.ProjectRoot != root || r.ProjectID != projectID || r.ExecutionNodeBinding != nodeBinding || r.RuntimeBundleDigest != bundleDigest {
		return nil, invalid
	}
	return &r, nil
}

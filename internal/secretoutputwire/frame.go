// Package secretoutputwire implements only the bounded confidential Fetch
// frame. It has no project, service, persistence or UI responsibilities.
package secretoutputwire

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"unicode/utf8"
)

const MaxFrameBytes = 65536

var ErrTransfer = errors.New("OUTPUT_TRANSFER_FAILED")

var (
	opaque     = regexp.MustCompile(`^[0-9a-f]{32}$`)
	project    = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,127}$`)
	deployment = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)
	run        = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
	digest     = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
)

// Binding is the expected identity from trusted local runtime context, never
// an identity inferred from the received frame itself.
type Binding struct {
	ProjectID, DeploymentID, PackageID, SourceRunID, RuntimeDigest string
	Generation                                                     int
}

type metadata struct {
	Protocol      string   `json:"protocol"`
	PackageID     string   `json:"packageId"`
	ProjectID     string   `json:"projectId"`
	DeploymentID  string   `json:"deploymentId"`
	SourceRunID   string   `json:"sourceRunId"`
	RuntimeDigest string   `json:"runtimeDigest"`
	Generation    int      `json:"generation"`
	State         string   `json:"state"`
	Entries       []string `json:"entries"`
}

// Consume validates the complete frame before invoking use. Token/shares are
// borrowed byte slices cleared on return, including callback failure. Callers
// must also establish a successful remote process exit before calling Consume.
// Transport and parse errors deliberately never include stream/error content.
func Consume(source io.Reader, expected Binding, use func(token, shares []byte) error) error {
	if source == nil || use == nil || !validBinding(expected) {
		return ErrTransfer
	}
	data, err := io.ReadAll(io.LimitReader(source, MaxFrameBytes+1))
	defer clear(data)
	if err != nil || len(data) < 16 || len(data) > MaxFrameBytes || string(data[:4]) != "SOD1" {
		return ErrTransfer
	}
	m := uint64(binary.BigEndian.Uint32(data[4:8]))
	t := uint64(binary.BigEndian.Uint32(data[8:12]))
	s := uint64(binary.BigEndian.Uint32(data[12:16]))
	if m < 1 || m > 8192 || t < 1 || t > 4096 || s < 1 || s > 32768 || 16+m+t+s != uint64(len(data)) {
		return ErrTransfer
	}
	header := data[16 : 16+m]
	if !utf8.Valid(header) || !uniqueFlatObject(header) || !exactMetadataKeys(header) {
		return ErrTransfer
	}
	var meta metadata
	decoder := json.NewDecoder(bytes.NewReader(header))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&meta) != nil || meta.Protocol != "SecretOutputDelivery/v1alpha1" || meta.State != "READY" ||
		len(meta.Entries) != 2 || meta.Entries[0] != "admin-token" || meta.Entries[1] != "unseal-shares" ||
		meta.ProjectID != expected.ProjectID || meta.DeploymentID != expected.DeploymentID ||
		meta.PackageID != expected.PackageID || meta.SourceRunID != expected.SourceRunID || meta.RuntimeDigest != expected.RuntimeDigest || meta.Generation != expected.Generation {
		return ErrTransfer
	}
	token, shares := data[16+m:16+m+t], data[16+m+t:]
	if !utf8.Valid(token) || !utf8.Valid(shares) || !json.Valid(shares) {
		return ErrTransfer
	}
	// Semantic shares validation belongs to the approved Vault input adapter.
	if use(token, shares) != nil {
		// The callback owns plaintext too: its error may contain that content.
		// Never propagate or wrap it across this confidential boundary.
		return ErrTransfer
	}
	return nil
}

func validBinding(b Binding) bool {
	return project.MatchString(b.ProjectID) && len(b.DeploymentID) <= 128 && deployment.MatchString(b.DeploymentID) &&
		opaque.MatchString(b.PackageID) && run.MatchString(b.SourceRunID) && digest.MatchString(b.RuntimeDigest) && b.Generation >= 1 && b.Generation <= 2147483647
}

// The metadata schema has a flat object with primitive values and one array.
// Checking duplicate keys here prevents JSON last-value-wins identity parsing.
func uniqueFlatObject(data []byte) bool {
	d := json.NewDecoder(bytes.NewReader(data))
	token, err := d.Token()
	if err != nil || token != json.Delim('{') {
		return false
	}
	seen := make(map[string]bool, 11)
	for d.More() {
		token, err = d.Token()
		key, ok := token.(string)
		if err != nil || !ok || seen[key] {
			return false
		}
		seen[key] = true
		var value json.RawMessage
		if d.Decode(&value) != nil {
			return false
		}
	}
	if _, err = d.Token(); err != nil {
		return false
	}
	_, err = d.Token()
	return err == io.EOF
}

func exactMetadataKeys(data []byte) bool {
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil || len(fields) != 9 {
		return false
	}
	for key := range fields {
		switch key {
		case "protocol", "packageId", "projectId", "deploymentId", "sourceRunId", "runtimeDigest", "generation", "state", "entries":
		default:
			return false
		}
	}
	return true
}

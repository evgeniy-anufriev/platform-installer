package coreadapter

import (
	"strings"
	"testing"
)

func TestDecodeSnapshotAcceptsLargeProjectionAndKeepsFiniteBoundary(t *testing.T) {
	const prefix = `{"status":"PASS","projectRevision":"sha256:a","snapshotFingerprint":"sha256:b","project":{"padding":"`
	const suffix = `"}}`
	for _, size := range []int{5 * 1024 * 1024, MaxSnapshotResponseBytes, MaxSnapshotResponseBytes + 1} {
		data := []byte(prefix + strings.Repeat("x", size-len(prefix)-len(suffix)) + suffix)
		snapshot, err := DecodeSnapshot(data)
		if size > MaxSnapshotResponseBytes {
			if err == nil || err.Error() != "PROJECT_SNAPSHOT_RESPONSE_INVALID" {
				t.Fatalf("oversized projection was not rejected: %v", err)
			}
			continue
		}
		if err != nil || len(snapshot.Raw) != size || snapshot.SnapshotFingerprint != "sha256:b" {
			t.Fatalf("valid projection size=%d was not preserved: %v", size, err)
		}
	}
}

func TestDecodeSnapshotKeepsOnlyStableConsumedFields(t *testing.T) {
	data := []byte(`{"status":"PASS","projectRevision":"sha256:a","snapshotFingerprint":"sha256:b","documents":[{"logicalPath":"inventory/hosts.yml","digest":"sha256:c","ownership":"USER_OWNED_READ_ONLY","revisionIncluded":true}],"serviceDeployments":{"postgres":{"serviceType":"postgresql"}},"futureField":{"ignored":true}}`)
	snapshot, err := DecodeSnapshot(data)
	if err != nil {
		t.Fatal(err)
	}
	if snapshot.ProjectRevision != "sha256:a" || snapshot.Documents[0].LogicalPath != "inventory/hosts.yml" || snapshot.ServiceDeployments["postgres"]["serviceType"] != "postgresql" {
		t.Fatalf("unexpected snapshot: %#v", snapshot)
	}
	if string(snapshot.Raw) != string(data) {
		t.Fatal("raw structured response was not retained")
	}
}

package coreadapter

import "testing"

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

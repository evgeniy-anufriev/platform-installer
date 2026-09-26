package secretoutputwire

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestRequestClosedOperations(t *testing.T) {
	for _, r := range []Request{
		{Protocol: Protocol, Operation: "GetCapabilities", ProjectID: "qa"},
		{Protocol: Protocol, Operation: "ListPending", ProjectID: "qa", Limit: 32},
		{Protocol: Protocol, Operation: "Fetch", ProjectID: "qa", PackageID: strings.Repeat("a", 32), ExpectedGeneration: 2147483647},
		{Protocol: Protocol, Operation: "Acknowledge", ProjectID: "qa", PackageID: strings.Repeat("a", 32), ExpectedGeneration: 1, ReceiptID: strings.Repeat("b", 32), CiphertextDigests: map[string]string{"admin-token": "sha256:" + strings.Repeat("c", 64), "unseal-shares": "sha256:" + strings.Repeat("d", 64)}},
	} {
		data, err := json.Marshal(r)
		if err != nil {
			t.Fatal(err)
		}
		decoded, err := DecodeRequest(data)
		if err != nil || decoded.Operation != r.Operation {
			t.Fatalf("%s: %v", r.Operation, err)
		}
	}
}

func TestRequestRejectsUnsafeOrAmbiguousInput(t *testing.T) {
	base := `{"protocol":"SecretOutputDelivery/v1alpha1","operation":"ListPending","projectId":"qa",`
	for _, data := range []string{
		base + `"limit":null}`, base + `"limit":0}`, base + `"limit":33}`, base + `"limit":true}`, base + `"limit":1.5}`,
		base + `"limit":1,"limit":2}`, base + `"limit":1,"cursor":null}`, base + `"limit":1,"path":"secret"}`,
		base + `"limit":1,"packageId":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`,
		`{"protocol":"SecretOutputDelivery/v1alpha1","operation":"GetCapabilities","projectId":"qa","limit":0}`,
		strings.Replace(base+`"limit":1}`, "v1alpha1", "v1alpha2", 1),
		base + `"limit":1} {}`, strings.Repeat(" ", MaxRequestBytes+1),
		base + `"limit":1,"projectId":"` + string([]byte{0xff}) + `"}`,
	} {
		if _, err := DecodeRequest([]byte(data)); err != ErrRequest {
			t.Fatal("unsafe input was admitted or exposed")
		}
	}
}

func TestRequestRejectsDuplicateReceiptDigest(t *testing.T) {
	r := Request{Protocol: Protocol, Operation: "Acknowledge", ProjectID: "qa", PackageID: strings.Repeat("a", 32), ExpectedGeneration: 1, ReceiptID: strings.Repeat("b", 32), CiphertextDigests: map[string]string{"admin-token": "sha256:" + strings.Repeat("c", 64), "unseal-shares": "sha256:" + strings.Repeat("d", 64)}}
	data, _ := json.Marshal(r)
	duplicate := strings.Replace(string(data), `"ciphertextDigests":{`, `"ciphertextDigests":{"admin-token":"sha256:`+strings.Repeat("e", 64)+`",`, 1)
	if _, err := DecodeRequest([]byte(duplicate)); err != ErrRequest {
		t.Fatal("duplicate digest admitted")
	}
}

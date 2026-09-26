package secretoutputwire

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

func fixture(t *testing.T) ([]byte, Binding) {
	t.Helper()
	b := Binding{"project-test", "vault-ha", strings.Repeat("a", 32), "installer-test", "sha256:" + strings.Repeat("b", 64), 1}
	m := metadata{"SecretOutputDelivery/v1alpha1", b.PackageID, b.ProjectID, b.DeploymentID, b.SourceRunID, b.RuntimeDigest, b.Generation, "READY", []string{"admin-token", "unseal-shares"}}
	header, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	token, shares := []byte("test-token"), []byte(`{"keys_base64":["test-share"]}`)
	data := make([]byte, 16)
	copy(data, "SOD1")
	binary.BigEndian.PutUint32(data[4:8], uint32(len(header)))
	binary.BigEndian.PutUint32(data[8:12], uint32(len(token)))
	binary.BigEndian.PutUint32(data[12:16], uint32(len(shares)))
	data = append(data, header...)
	data = append(data, token...)
	data = append(data, shares...)
	return data, b
}

func TestConsumeValidFrameAndClearsBorrowedSecrets(t *testing.T) {
	data, b := fixture(t)
	var borrowed []byte
	err := Consume(bytes.NewReader(data), b, func(token, shares []byte) error {
		if string(token) != "test-token" || !json.Valid(shares) {
			t.Fatal("invalid borrowed content")
		}
		borrowed = token
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
		t.Fatal("borrowed secret not cleared")
	}
}

func TestConsumeRejectsMalformedAndConflictingFrames(t *testing.T) {
	data, b := fixture(t)
	cases := map[string][]byte{"truncated": data[:len(data)-1], "trailing": append(append([]byte{}, data...), 1), "oversized": make([]byte, MaxFrameBytes+1)}
	bad := append([]byte{}, data...)
	binary.BigEndian.PutUint32(bad[8:12], 4097)
	cases["length"] = bad
	for name, input := range cases {
		t.Run(name, func(t *testing.T) {
			called := false
			err := Consume(bytes.NewReader(input), b, func([]byte, []byte) error { called = true; return nil })
			if !errors.Is(err, ErrTransfer) || called {
				t.Fatal("invalid frame admitted")
			}
		})
	}
	b.PackageID = strings.Repeat("c", 32)
	if err := Consume(bytes.NewReader(data), b, func([]byte, []byte) error { t.Fatal("identity mismatch admitted"); return nil }); !errors.Is(err, ErrTransfer) {
		t.Fatal("missing safe identity error")
	}
}

type failingReader struct{ done bool }

func (r *failingReader) Read(p []byte) (int, error) {
	if !r.done {
		r.done = true
		return copy(p, []byte("sensitive partial output")), nil
	}
	return 0, errors.New("sensitive transport diagnostic")
}

func TestConsumeTransportFailureHasNoContent(t *testing.T) {
	_, b := fixture(t)
	err := Consume(&failingReader{}, b, func([]byte, []byte) error { t.Fatal("partial content consumed"); return nil })
	if err != ErrTransfer {
		t.Fatalf("unsafe error type: %T", err)
	}
}

func TestConsumeCallbackFailureHasNoContentAndClearsBothBuffers(t *testing.T) {
	data, b := fixture(t)
	var borrowedToken, borrowedShares []byte
	err := Consume(bytes.NewReader(data), b, func(token, shares []byte) error {
		borrowedToken, borrowedShares = token, shares
		return errors.New(string(token) + string(shares))
	})
	if err != ErrTransfer || errors.Unwrap(err) != nil {
		t.Fatal("secret-bearing callback error propagated")
	}
	for _, borrowed := range [][]byte{borrowedToken, borrowedShares} {
		if len(borrowed) == 0 || !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
			t.Fatal("borrowed secret not cleared after callback failure")
		}
	}
}

func TestMetadataRejectsDuplicatesAndTrailingJSON(t *testing.T) {
	for _, data := range []string{`{"packageId":"a","packageId":"b"}`, `{"state":"READY"} {}`, `[]`} {
		if uniqueFlatObject([]byte(data)) {
			t.Fatal("ambiguous metadata admitted")
		}
	}
}

func TestConsumeCanonicalDeploymentAndExactMetadataKeys(t *testing.T) {
	for _, id := range []string{"vault-ha", "vault.ha", "vault_ha", strings.Repeat("a", 128), "1vault", "vault--ha", "vault/ha", "vault-", strings.Repeat("a", 129)} {
		data, b := fixture(t)
		n := int(binary.BigEndian.Uint32(data[4:8]))
		header := strings.Replace(string(data[16:16+n]), "vault-ha", id, 1)
		b.DeploymentID = id
		frame := append([]byte{}, data[:16]...)
		binary.BigEndian.PutUint32(frame[4:8], uint32(len(header)))
		frame = append(frame, []byte(header)...)
		frame = append(frame, data[16+n:]...)
		called := false
		err := Consume(bytes.NewReader(frame), b, func([]byte, []byte) error { called = true; return nil })
		valid := id == "vault-ha" || id == "vault.ha" || id == "vault_ha" || id == strings.Repeat("a", 128)
		if (err == nil) != valid || called != valid {
			t.Fatal("canonical deployment admission mismatch")
		}
	}
	for _, replacement := range []string{`"PROJECTID":`, `"PROJECTID":"project-test","projectId":`} {
		data, b := fixture(t)
		n := int(binary.BigEndian.Uint32(data[4:8]))
		header := strings.Replace(string(data[16:16+n]), `"projectId":`, replacement, 1)
		frame := append([]byte{}, data[:16]...)
		binary.BigEndian.PutUint32(frame[4:8], uint32(len(header)))
		frame = append(frame, []byte(header)...)
		frame = append(frame, data[16+n:]...)
		if Consume(bytes.NewReader(frame), b, func([]byte, []byte) error { t.Fatal("altered key admitted"); return nil }) != ErrTransfer {
			t.Fatal("missing safe rejection")
		}
	}
}

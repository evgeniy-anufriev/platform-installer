package secretfiles

import (
	"bytes"
	"errors"
	"testing"
)

func TestAgePasswordFileRoundTrip(t *testing.T) {
	password := []byte("correct horse battery staple")
	plain := []byte("vault token fixture")
	ciphertext, err := Encrypt(password, plain)
	if err != nil {
		t.Fatal("encrypt rejected valid input")
	}
	if len(ciphertext) > MaxEncryptedBytes || bytes.Contains(ciphertext, plain) {
		t.Fatal("ciphertext bound or confidentiality check failed")
	}
	got, err := Decrypt(password, ciphertext, 4096)
	if err != nil || !bytes.Equal(got, plain) {
		t.Fatal("age round-trip failed")
	}
	clear(got)
	if _, err := Decrypt([]byte("wrong password"), ciphertext, 4096); !errors.Is(err, ErrFile) {
		t.Fatal("wrong password did not fail safely")
	}
}

func TestAgeFileRejectsInvalidOrUnboundedInputs(t *testing.T) {
	for _, password := range [][]byte{nil, []byte{0xff}, bytes.Repeat([]byte("p"), MaxPasswordBytes+1)} {
		if _, err := Encrypt(password, []byte("secret")); !errors.Is(err, ErrFile) {
			t.Fatal("invalid password accepted")
		}
		if _, err := Decrypt(password, []byte("age-encryption.org/v1"), 4096); !errors.Is(err, ErrFile) {
			t.Fatal("invalid password accepted by decrypt")
		}
	}
	if _, err := Encrypt([]byte("valid"), nil); !errors.Is(err, ErrFile) {
		t.Fatal("empty plaintext accepted")
	}
	if _, err := Decrypt([]byte("valid"), []byte("plaintext"), 4096); !errors.Is(err, ErrFile) {
		t.Fatal("plaintext fallback accepted")
	}
	if _, err := Decrypt([]byte("valid"), []byte("x"), 0); !errors.Is(err, ErrFile) {
		t.Fatal("invalid plaintext bound accepted")
	}
	if _, err := Decrypt([]byte("valid"), bytes.Repeat([]byte("x"), MaxEncryptedBytes+1), 4096); !errors.Is(err, ErrFile) {
		t.Fatal("oversized ciphertext accepted")
	}
}

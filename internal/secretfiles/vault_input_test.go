package secretfiles

import (
	"errors"
	"strings"
	"testing"
)

func TestReadAdminTokenRawAndInitJSON(t *testing.T) {
	for _, input := range [][]byte{
		[]byte("root-token"),
		[]byte(`{"root_token":"root-token","keys":["must-not-escape"],"unseal_keys_b64":["also-secret"]}`),
	} {
		got, err := ReadVaultInput(PurposeAdminToken, input, nil)
		if err != nil || string(got.Token) != "root-token" || len(got.Shares) != 0 {
			t.Fatal("admin token input was not projected safely")
		}
		clear(got.Token)
	}
	for _, input := range [][]byte{
		nil,
		[]byte(`{"root_token":"first","root_token":"second"}`),
		[]byte(`{"root_token":7}`),
		[]byte(`{"root_token":""}`),
		[]byte(strings.Repeat("x", MaxTokenBytes+1)),
		{0xff},
	} {
		if _, err := ReadVaultInput(PurposeAdminToken, input, nil); !errors.Is(err, ErrFile) {
			t.Fatal("invalid token file accepted")
		}
	}
}

func TestReadUnsealSharesAcceptedContainers(t *testing.T) {
	inputs := []string{
		`{"keys":["share-a","share-b"]}`,
		`{"keys_base64":["c2hhcmUtYQ==","c2hhcmUtYg=="]}`,
		`{"unseal_keys_hex":["73686172652d61","73686172652d62"]}`,
		`{"unseal_keys_b64":["c2hhcmUtYQ==","c2hhcmUtYg=="]}`,
		`{"unseal_keys_hex":["73686172652d61","73686172652d62"],"unseal_keys_b64":["c2hhcmUtYQ==","c2hhcmUtYg=="]}`,
	}
	for _, input := range inputs {
		got, err := ReadVaultInput(PurposeUnsealShares, []byte(input), nil)
		if err != nil || len(got.Shares) != 2 {
			t.Fatal("approved shares container rejected")
		}
		for _, share := range got.Shares {
			clear(share)
		}
	}
}

func TestReadUnsealSharesRejectsAmbiguityDuplicatesAndBounds(t *testing.T) {
	valid := `{"keys":["share-a","share-b"]}`
	matchingHex := `{"unseal_keys_hex":["73686172652d61","73686172652d62"],"unseal_keys_b64":["c2hhcmUtYQ==","c2hhcmUtYg=="]}`
	mismatched := strings.Replace(matchingHex, "c2hhcmUtYg==", "b3RoZXI=", 1)
	for _, input := range []string{
		`{"keys":["a"],"keys_base64":["YQ=="]}`,
		`{"keys":["a"],"unseal_keys_hex":["61"]}`,
		`{"unseal_keys_hex":["61"],"unseal_keys_b64":["Yg=="]}`,
		`{"unseal_keys_hex":["zz"]}`,
		`{"unseal_keys_b64":["not-base64"]}`,
		`{"keys":["same","same"]}`,
		`{"outer":{"x":1,"x":2},"keys":["a"]}`,
		`{"keys":"not-an-array"}`,
		`{"keys":[]}`,
		`{"keys":[""]}`,
		`{"keys":["` + strings.Repeat("x", MaxShareBytes+1) + `"]}`,
		`{"keys":["a"],"keys":["b"]}`,
		mismatched,
	} {
		if _, err := ReadVaultInput(PurposeUnsealShares, []byte(input), nil); !errors.Is(err, ErrFile) {
			t.Fatal("invalid or ambiguous shares input accepted")
		}
	}
	if _, err := ReadVaultInput(PurposeUnsealShares, []byte(valid), nil); err != nil {
		t.Fatal("valid installer shares container rejected")
	}
	if _, err := ReadVaultInput(PurposeUnsealShares, []byte(matchingHex), nil); err != nil {
		t.Fatal("matching hex and base64 representations rejected")
	}
}

func TestReadVaultInputDecryptsAgeAndNeverFallsBack(t *testing.T) {
	password := []byte("input-password")
	plain := []byte(`{"root_token":"token-from-encrypted-init"}`)
	ciphertext, err := Encrypt(password, plain)
	if err != nil {
		t.Fatal("could not prepare age test input")
	}
	got, err := ReadVaultInput(PurposeAdminToken, ciphertext, password)
	if err != nil || string(got.Token) != "token-from-encrypted-init" {
		t.Fatal("encrypted init input not decoded")
	}
	clear(got.Token)
	for _, bad := range [][]byte{[]byte("age-encryption.org/v2\nunknown"), ciphertext} {
		if _, err := ReadVaultInput(PurposeAdminToken, bad, []byte("wrong-password")); !errors.Is(err, ErrFile) {
			t.Fatal("bad encrypted file or password did not fail closed")
		}
	}
	if _, err := ReadVaultInput("SERVICE_PASSWORD", []byte("a"), nil); !errors.Is(err, ErrFile) {
		t.Fatal("unsupported purpose accepted")
	}
}

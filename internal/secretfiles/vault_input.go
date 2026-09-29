package secretfiles

import (
	"bytes"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"unicode/utf8"
)

const (
	PurposeAdminToken   = "SERVICE_ADMIN_TOKEN"
	PurposeUnsealShares = "SERVICE_UNSEAL_SHARES"
	MaxTokenBytes       = 4096
	MaxSharesJSONBytes  = 65536
	MaxShareBytes       = 128
	MaxShares           = 255
)

// VaultInput contains exactly one of Token or Shares. Byte slices remain
// caller-owned and must be cleared when the value is no longer needed.
type VaultInput struct {
	Purpose string
	Token   []byte
	Shares  [][]byte
}

// ReadVaultInput decodes one of the explicitly approved Vault input file
// forms. The function does not access the filesystem and never returns the
// surrounding initialization JSON. Encrypted input requires a password; a
// recognized age prefix is never retried as plaintext.
func ReadVaultInput(purpose string, fileBytes, inputPassword []byte) (VaultInput, error) {
	if len(fileBytes) == 0 || len(fileBytes) > MaxEncryptedBytes {
		return VaultInput{}, ErrFile
	}
	plain := fileBytes
	ownedPlain := false
	if bytes.HasPrefix(fileBytes, []byte("age-encryption.org/")) {
		if !bytes.HasPrefix(fileBytes, []byte("age-encryption.org/v1\n")) || len(inputPassword) == 0 {
			return VaultInput{}, ErrFile
		}
		limit := MaxTokenBytes
		if purpose == PurposeUnsealShares {
			limit = MaxSharesJSONBytes
		}
		var err error
		plain, err = Decrypt(inputPassword, fileBytes, limit)
		if err != nil {
			return VaultInput{}, ErrFile
		}
		ownedPlain = true
	}
	if ownedPlain {
		defer clear(plain)
	}
	if !utf8.Valid(plain) {
		return VaultInput{}, ErrFile
	}
	switch purpose {
	case PurposeAdminToken:
		return readAdminToken(plain)
	case PurposeUnsealShares:
		return readUnsealShares(plain)
	default:
		return VaultInput{}, ErrFile
	}
}

func readAdminToken(data []byte) (VaultInput, error) {
	if len(data) == 0 || len(data) > MaxTokenBytes {
		return VaultInput{}, ErrFile
	}
	value := data
	trimmed := bytes.TrimSpace(data)
	if len(trimmed) > 0 && trimmed[0] == '{' {
		fields, err := uniqueObject(data)
		if err != nil {
			return VaultInput{}, ErrFile
		}
		raw, ok := fields["root_token"]
		var token string
		if !ok || json.Unmarshal(raw, &token) != nil || !utf8.ValidString(token) {
			return VaultInput{}, ErrFile
		}
		value = []byte(token)
	}
	if len(value) == 0 || len(value) > MaxTokenBytes || bytes.ContainsAny(value, "\r\n") {
		return VaultInput{}, ErrFile
	}
	return VaultInput{Purpose: PurposeAdminToken, Token: append([]byte(nil), value...)}, nil
}

func readUnsealShares(data []byte) (VaultInput, error) {
	if len(data) == 0 || len(data) > MaxSharesJSONBytes {
		return VaultInput{}, ErrFile
	}
	fields, err := uniqueObject(data)
	if err != nil {
		return VaultInput{}, ErrFile
	}
	selected := ""
	for _, key := range []string{"keys", "keys_base64", "unseal_keys_hex", "unseal_keys_b64"} {
		if _, ok := fields[key]; ok {
			if selected != "" && !(selected == "unseal_keys_hex" && key == "unseal_keys_b64") && !(selected == "unseal_keys_b64" && key == "unseal_keys_hex") {
				return VaultInput{}, ErrFile
			}
			if key == "unseal_keys_hex" || key == "unseal_keys_b64" {
				if selected != "" && selected != "unseal_keys_hex" && selected != "unseal_keys_b64" {
					return VaultInput{}, ErrFile
				}
			}
			selected = key
		}
	}
	if selected == "" {
		return VaultInput{}, ErrFile
	}
	selectedRaw, ok := fields[selected]
	if !ok {
		return VaultInput{}, ErrFile
	}
	values, err := decodeStringArray(selectedRaw)
	if err != nil {
		return VaultInput{}, ErrFile
	}
	if _, err := validateShares(values); err != nil {
		return VaultInput{}, ErrFile
	}
	selectedBytes, err := decodeRepresentation(selected, values)
	if err != nil {
		return VaultInput{}, ErrFile
	}
	if selected == "unseal_keys_hex" || selected == "unseal_keys_b64" {
		for _, key := range []string{"unseal_keys_hex", "unseal_keys_b64"} {
			other, exists := fields[key]
			if !exists || key == selected {
				continue
			}
			otherValues, decodeErr := decodeStringArray(other)
			if decodeErr != nil {
				return VaultInput{}, ErrFile
			}
			decoded, decodeErr := decodeRepresentation(key, otherValues)
			if decodeErr != nil || !sameByteSet(selectedBytes, decoded) {
				return VaultInput{}, ErrFile
			}
		}
	}
	encoded, err := json.Marshal(values)
	if err != nil || len(encoded) > 32768 {
		return VaultInput{}, ErrFile
	}
	return VaultInput{Purpose: PurposeUnsealShares, Shares: cloneByteSlices(values)}, nil
}

func decodeStringArray(raw json.RawMessage) ([][]byte, error) {
	var values []string
	if len(raw) == 0 || json.Unmarshal(raw, &values) != nil || len(values) == 0 || len(values) > MaxShares {
		return nil, ErrFile
	}
	result := make([][]byte, len(values))
	for i, value := range values {
		if !utf8.ValidString(value) || len([]byte(value)) == 0 || len([]byte(value)) > MaxShareBytes {
			return nil, ErrFile
		}
		result[i] = []byte(value)
	}
	return result, nil
}

func validateShares(values [][]byte) ([][]byte, error) {
	seen := make(map[string]struct{}, len(values))
	for _, value := range values {
		if len(value) == 0 || len(value) > MaxShareBytes || !utf8.Valid(value) {
			return nil, ErrFile
		}
		if _, ok := seen[string(value)]; ok {
			return nil, ErrFile
		}
		seen[string(value)] = struct{}{}
	}
	return cloneByteSlices(values), nil
}

func decodeRepresentation(key string, values [][]byte) ([][]byte, error) {
	result := make([][]byte, len(values))
	for i, value := range values {
		var decoded []byte
		var err error
		switch key {
		case "unseal_keys_hex":
			decoded, err = hex.DecodeString(string(value))
		case "unseal_keys_b64", "keys_base64":
			decoded, err = base64.StdEncoding.Strict().DecodeString(string(value))
			if err != nil {
				decoded, err = base64.RawStdEncoding.Strict().DecodeString(string(value))
			}
		default:
			decoded = append([]byte(nil), value...)
		}
		if err != nil || len(decoded) == 0 || len(decoded) > MaxShareBytes {
			return nil, ErrFile
		}
		result[i] = decoded
	}
	if _, err := validateShares(result); err != nil {
		return nil, ErrFile
	}
	return result, nil
}

func sameByteSet(left, right [][]byte) bool {
	if len(left) != len(right) {
		return false
	}
	set := make(map[string]int, len(left))
	for _, item := range left {
		set[string(item)]++
	}
	for _, item := range right {
		set[string(item)]--
		if set[string(item)] < 0 {
			return false
		}
	}
	for _, count := range set {
		if count != 0 {
			return false
		}
	}
	return true
}

func cloneByteSlices(values [][]byte) [][]byte {
	result := make([][]byte, len(values))
	for i, value := range values {
		result[i] = append([]byte(nil), value...)
	}
	return result
}

func uniqueObject(data []byte) (map[string]json.RawMessage, error) {
	if len(data) == 0 || !utf8.Valid(data) {
		return nil, ErrFile
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	if err := scanJSONValue(decoder); err != nil {
		return nil, ErrFile
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		return nil, ErrFile
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil || fields == nil {
		return nil, ErrFile
	}
	return fields, nil
}

func scanJSONValue(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delim, isDelim := token.(json.Delim)
	if !isDelim {
		return nil
	}
	switch delim {
	case '{':
		seen := map[string]struct{}{}
		for decoder.More() {
			keyToken, err := decoder.Token()
			if err != nil {
				return err
			}
			key, ok := keyToken.(string)
			if !ok {
				return ErrFile
			}
			if _, duplicate := seen[key]; duplicate {
				return ErrFile
			}
			seen[key] = struct{}{}
			if err := scanJSONValue(decoder); err != nil {
				return err
			}
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim('}') {
			return ErrFile
		}
	case '[':
		for decoder.More() {
			if err := scanJSONValue(decoder); err != nil {
				return err
			}
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim(']') {
			return ErrFile
		}
	default:
		return ErrFile
	}
	return nil
}

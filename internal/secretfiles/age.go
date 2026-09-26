// Package secretfiles provides bounded age password encryption for local
// runtime-secret files. It deliberately knows no service or project semantics.
package secretfiles

import (
	"bytes"
	"errors"
	"io"
	"unicode/utf8"

	"filippo.io/age"
)

const (
	MaxEncryptedBytes = 131072
	MaxPasswordBytes  = 4096
	ScryptWorkFactor  = 18
)

var ErrFile = errors.New("SECRET_FILE_INVALID")

// Encrypt emits the standard binary age format with only the approved
// password/Scrypt recipient. Plaintext is never written to a file or exposed
// in an error. The caller owns and should clear its plaintext/password buffers.
func Encrypt(password, plaintext []byte) ([]byte, error) {
	if !validPassword(password) || len(plaintext) == 0 || len(plaintext) > MaxEncryptedBytes {
		return nil, ErrFile
	}
	recipient, err := age.NewScryptRecipient(string(password))
	if err != nil {
		return nil, ErrFile
	}
	recipient.SetWorkFactor(ScryptWorkFactor)
	var ciphertext bytes.Buffer
	writer, err := age.Encrypt(&ciphertext, recipient)
	if err != nil {
		return nil, ErrFile
	}
	if _, err = writer.Write(plaintext); err != nil {
		_ = writer.Close()
		return nil, ErrFile
	}
	if err = writer.Close(); err != nil || ciphertext.Len() > MaxEncryptedBytes {
		return nil, ErrFile
	}
	return ciphertext.Bytes(), nil
}

// Decrypt accepts only age-encrypted bytes and rejects oversized ciphertext,
// unsupported Scrypt work factors, invalid UTF-8 passwords and plaintext
// exceeding maxPlaintextBytes. It never attempts plaintext fallback.
func Decrypt(password, ciphertext []byte, maxPlaintextBytes int) ([]byte, error) {
	if !validPassword(password) || len(ciphertext) == 0 || len(ciphertext) > MaxEncryptedBytes || maxPlaintextBytes < 1 || maxPlaintextBytes > MaxEncryptedBytes {
		return nil, ErrFile
	}
	identity, err := age.NewScryptIdentity(string(password))
	if err != nil {
		return nil, ErrFile
	}
	identity.SetMaxWorkFactor(ScryptWorkFactor)
	reader, err := age.Decrypt(bytes.NewReader(ciphertext), identity)
	if err != nil {
		return nil, ErrFile
	}
	plaintext, err := io.ReadAll(io.LimitReader(reader, int64(maxPlaintextBytes)+1))
	if err != nil || len(plaintext) == 0 || len(plaintext) > maxPlaintextBytes || !utf8.Valid(plaintext) {
		clear(plaintext)
		return nil, ErrFile
	}
	return plaintext, nil
}

func validPassword(password []byte) bool {
	return len(password) > 0 && len(password) <= MaxPasswordBytes && utf8.Valid(password)
}

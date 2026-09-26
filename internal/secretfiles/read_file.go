package secretfiles

import (
	"errors"
	"io"
)

var ErrSelectedFile = errors.New("SECRET_FILE_UNSAFE")

// ReadSelectedFile reads a bounded regular file from the same opened object
// whose no-follow identity was checked by the platform-specific opener.
func ReadSelectedFile(path string, maxBytes int64) ([]byte, error) {
	if path == "" || maxBytes < 1 || maxBytes > MaxEncryptedBytes {
		return nil, ErrSelectedFile
	}
	file, err := openSelectedFile(path)
	if err != nil {
		return nil, ErrSelectedFile
	}
	defer file.Close()
	before, err := file.Stat()
	if err != nil || !before.Mode().IsRegular() || before.Size() < 1 || before.Size() > maxBytes {
		return nil, ErrSelectedFile
	}
	data, err := io.ReadAll(io.LimitReader(file, maxBytes+1))
	if err != nil || int64(len(data)) != before.Size() || int64(len(data)) > maxBytes {
		clear(data)
		return nil, ErrSelectedFile
	}
	after, err := file.Stat()
	if err != nil || !after.Mode().IsRegular() || after.Size() != before.Size() {
		clear(data)
		return nil, ErrSelectedFile
	}
	return data, nil
}

package installer

import (
	"errors"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"
)

const maxExportDirectoryNameBytes = 128

// ValidateExportDirectoryName admits exactly one portable export destination
// leaf. It intentionally does not reuse the project display-name validator.
func ValidateExportDirectoryName(value string) (string, error) {
	if value == "" || !utf8.ValidString(value) || len(value) > maxExportDirectoryNameBytes || value == "." || value == ".." || filepath.IsAbs(value) || filepath.VolumeName(value) != "" || strings.ContainsAny(value, `/\\:`) {
		return "", errors.New("EXPORT_DESTINATION_INVALID")
	}
	if strings.HasSuffix(value, ".") || strings.HasSuffix(value, " ") || reservedExportDirectoryName(value) {
		return "", errors.New("EXPORT_DESTINATION_INVALID")
	}
	for _, character := range value {
		if unicode.IsControl(character) {
			return "", errors.New("EXPORT_DESTINATION_INVALID")
		}
	}
	return value, nil
}

func reservedExportDirectoryName(value string) bool {
	base := strings.ToUpper(value)
	if index := strings.IndexByte(base, '.'); index >= 0 {
		base = base[:index]
	}
	if base == "CON" || base == "PRN" || base == "AUX" || base == "NUL" {
		return true
	}
	if len(base) == 4 && (strings.HasPrefix(base, "COM") || strings.HasPrefix(base, "LPT")) {
		return base[3] >= '1' && base[3] <= '9'
	}
	return false
}

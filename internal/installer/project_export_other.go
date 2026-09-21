//go:build !windows && !linux

package installer

import "errors"

type exportIdentity struct{}

func (exportIdentity) empty() bool    { return true }
func (exportIdentity) String() string { return "" }

type exportFileIdentity struct{}
type exportDirectory struct{}
type exportEntryKind uint8

const (
	exportEntryDirectory exportEntryKind = iota + 1
	exportEntryRegular
)

type exportEntry struct {
	name string
	kind exportEntryKind
}

func openExportSourceDirectory(string) (*exportDirectory, error) {
	return nil, errors.New("EXPORT_SOURCE_UNSAFE")
}
func openExportDestinationDirectory(string) (*exportDirectory, error) {
	return nil, errors.New("EXPORT_DESTINATION_UNSAFE")
}
func (directory *exportDirectory) close()                   {}
func (directory *exportDirectory) identity() exportIdentity { return exportIdentity{} }
func (directory *exportDirectory) openDirectory([]string) (*exportDirectory, error) {
	return nil, errors.New("unsupported")
}
func (directory *exportDirectory) entries() ([]exportEntry, error) {
	return nil, errors.New("unsupported")
}
func (directory *exportDirectory) readFile([]string, int64) ([]byte, exportFileIdentity, error) {
	return nil, exportFileIdentity{}, errors.New("unsupported")
}
func (directory *exportDirectory) exists(string) (bool, error) {
	return false, errors.New("unsupported")
}
func (directory *exportDirectory) createStaging(string) (*exportDirectory, string, error) {
	return nil, "", errors.New("unsupported")
}
func (directory *exportDirectory) createDirectory(string) (*exportDirectory, error) {
	return nil, errors.New("unsupported")
}
func (directory *exportDirectory) writeFile(string, []byte) error { return errors.New("unsupported") }
func (directory *exportDirectory) publish(*exportDirectory, string, string) error {
	return errors.New("unsupported")
}
func (directory *exportDirectory) removeOwnedTree(*exportDirectory, string) error {
	return errors.New("unsupported")
}
func isExportNotExist(error) bool { return false }

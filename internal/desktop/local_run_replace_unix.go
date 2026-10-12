//go:build !windows

package desktop

import "os"

func replaceLocalRunRecord(source, destination string) error { return os.Rename(source, destination) }
func syncLocalRunRecordDir(path string) error {
	directory, err := os.Open(path)
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}

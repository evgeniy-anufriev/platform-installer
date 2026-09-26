//go:build windows

package installer

import "testing"

func TestSecretOutputWindowsHeldDirectoryDurability(t *testing.T) {
	directory, err := openExportDestinationDirectory(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	if err := syncSecretOutputDirectory(directory); err != nil {
		t.Fatalf("held directory durability barrier: %v", err)
	}
}

package secretfiles

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestReadSelectedFileBoundedAndRegularOnly(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "secret.txt")
	if err := os.WriteFile(path, []byte("secret"), 0600); err != nil {
		t.Fatal("fixture setup failed")
	}
	got, err := ReadSelectedFile(path, 16)
	if err != nil || string(got) != "secret" {
		t.Fatal("regular selected file was not read")
	}
	clear(got)
	if _, err := ReadSelectedFile(path, 5); err == nil {
		t.Fatal("oversized file was accepted")
	}
	if _, err := ReadSelectedFile(dir, 16); err == nil {
		t.Fatal("directory was accepted")
	}
	link := filepath.Join(dir, "secret-link")
	if err := os.Symlink(path, link); err != nil {
		if runtime.GOOS == "windows" {
			t.Skip("symlink creation unavailable")
		}
		t.Fatal("symlink setup failed")
	}
	if _, err := ReadSelectedFile(link, 16); err == nil {
		t.Fatal("symlink was accepted")
	}
}

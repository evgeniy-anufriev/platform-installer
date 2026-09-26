//go:build linux

package secretfiles

import (
	"golang.org/x/sys/unix"
	"path/filepath"
	"testing"
	"time"
)

func TestSelectedFIFORejectsWithoutWriter(t *testing.T) {
	path := filepath.Join(t.TempDir(), "input")
	if err := unix.Mkfifo(path, 0600); err != nil {
		t.Fatal(err)
	}
	started := time.Now()
	if _, err := ReadSelectedFile(path, 4096); err == nil {
		t.Fatal("FIFO admitted")
	}
	if time.Since(started) > time.Second {
		t.Fatal("FIFO rejection blocked")
	}
}

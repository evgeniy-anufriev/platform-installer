//go:build linux

package installer

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSecretOutputStagingSubstitutionNeverReturnsReceiptOrDeletesForeignObject(t *testing.T) {
	project := t.TempDir()
	secrets := filepath.Join(project, "secrets")
	var retained string
	receipt, err := publishSecretOutputFiles(project, "project-test", "vault-ha", repeatHex('a', 32), "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("encrypted-admin"), []byte("encrypted-shares"), func(stage string) error {
		if stage != "publish" {
			return nil
		}
		entries, err := os.ReadDir(secrets)
		if err != nil {
			return err
		}
		for _, entry := range entries {
			if !strings.HasPrefix(entry.Name(), ".") {
				continue
			}
			path := filepath.Join(secrets, entry.Name())
			retained = path + "-original"
			if err := os.Rename(path, retained); err != nil {
				return err
			}
			if err := os.Mkdir(path, 0700); err != nil {
				return err
			}
			return os.WriteFile(filepath.Join(path, "foreign"), []byte("keep"), 0600)
		}
		t.Fatal("staging absent")
		return nil
	})
	if err == nil || receipt.ReceiptID != "" {
		t.Fatal("substituted publication admitted")
	}
	if data, err := os.ReadFile(filepath.Join(secrets, "vault-ha", "foreign")); err != nil || string(data) != "keep" {
		t.Fatal("foreign object deleted")
	}
	if _, err := os.Stat(filepath.Join(retained, "complete")); err != nil {
		t.Fatal("original encrypted staging lost")
	}
}

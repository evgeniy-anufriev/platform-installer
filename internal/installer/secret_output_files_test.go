package installer

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestSecretOutputDurabilityFailuresNeverIssueReceipt(t *testing.T) {
	for _, stage := range []string{"project-flush", "staging-flush", "publish", "published-flush", "binding-readback"} {
		t.Run(stage, func(t *testing.T) {
			receipt, err := publishSecretOutputFiles(t.TempDir(), "project-test", "vault-ha", repeatHex('a', 32), "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("encrypted-admin"), []byte("encrypted-shares"), func(current string) error {
				if current == stage {
					return errors.New("injected barrier failure")
				}
				return nil
			})
			if err == nil || receipt.ReceiptID != "" {
				t.Fatal("failure authorized destructive ACK")
			}
		})
	}
}

func TestPublishSecretOutputFilesAtomicallyPublishesOnlyEncryptedFixedEntries(t *testing.T) {
	parent := t.TempDir()
	receipt, err := PublishSecretOutputFiles(parent, "project-test", "vault-ha", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("age-admin-ciphertext"), []byte("age-shares-ciphertext"))
	if err != nil {
		t.Fatal(err)
	}
	if receipt.ReceiptID == "" || len(receipt.Digests) != 2 {
		t.Fatalf("receipt=%#v", receipt)
	}
	if receipt.Directory != filepath.Join(parent, "secrets", "vault-ha", receipt.PackageID) {
		t.Fatalf("output is not in the package's secrets directory: %s", receipt.Directory)
	}
	if got, err := os.ReadFile(filepath.Join(receipt.Directory, "admin-token.age")); err != nil || string(got) != "age-admin-ciphertext" {
		t.Fatalf("admin file=%q err=%v", got, err)
	}
	if got, err := os.ReadFile(filepath.Join(receipt.Directory, "unseal-shares.age")); err != nil || string(got) != "age-shares-ciphertext" {
		t.Fatalf("shares file=%q err=%v", got, err)
	}
	complete, err := os.ReadFile(filepath.Join(receipt.Directory, "complete"))
	var value map[string]any
	if err != nil || json.Unmarshal(complete, &value) != nil || value["packageId"] != "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" || value["receiptId"] != receipt.ReceiptID {
		t.Fatalf("complete receipt=%s err=%v", complete, err)
	}
	loaded, encrypted, err := ReadSecretOutputFiles(parent, receipt.ProjectID, receipt.DeploymentID, receipt.PackageID, receipt.SourceRunID, receipt.Generation, receipt.RuntimeDigest)
	if err != nil || loaded.ReceiptID != receipt.ReceiptID || string(encrypted["admin-token"]) != "age-admin-ciphertext" || string(encrypted["unseal-shares"]) != "age-shares-ciphertext" {
		t.Fatalf("readback=%#v bytes=%v err=%v", loaded, encrypted, err)
	}
	for _, data := range encrypted {
		clear(data)
	}
	if _, err := PublishSecretOutputFiles(parent, "project-test", "vault-ha", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("replacement"), []byte("replacement")); err == nil {
		t.Fatal("existing output package was overwritten")
	}
	if got, _ := os.ReadFile(filepath.Join(receipt.Directory, "admin-token.age")); string(got) != "age-admin-ciphertext" {
		t.Fatal("existing output changed after conflict")
	}
}

func TestSecretOutputFilesPreserveEarlierGeneration(t *testing.T) {
	root := t.TempDir()
	digest := "sha256:" + repeatHex('b', 64)
	first, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", repeatHex('a', 32), "installer-first", 1, digest, []byte("first-token"), []byte("first-shares"))
	if err != nil {
		t.Fatal(err)
	}
	second, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", repeatHex('c', 32), "installer-second", 2, digest, []byte("second-token"), []byte("second-shares"))
	if err != nil {
		t.Fatal(err)
	}
	if first.Directory == second.Directory {
		t.Fatal("generations share a destination")
	}
	for _, item := range []struct {
		receipt SecretOutputFileReceipt
		token   string
	}{{first, "first-token"}, {second, "second-token"}} {
		_, encrypted, err := ReadSecretOutputFiles(root, item.receipt.ProjectID, item.receipt.DeploymentID, item.receipt.PackageID, item.receipt.SourceRunID, item.receipt.Generation, item.receipt.RuntimeDigest)
		if err != nil || string(encrypted["admin-token"]) != item.token {
			t.Fatalf("read %s: %v", item.receipt.PackageID, err)
		}
		for _, value := range encrypted {
			clear(value)
		}
	}
}

func TestSecretOutputFilesReadLegacyFlatPackageWithoutReplacingIt(t *testing.T) {
	root := t.TempDir()
	digest := "sha256:" + repeatHex('b', 64)
	old, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", repeatHex('a', 32), "installer-first", 1, digest, []byte("first-token"), []byte("first-shares"))
	if err != nil {
		t.Fatal(err)
	}
	flat := filepath.Join(root, "secrets", "vault-ha")
	for _, name := range []string{"admin-token.age", "unseal-shares.age", "complete"} {
		if err := os.Rename(filepath.Join(old.Directory, name), filepath.Join(flat, name)); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Remove(old.Directory); err != nil {
		t.Fatal(err)
	}
	newer, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", repeatHex('c', 32), "installer-second", 2, digest, []byte("second-token"), []byte("second-shares"))
	if err != nil {
		t.Fatal(err)
	}
	if newer.Directory == flat {
		t.Fatal("new package replaced the flat legacy package")
	}
	for _, item := range []struct {
		receipt SecretOutputFileReceipt
		token   string
	}{{old, "first-token"}, {newer, "second-token"}} {
		loaded, encrypted, err := ReadSecretOutputFiles(root, item.receipt.ProjectID, item.receipt.DeploymentID, item.receipt.PackageID, item.receipt.SourceRunID, item.receipt.Generation, item.receipt.RuntimeDigest)
		if err != nil || string(encrypted["admin-token"]) != item.token {
			t.Fatalf("read %s: %v", item.receipt.PackageID, err)
		}
		if item.receipt.PackageID == old.PackageID && loaded.Directory != flat {
			t.Fatalf("legacy path: %s", loaded.Directory)
		}
		for _, value := range encrypted {
			clear(value)
		}
	}
}

func TestSecretOutputPackageDirectoryRejectsSubstitution(t *testing.T) {
	root, outside := t.TempDir(), t.TempDir()
	deployment := filepath.Join(root, "secrets", "vault-ha")
	if err := os.MkdirAll(deployment, 0o700); err != nil {
		t.Fatal(err)
	}
	packageID := repeatHex('a', 32)
	if err := os.Symlink(outside, filepath.Join(deployment, packageID)); err != nil {
		t.Skipf("symlink prerequisite: %v", err)
	}
	_, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", packageID, "installer-first", 1,
		"sha256:"+repeatHex('b', 64), []byte("cipher"), []byte("cipher"))
	if err == nil {
		t.Fatal("substituted package directory accepted for publication")
	}
	if _, _, err := ReadSecretOutputFiles(root, "project-test", "vault-ha", packageID, "installer-first", 1,
		"sha256:"+repeatHex('b', 64)); err == nil {
		t.Fatal("substituted package directory accepted for read")
	}
	entries, err := os.ReadDir(outside)
	if err != nil || len(entries) != 0 {
		t.Fatalf("outside modified: entries=%v err=%v", entries, err)
	}
}

func TestPublishSecretOutputFilesRejectsInvalidBindingBeforeCreatingStaging(t *testing.T) {
	parent := t.TempDir()
	if _, err := PublishSecretOutputFiles(parent, "../project", "vault-ha", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("cipher"), []byte("cipher")); err == nil {
		t.Fatal("invalid project identity accepted")
	}
	entries, err := os.ReadDir(parent)
	if err != nil || len(entries) != 0 {
		t.Fatalf("invalid request created filesystem objects: entries=%v err=%v", entries, err)
	}
}

func TestSecretOutputDefaultDirectoryRejectsSymlink(t *testing.T) {
	project, outside := t.TempDir(), t.TempDir()
	if err := os.Symlink(outside, filepath.Join(project, "secrets")); err != nil {
		t.Skipf("symlink prerequisite: %v", err)
	}
	_, err := PublishSecretOutputFiles(project, "project-test", "vault-ha", repeatHex('a', 32), "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("cipher"), []byte("cipher"))
	if err == nil {
		t.Fatal("substituted secrets directory accepted")
	}
	entries, err := os.ReadDir(outside)
	if err != nil || len(entries) != 0 {
		t.Fatalf("outside directory modified: entries=%v err=%v", entries, err)
	}
}

func TestProjectCopyAndRevisionExcludeSecretOutputs(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("name: qa\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	before, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := PublishSecretOutputFiles(root, "project-test", "vault-ha", repeatHex('a', 32), "installer-1234", 1, "sha256:"+repeatHex('b', 64), []byte("cipher"), []byte("cipher")); err != nil {
		t.Fatal(err)
	}
	after, err := ProjectRevision(root)
	if err != nil || before != after {
		t.Fatalf("secret output changed desired revision: %s %s %v", before, after, err)
	}
	copyRoot, cleanup, err := copyProject(root)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	if _, err := os.Stat(filepath.Join(copyRoot, "secrets")); !os.IsNotExist(err) {
		t.Fatal("secret output included in Core staging")
	}
}

func repeatHex(value byte, count int) string {
	data := make([]byte, count)
	for index := range data {
		data[index] = value
	}
	return string(data)
}

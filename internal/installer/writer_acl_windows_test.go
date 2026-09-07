//go:build windows

package installer

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"unsafe"
)

var testConvertSecurityDescriptorToString = syscall.NewLazyDLL("advapi32.dll").NewProc("ConvertSecurityDescriptorToStringSecurityDescriptorW")

func testWriterDACL(t *testing.T, path string) ([]byte, uint16) {
	t.Helper()
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	descriptor, control, err := readWriterDACL(file)
	if err != nil {
		t.Fatal(err)
	}
	return descriptor, control
}

func protectTestCanonicalFile(t *testing.T, path string) {
	t.Helper()
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := hardenWriterFile(file, 0o600); err != nil {
		file.Close()
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}
}

func setTestParentOnlyACE(t *testing.T, path string) {
	t.Helper()
	token, err := syscall.OpenCurrentProcessToken()
	if err != nil {
		t.Fatal(err)
	}
	defer token.Close()
	user, err := token.GetTokenUser()
	if err != nil {
		t.Fatal(err)
	}
	sid, err := user.User.Sid.String()
	if err != nil {
		t.Fatal(err)
	}
	sddl, err := syscall.UTF16PtrFromString("D:P(A;OICI;FA;;;" + sid + ")(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;;GR;;;WD)")
	if err != nil {
		t.Fatal(err)
	}
	var descriptor uintptr
	var size uint32
	result, _, callErr := writerConvertSecurityDescriptor.Call(uintptr(unsafe.Pointer(sddl)), 1, uintptr(unsafe.Pointer(&descriptor)), uintptr(unsafe.Pointer(&size)))
	if result == 0 {
		t.Fatal(callErr)
	}
	defer syscall.LocalFree(syscall.Handle(descriptor))
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	result, _, callErr = writerSetKernelObjectSecurity.Call(file.Fd(), writerDACLInformation|writerProtectedDACLInformation, descriptor)
	if result == 0 {
		t.Fatal(callErr)
	}
}

func testWriterSDDL(t *testing.T, path string) string {
	t.Helper()
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	descriptor, _, err := readWriterDACL(file)
	if err != nil {
		t.Fatal(err)
	}
	var textPointer *uint16
	var length uint32
	result, _, callErr := testConvertSecurityDescriptorToString.Call(uintptr(unsafe.Pointer(&descriptor[0])), 1, writerDACLInformation, uintptr(unsafe.Pointer(&textPointer)), uintptr(unsafe.Pointer(&length)))
	if result == 0 {
		t.Fatal(callErr)
	}
	defer syscall.LocalFree(syscall.Handle(uintptr(unsafe.Pointer(textPointer))))
	text := unsafe.Slice(textPointer, length)
	return syscall.UTF16ToString(text)
}

func TestWindowsCanonicalACLPolicy(t *testing.T) {
	t.Run("existing document ACL is preserved", func(t *testing.T) {
		root := t.TempDir()
		before := []byte("before\n")
		target := filepath.Join(root, "ansible.cfg")
		if err := os.WriteFile(target, before, 0o600); err != nil {
			t.Fatal(err)
		}
		protectTestCanonicalFile(t, target)
		beforeACL, beforeControl := testWriterDACL(t, target)
		err := (&Backend{replace: atomicReplace}).commitDocuments(root, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", []storedDocument{{LogicalPath: "ansible.cfg", Before: before, After: []byte("after\n"), Existed: true}})
		if err != nil {
			t.Fatal(err)
		}
		afterACL, afterControl := testWriterDACL(t, target)
		if beforeControl != afterControl || !bytes.Equal(beforeACL, afterACL) {
			t.Fatal("existing canonical DACL changed during replacement")
		}
	})

	t.Run("recovery rejects ACL-only external mutation", func(t *testing.T) {
		root := t.TempDir()
		target := filepath.Join(root, "ansible.cfg")
		before := []byte("before\n")
		if err := os.WriteFile(target, before, 0o600); err != nil {
			t.Fatal(err)
		}
		_, beforeDigest, beforeIdentity, err := inspectWriterFile(target)
		if err != nil {
			t.Fatal(err)
		}
		beforeSecurity := mustCaptureCanonicalSecurity(t, target)

		after := []byte("published\n")
		outputPath := target + ".published"
		output, err := createWriterFile(outputPath, 0o600)
		if err != nil {
			t.Fatal(err)
		}
		if err := applyCanonicalSecurity(beforeSecurity, output); err == nil {
			_, err = output.Write(after)
		}
		if err == nil {
			err = output.Sync()
		}
		var outputIdentity string
		if err == nil {
			outputIdentity, err = writerFileIdentity(output)
		}
		if closeErr := output.Close(); err == nil {
			err = closeErr
		}
		if err != nil {
			t.Fatal(err)
		}
		if err := atomicReplace(outputPath, target); err != nil {
			t.Fatal(err)
		}

		identifier := strings.Repeat("d", 32)
		journal := transactionJournal{TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1,
			Documents: []transactionDocument{{LogicalPath: "ansible.cfg", Existed: true, Mode: 0o600,
				Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
				BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity,
				AfterDigest: digestBytes(after), OutputIdentity: outputIdentity}}}
		directory := writeRecoveryJournal(t, root, identifier, journal)
		if err := os.WriteFile(filepath.Join(directory, "000.before"), before, 0o600); err != nil {
			t.Fatal(err)
		}

		_, _, identityBeforeACLChange, err := inspectWriterFile(target)
		if err != nil {
			t.Fatal(err)
		}
		protectTestCanonicalFile(t, target)
		_, digestAfterACLChange, identityAfterACLChange, err := inspectWriterFile(target)
		if err != nil {
			t.Fatal(err)
		}
		if identityAfterACLChange != identityBeforeACLChange || digestAfterACLChange != digestBytes(after) {
			t.Fatal("ACL-only test mutation changed file identity or bytes")
		}
		if matches, matchErr := canonicalSecurityMatches(target, beforeSecurity); matchErr != nil || matches {
			t.Fatalf("ACL-only test mutation was not distinct: matches=%v err=%v", matches, matchErr)
		}
		if err := recoverTransactions(root); err == nil {
			t.Fatal("recovery accepted an ACL-only external mutation")
		}
		current, readErr := os.ReadFile(target)
		if readErr != nil || !bytes.Equal(current, after) {
			t.Fatalf("blocked recovery mutated canonical bytes: %q, %v", current, readErr)
		}
	})

	t.Run("recovery rejects ACL-only rollback temporary mutation", func(t *testing.T) {
		root := t.TempDir()
		target := filepath.Join(root, "ansible.cfg")
		before, after := []byte("before\n"), []byte("published\n")
		if err := os.WriteFile(target, before, 0o600); err != nil {
			t.Fatal(err)
		}
		_, beforeDigest, beforeIdentity, _ := inspectWriterFile(target)
		beforeSecurity := mustCaptureCanonicalSecurity(t, target)
		outputPath := target + ".published"
		if err := os.WriteFile(outputPath, after, 0o600); err != nil {
			t.Fatal(err)
		}
		mustApplyCanonicalSecurity(t, outputPath, beforeSecurity)
		_, _, outputIdentity, _ := inspectWriterFile(outputPath)
		if err := atomicReplace(outputPath, target); err != nil {
			t.Fatal(err)
		}
		identifier := strings.Repeat("e", 32)
		journal := transactionJournal{TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1,
			Documents: []transactionDocument{{LogicalPath: "ansible.cfg", Existed: true, Mode: 0o600,
				Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
				BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity,
				AfterDigest: digestBytes(after), OutputIdentity: outputIdentity}}}
		directory := writeRecoveryJournal(t, root, identifier, journal)
		if err := os.WriteFile(filepath.Join(directory, "000.before"), before, 0o600); err != nil {
			t.Fatal(err)
		}
		rollbackPath := filepath.Join(directory, "000.rollback")
		if err := os.WriteFile(rollbackPath, before, 0o600); err != nil {
			t.Fatal(err)
		}
		mustApplyCanonicalSecurity(t, rollbackPath, beforeSecurity)
		_, _, rollbackIdentity, _ := inspectWriterFile(rollbackPath)
		journal.Documents[0].RollbackIdentity = rollbackIdentity
		content, _ := json.Marshal(journal)
		if err := os.WriteFile(filepath.Join(directory, "journal.json"), content, 0o600); err != nil {
			t.Fatal(err)
		}
		protectTestCanonicalFile(t, rollbackPath)
		if err := recoverTransactions(root); err == nil {
			t.Fatal("recovery accepted an ACL-only rollback temporary mutation")
		}
		current, readErr := os.ReadFile(target)
		if readErr != nil || !bytes.Equal(current, after) {
			t.Fatalf("blocked recovery replaced canonical bytes: %q, %v", current, readErr)
		}
	})

	t.Run("recovery rechecks target ACL immediately before rollback", func(t *testing.T) {
		root := t.TempDir()
		logical := "ansible.cfg"
		target := filepath.Join(root, logical)
		before, after := []byte("before\n"), []byte("published\n")
		identifier := strings.Repeat("f", 32)
		if err := os.WriteFile(target, before, 0o600); err != nil {
			t.Fatal(err)
		}
		_, beforeDigest, beforeIdentity, _ := inspectWriterFile(target)
		beforeSecurity := mustCaptureCanonicalSecurity(t, target)
		outputPath := target + ".published"
		if err := os.WriteFile(outputPath, after, 0o600); err != nil {
			t.Fatal(err)
		}
		mustApplyCanonicalSecurity(t, outputPath, beforeSecurity)
		_, _, outputIdentity, _ := inspectWriterFile(outputPath)
		if err := atomicReplace(outputPath, target); err != nil {
			t.Fatal(err)
		}
		document := transactionDocument{LogicalPath: logical, Existed: true, Mode: 0o600,
			Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
			BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity,
			AfterDigest: digestBytes(after), OutputIdentity: outputIdentity}
		journal := transactionJournal{TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1, Documents: []transactionDocument{document}}
		directory := writeRecoveryJournal(t, root, identifier, journal)
		if err := os.WriteFile(filepath.Join(directory, "000.before"), before, 0o600); err != nil {
			t.Fatal(err)
		}
		originalPersist := persistTransactionJournal
		mutated := false
		persistTransactionJournal = func(path string, current transactionJournal) error {
			if !mutated && current.Documents[0].RollbackIdentity != "" {
				mutated = true
				protectTestCanonicalFile(t, target)
			}
			return originalPersist(path, current)
		}
		defer func() { persistTransactionJournal = originalPersist }()
		if err := restoreTransaction(root, directory, journal); err == nil {
			t.Fatal("rollback accepted a target DACL changed after recovery preflight")
		}
		if !mutated {
			t.Fatal("test did not inject the DACL-only mutation")
		}
		current, readErr := os.ReadFile(target)
		if readErr != nil || !bytes.Equal(current, after) {
			t.Fatalf("rollback overwrote the externally secured target: %q, %v", current, readErr)
		}
	})

	t.Run("new nested canonical tree enables parent inheritance", func(t *testing.T) {
		root := t.TempDir()
		setTestParentOnlyACE(t, root)
		if !strings.Contains(testWriterSDDL(t, root), ";;;WD)") {
			t.Fatal("test parent-only ACE was not installed")
		}
		target := filepath.Join(root, filepath.FromSlash(desiredDocument))
		err := (&Backend{replace: atomicReplace}).commitDocuments(root, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", []storedDocument{{LogicalPath: desiredDocument, After: []byte("new\n")}})
		if err != nil {
			t.Fatal(err)
		}
		for _, path := range []string{filepath.Join(root, "inventory"), filepath.Join(root, "inventory", "group_vars"), filepath.Join(root, "inventory", "group_vars", "all"), target} {
			_, control := testWriterDACL(t, path)
			if control&writerDACLProtectedControl != 0 {
				t.Fatalf("new canonical path retained the private transaction DACL: %s", path)
			}
			if strings.Contains(testWriterSDDL(t, path), ";;;WD)") {
				t.Fatalf("non-inheritable parent ACE was copied to canonical child: %s", path)
			}
		}
	})

	t.Run("rollback restores existing document ACL", func(t *testing.T) {
		root := t.TempDir()
		firstPath := filepath.Join(root, "ansible.cfg")
		secondPath := filepath.Join(root, "inventory", "hosts.yml")
		if err := os.MkdirAll(filepath.Dir(secondPath), 0o755); err != nil {
			t.Fatal(err)
		}
		firstBefore, secondBefore := []byte("first-before\n"), []byte("second-before\n")
		if err := os.WriteFile(firstPath, firstBefore, 0o600); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(secondPath, secondBefore, 0o600); err != nil {
			t.Fatal(err)
		}
		protectTestCanonicalFile(t, firstPath)
		beforeACL, beforeControl := testWriterDACL(t, firstPath)
		calls := 0
		backend := &Backend{replace: func(source, destination string) error {
			calls++
			if calls == 2 {
				return errors.New("injected replacement failure")
			}
			return atomicReplace(source, destination)
		}}
		err := backend.commitDocuments(root, "cccccccccccccccccccccccccccccccc", []storedDocument{
			{LogicalPath: "ansible.cfg", Before: firstBefore, After: []byte("first-after\n"), Existed: true},
			{LogicalPath: "inventory/hosts.yml", Before: secondBefore, After: []byte("second-after\n"), Existed: true},
		})
		if err == nil {
			t.Fatal("expected injected transaction failure")
		}
		afterACL, afterControl := testWriterDACL(t, firstPath)
		if beforeControl != afterControl || !bytes.Equal(beforeACL, afterACL) {
			t.Fatal("rollback did not restore the original canonical DACL")
		}
		if content, readErr := os.ReadFile(firstPath); readErr != nil || !bytes.Equal(content, firstBefore) {
			t.Fatalf("rollback bytes=%q err=%v", content, readErr)
		}
	})
}

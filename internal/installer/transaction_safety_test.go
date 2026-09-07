package installer

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func writeRecoveryJournal(t *testing.T, root, identifier string, journal transactionJournal) string {
	t.Helper()
	directory := runtimePath(root, "edit-transactions", identifier)
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	content, err := json.Marshal(journal)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "journal.json"), content, 0o600); err != nil {
		t.Fatal(err)
	}
	return directory
}

func mustCaptureCanonicalSecurity(t *testing.T, path string) string {
	t.Helper()
	security, err := captureCanonicalSecurity(path)
	if err != nil {
		t.Fatal(err)
	}
	return security
}

func mustApplyCanonicalSecurity(t *testing.T, path, security string) {
	t.Helper()
	file, err := openWriterSecurityHandle(path)
	if err == nil {
		err = applyCanonicalSecurity(security, file)
	}
	if file != nil {
		if closeErr := file.Close(); err == nil {
			err = closeErr
		}
	}
	if err != nil {
		t.Fatal(err)
	}
}

func TestRecoveryBlocksExternalChangeToPublishedNewDocument(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("b", 32)
	logical := managedHostDocument("recovery-node")
	target := filepath.Join(root, filepath.FromSlash(logical))
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	transactionOutput := []byte("transaction output\n")
	if err := os.WriteFile(target, transactionOutput, 0o644); err != nil {
		t.Fatal(err)
	}
	_, _, outputIdentity, err := inspectWriterFile(target)
	if err != nil {
		t.Fatal(err)
	}
	directory := writeRecoveryJournal(t, root, identifier, transactionJournal{
		TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1,
		Documents: []transactionDocument{{
			LogicalPath: logical, Mode: 0o644, Backup: "000.before",
			Temporary:   ".platform-installer-" + identifier + "-000.tmp",
			AfterDigest: digestBytes(transactionOutput), OutputIdentity: outputIdentity,
		}},
	})
	external := []byte("external owner content\n")
	if err := os.WriteFile(target, external, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err == nil {
		t.Fatal("recovery accepted an externally changed published document")
	}
	current, err := os.ReadFile(target)
	if err != nil || string(current) != string(external) {
		t.Fatalf("recovery changed external content: %q, %v", current, err)
	}
	if _, err := os.Stat(directory); err != nil {
		t.Fatalf("blocked recovery removed diagnostic transaction state: %v", err)
	}
}

func TestRecoveryBlocksSameContentReplacementByIdentity(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("f", 32)
	logical := managedHostDocument("identity-node")
	target := filepath.Join(root, filepath.FromSlash(logical))
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	output := []byte("transaction output\n")
	if err := os.WriteFile(target, output, 0o644); err != nil {
		t.Fatal(err)
	}
	_, _, outputIdentity, err := inspectWriterFile(target)
	if err != nil {
		t.Fatal(err)
	}
	directory := writeRecoveryJournal(t, root, identifier, transactionJournal{
		TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1,
		Documents: []transactionDocument{{
			LogicalPath: logical, Mode: 0o644, Backup: "000.before",
			Temporary:   ".platform-installer-" + identifier + "-000.tmp",
			AfterDigest: digestBytes(output), OutputIdentity: outputIdentity,
		}},
	})
	replacement := target + ".external"
	if err := os.WriteFile(replacement, output, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := atomicReplace(replacement, target); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err == nil {
		t.Fatal("recovery accepted a same-content external replacement")
	}
	current, err := os.ReadFile(target)
	if err != nil || string(current) != string(output) {
		t.Fatalf("recovery changed replacement content: %q, %v", current, err)
	}
	if _, err := os.Stat(directory); err != nil {
		t.Fatalf("blocked recovery removed diagnostic transaction state: %v", err)
	}
}

func TestRecoveryRestoresOnlyPublishedDocuments(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("9", 32)
	firstLogical := desiredDocument
	secondLogical := "project.yml"
	firstTarget := filepath.Join(root, filepath.FromSlash(firstLogical))
	secondTarget := filepath.Join(root, secondLogical)
	firstBefore, _ := os.ReadFile(firstTarget)
	secondBefore, _ := os.ReadFile(secondTarget)
	_, firstBeforeDigest, firstBeforeIdentity, _ := inspectWriterFile(firstTarget)
	_, secondBeforeDigest, secondBeforeIdentity, _ := inspectWriterFile(secondTarget)
	firstBeforeSecurity := mustCaptureCanonicalSecurity(t, firstTarget)
	secondBeforeSecurity := mustCaptureCanonicalSecurity(t, secondTarget)
	firstAfter := []byte("published transaction output\n")
	firstTemporary := firstTarget + ".published"
	if err := os.WriteFile(firstTemporary, firstAfter, 0o644); err != nil {
		t.Fatal(err)
	}
	mustApplyCanonicalSecurity(t, firstTemporary, firstBeforeSecurity)
	_, _, firstOutputIdentity, _ := inspectWriterFile(firstTemporary)
	if err := atomicReplace(firstTemporary, firstTarget); err != nil {
		t.Fatal(err)
	}
	secondAfter := []byte("not published\n")
	secondTemporaryName := ".platform-installer-" + identifier + "-001.tmp"
	secondTemporary := filepath.Join(root, secondTemporaryName)
	if err := os.WriteFile(secondTemporary, secondAfter, 0o644); err != nil {
		t.Fatal(err)
	}
	_, _, secondOutputIdentity, _ := inspectWriterFile(secondTemporary)
	directory := runtimePath(root, "edit-transactions", identifier)
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "000.before"), firstBefore, 0o600); err != nil {
		t.Fatal(err)
	}
	journal := transactionJournal{TransactionID: identifier, Phase: "REPLACING", Replacing: 1, Published: 1,
		Documents: []transactionDocument{
			{LogicalPath: firstLogical, Existed: true, Mode: 0o644, Backup: "000.before",
				Temporary: ".platform-installer-" + identifier + "-000.tmp", BeforeDigest: firstBeforeDigest,
				BeforeIdentity: firstBeforeIdentity, BeforeSecurity: firstBeforeSecurity, AfterDigest: digestBytes(firstAfter), OutputIdentity: firstOutputIdentity},
			{LogicalPath: secondLogical, Existed: true, Mode: 0o644, Backup: "001.before",
				Temporary: secondTemporaryName, BeforeDigest: secondBeforeDigest, BeforeIdentity: secondBeforeIdentity, BeforeSecurity: secondBeforeSecurity,
				AfterDigest: digestBytes(secondAfter), OutputIdentity: secondOutputIdentity},
		}}
	writeRecoveryJournal(t, root, identifier, journal)
	if err := validateTransactionJournal(root, directory, journal); err != nil {
		t.Fatalf("test journal invalid: %v", err)
	}
	if err := validateTransactionDirectory(directory, journal); err != nil {
		t.Fatalf("test directory invalid: %v", err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatal(err)
	}
	firstCurrent, _ := os.ReadFile(firstTarget)
	secondCurrent, _ := os.ReadFile(secondTarget)
	if string(firstCurrent) != string(firstBefore) {
		t.Fatal("published document was not restored")
	}
	if string(secondCurrent) != string(secondBefore) {
		t.Fatal("unpublished document was mutated")
	}
}

func TestRecoveryRejectsCorruptJournalBeforeMutation(t *testing.T) {
	tests := []struct {
		name    string
		journal func(string) []byte
	}{
		{name: "unknown field", journal: func(identifier string) []byte {
			return []byte(`{"transactionId":"` + identifier + `","phase":"PREPARING","replacingIndex":-1,"publishedCount":0,"documents":[],"unexpected":true}`)
		}},
		{name: "escaping document", journal: func(identifier string) []byte {
			journal := transactionJournal{TransactionID: identifier, Phase: "PREPARING", Replacing: -1,
				Documents: []transactionDocument{{LogicalPath: "../outside.yml", Mode: 0o644,
					Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp", AfterDigest: digestBytes([]byte("new"))}}}
			content, _ := json.Marshal(journal)
			return content
		}},
	}
	for index, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root, cleanup := testProject(t)
			defer cleanup()
			canonical := filepath.Join(root, filepath.FromSlash(desiredDocument))
			before, err := os.ReadFile(canonical)
			if err != nil {
				t.Fatal(err)
			}
			identifier := strings.Repeat(string(rune('c'+index)), 32)
			directory := runtimePath(root, "edit-transactions", identifier)
			if err := os.MkdirAll(directory, 0o700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(directory, "journal.json"), test.journal(identifier), 0o600); err != nil {
				t.Fatal(err)
			}
			if err := recoverTransactions(root); err == nil {
				t.Fatal("corrupt recovery journal was accepted")
			}
			after, err := os.ReadFile(canonical)
			if err != nil || string(after) != string(before) {
				t.Fatalf("corrupt recovery mutated canonical content: %v", err)
			}
			if _, err := os.Stat(directory); err != nil {
				t.Fatalf("corrupt journal directory was deleted: %v", err)
			}
		})
	}
}

func TestRecoveryRejectsUnknownTransactionMaterialBeforeRollback(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("f", 32)
	target := filepath.Join(root, filepath.FromSlash(desiredDocument))
	original, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	_, beforeDigest, beforeIdentity, err := inspectWriterFile(target)
	if err != nil {
		t.Fatal(err)
	}
	beforeSecurity := mustCaptureCanonicalSecurity(t, target)
	transactionOutput := []byte("published transaction output\n")
	replacement := filepath.Join(filepath.Dir(target), ".unknown-material-output")
	if err := os.WriteFile(replacement, transactionOutput, 0o600); err != nil {
		t.Fatal(err)
	}
	mustApplyCanonicalSecurity(t, replacement, beforeSecurity)
	_, _, outputIdentity, err := inspectWriterFile(replacement)
	if err != nil {
		t.Fatal(err)
	}
	if err := atomicReplace(replacement, target); err != nil {
		t.Fatal(err)
	}
	journal := transactionJournal{TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1,
		Documents: []transactionDocument{{LogicalPath: desiredDocument, Existed: true, Mode: 0o600,
			Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
			BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity,
			AfterDigest: digestBytes(transactionOutput), OutputIdentity: outputIdentity}}}
	directory := writeRecoveryJournal(t, root, identifier, journal)
	if err := os.WriteFile(filepath.Join(directory, "000.before"), original, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "unknown.bin"), []byte("external"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err == nil {
		t.Fatal("unknown transaction material was accepted")
	}
	current, err := os.ReadFile(target)
	if err != nil || string(current) != string(transactionOutput) {
		t.Fatalf("recovery mutated canonical bytes before validating transaction directory: %q, %v", current, err)
	}
}

func TestPreparationFailureUnwindsCreatedParents(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("e", 32)
	logical := managedHostDocument("preparation-node")
	parent := filepath.Join(root, "inventory", "host_vars", "preparation-node")
	originalPersist := persistTransactionJournal
	calls := 0
	persistTransactionJournal = func(path string, journal transactionJournal) error {
		calls++
		if calls == 2 {
			return errors.New("injected journal persistence failure")
		}
		return persistJournal(path, journal)
	}
	t.Cleanup(func() { persistTransactionJournal = originalPersist })

	err := (&Backend{replace: atomicReplace}).commitDocuments(root, identifier, []storedDocument{{
		LogicalPath: logical, After: []byte("managed\n"), Existed: false,
	}})
	if err == nil {
		t.Fatal("injected preparation failure was ignored")
	}
	if _, err := os.Stat(parent); !os.IsNotExist(err) {
		t.Fatalf("transaction-created parent remains after preparation failure: %v", err)
	}
	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(logical))); !os.IsNotExist(err) {
		t.Fatalf("canonical document appeared after preparation failure: %v", err)
	}
	if _, err := os.Stat(runtimePath(root, "edit-transactions", identifier)); !os.IsNotExist(err) {
		t.Fatalf("transaction artifacts remain after preparation failure: %v", err)
	}
}

func TestPreparingCrashWithUnjournaledIdentitiesRemainsRecoverable(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("d", 32)
	logical := managedHostDocument("crash-node")
	temporaryName := ".platform-installer-" + identifier + "-000.tmp"
	journal := transactionJournal{TransactionID: identifier, Phase: "PREPARING", Replacing: -1,
		Documents: []transactionDocument{{LogicalPath: logical, Existed: false, Mode: 0o600,
			Backup: "000.before", Temporary: temporaryName, AfterDigest: digestBytes([]byte("managed\n")),
			CreatedParents: []transactionParent{{LogicalPath: "inventory/host_vars/crash-node"}}}}}
	directory := writeRecoveryJournal(t, root, identifier, journal)
	parent := filepath.Join(root, "inventory", "host_vars", "crash-node")
	if err := os.Mkdir(parent, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, temporaryName), []byte("managed\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatalf("PREPARING crash was not recoverable: %v", err)
	}
	if _, err := os.Stat(directory); !os.IsNotExist(err) {
		t.Fatalf("transaction directory remains: %v", err)
	}
	if info, err := os.Stat(parent); err != nil || !info.IsDir() {
		t.Fatalf("unproven crash-window parent must be preserved: %v", err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatalf("future writes remain blocked after recovery: %v", err)
	}
}

func TestWriterLockCannotBeStolenByAge(t *testing.T) {
	root := t.TempDir()
	release, err := acquireWriterLock(t.Context(), root, 0)
	if err != nil {
		t.Fatal(err)
	}
	lockPath := runtimePath(root, "project-writer.lock")
	old := time.Now().Add(-24 * time.Hour)
	if err := os.Chtimes(lockPath, old, old); err != nil {
		release()
		t.Fatal(err)
	}
	if _, err := acquireWriterLock(t.Context(), root, 10*time.Millisecond); err == nil || err.Error() != "PROJECT_LOCKED" {
		release()
		t.Fatalf("aged live lock was stolen: %v", err)
	}
	release()
	secondRelease, err := acquireWriterLock(t.Context(), root, 0)
	if err != nil {
		t.Fatalf("released persistent lock cannot be reacquired: %v", err)
	}
	secondRelease()
}

func TestRecoveryRemovesEmptyPreJournalTransaction(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("a", 32)
	pending := runtimePath(root, "edit-transactions", "."+identifier+".preparing")
	if err := os.MkdirAll(pending, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatalf("empty pre-journal transaction blocked recovery: %v", err)
	}
	if _, err := os.Stat(pending); !os.IsNotExist(err) {
		t.Fatalf("empty pre-journal transaction remains: %v", err)
	}
}

func TestRecoveryRecognizesAlreadyRestoredPublishedDocument(t *testing.T) {
	root, cleanup := testProject(t)
	defer cleanup()
	identifier := strings.Repeat("7", 32)
	logical := []string{desiredDocument, "project.yml"}
	documents := make([]transactionDocument, 0, len(logical))
	originals := make([][]byte, 0, len(logical))
	directory := runtimePath(root, "edit-transactions", identifier)
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	for index, name := range logical {
		target := filepath.Join(root, filepath.FromSlash(name))
		before, err := os.ReadFile(target)
		if err != nil {
			t.Fatal(err)
		}
		originals = append(originals, before)
		_, beforeDigest, beforeIdentity, err := inspectWriterFile(target)
		if err != nil {
			t.Fatal(err)
		}
		beforeSecurity := mustCaptureCanonicalSecurity(t, target)
		if err := os.WriteFile(filepath.Join(directory, fmt.Sprintf("%03d.before", index)), before, 0o600); err != nil {
			t.Fatal(err)
		}
		after := []byte(fmt.Sprintf("transaction output %d\n", index))
		output := target + ".published"
		if err := os.WriteFile(output, after, 0o600); err != nil {
			t.Fatal(err)
		}
		mustApplyCanonicalSecurity(t, output, beforeSecurity)
		_, _, outputIdentity, err := inspectWriterFile(output)
		if err != nil {
			t.Fatal(err)
		}
		if err := atomicReplace(output, target); err != nil {
			t.Fatal(err)
		}
		documents = append(documents, transactionDocument{LogicalPath: name, Existed: true, Mode: 0o600,
			Backup: fmt.Sprintf("%03d.before", index), Temporary: fmt.Sprintf(".platform-installer-%s-%03d.tmp", identifier, index),
			BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity, AfterDigest: digestBytes(after), OutputIdentity: outputIdentity})
		if index == 1 {
			restored := target + ".restored"
			if err := os.WriteFile(restored, before, 0o600); err != nil {
				t.Fatal(err)
			}
			mustApplyCanonicalSecurity(t, restored, beforeSecurity)
			if err := atomicReplace(restored, target); err != nil {
				t.Fatal(err)
			}
			_, _, rollbackIdentity, err := inspectWriterFile(target)
			if err != nil {
				t.Fatal(err)
			}
			documents[index].RollbackIdentity = rollbackIdentity
		}
	}
	journal := transactionJournal{TransactionID: identifier, Phase: "REPLACING", Replacing: 1, Published: 1, Documents: documents}
	content, _ := json.Marshal(journal)
	if err := os.WriteFile(filepath.Join(directory, "journal.json"), content, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err != nil {
		t.Fatalf("recovery was not idempotent: %v", err)
	}
	for index, name := range logical {
		current, _ := os.ReadFile(filepath.Join(root, filepath.FromSlash(name)))
		if string(current) != string(originals[index]) {
			t.Fatalf("%s was not restored", name)
		}
	}
}

func TestRecoveryRejectsExternalSameContentRollbackSubstitution(t *testing.T) {
	root := t.TempDir()
	identifier := strings.Repeat("8", 32)
	logical := desiredDocument
	target := filepath.Join(root, filepath.FromSlash(logical))
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(target, []byte("before\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	before, err := os.ReadFile(target)
	if err != nil {
		t.Fatal(err)
	}
	_, beforeDigest, beforeIdentity, err := inspectWriterFile(target)
	if err != nil {
		t.Fatal(err)
	}
	beforeSecurity := mustCaptureCanonicalSecurity(t, target)
	directory := runtimePath(root, "edit-transactions", identifier)
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "000.before"), before, 0o600); err != nil {
		t.Fatal(err)
	}
	after := []byte("published output\n")
	output := target + ".published"
	if err := os.WriteFile(output, after, 0o600); err != nil {
		t.Fatal(err)
	}
	mustApplyCanonicalSecurity(t, output, beforeSecurity)
	_, _, outputIdentity, err := inspectWriterFile(output)
	if err != nil {
		t.Fatal(err)
	}
	if err := atomicReplace(output, target); err != nil {
		t.Fatal(err)
	}
	journal := transactionJournal{TransactionID: identifier, Phase: "PREPARED", Replacing: -1, Published: 1, Documents: []transactionDocument{{
		LogicalPath: logical, Existed: true, Mode: 0o600, Backup: "000.before", Temporary: ".platform-installer-" + identifier + "-000.tmp",
		BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity, AfterDigest: digestBytes(after), OutputIdentity: outputIdentity,
	}}}
	content, _ := json.Marshal(journal)
	if err := os.WriteFile(filepath.Join(directory, "journal.json"), content, 0o600); err != nil {
		t.Fatal(err)
	}
	external := target + ".external"
	if err := os.WriteFile(external, before, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := atomicReplace(external, target); err != nil {
		t.Fatal(err)
	}
	if err := recoverTransactions(root); err == nil {
		t.Fatal("recovery accepted an external same-content rollback substitution")
	}
	if current, readErr := os.ReadFile(target); readErr != nil || !bytes.Equal(current, before) {
		t.Fatalf("recovery mutated external replacement: %q, %v", current, readErr)
	}
}

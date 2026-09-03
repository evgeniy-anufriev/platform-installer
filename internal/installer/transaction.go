package installer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"

	"platform-installer/internal/coreadapter"
)

type transactionDocument struct {
	LogicalPath string `json:"logicalPath"`
	Existed     bool   `json:"existed"`
	Mode        uint32 `json:"mode"`
	Backup      string `json:"backup"`
	Temporary   string `json:"temporary"`
}

type transactionJournal struct {
	TransactionID string                `json:"transactionId"`
	Phase         string                `json:"phase"`
	Replacing     int                   `json:"replacingIndex"`
	Documents     []transactionDocument `json:"documents"`
}

func writeSynced(path string, content []byte, mode os.FileMode) error {
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
	if err != nil {
		return err
	}
	if _, err = file.Write(content); err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	return closeErr
}

func persistJournal(path string, journal transactionJournal) error {
	content, err := json.Marshal(journal)
	if err != nil {
		return err
	}
	directory := filepath.Dir(path)
	temporary, err := os.CreateTemp(directory, ".journal-")
	if err != nil {
		return err
	}
	temporaryPath := temporary.Name()
	defer os.Remove(temporaryPath)
	if err := temporary.Chmod(0o600); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(content); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	if err := atomicReplace(temporaryPath, path); err != nil {
		return err
	}
	return syncDirectory(directory)
}

func restoreTransaction(root, directory string, journal transactionJournal) error {
	var failures []error
	for _, document := range journal.Documents {
		target, err := safeProjectPath(root, document.LogicalPath, true)
		if err != nil {
			failures = append(failures, err)
			continue
		}
		if document.Existed {
			backup := filepath.Join(directory, document.Backup)
			content, readErr := os.ReadFile(backup)
			if readErr != nil {
				failures = append(failures, readErr)
				continue
			}
			temporary, createErr := os.CreateTemp(filepath.Dir(target), ".platform-installer-rollback-")
			if createErr != nil {
				failures = append(failures, createErr)
				continue
			}
			temporaryPath := temporary.Name()
			if chmodErr := temporary.Chmod(os.FileMode(document.Mode)); chmodErr != nil {
				temporary.Close()
				os.Remove(temporaryPath)
				failures = append(failures, chmodErr)
				continue
			}
			_, writeErr := temporary.Write(content)
			if writeErr == nil {
				writeErr = temporary.Sync()
			}
			closeErr := temporary.Close()
			if writeErr == nil {
				writeErr = closeErr
			}
			if writeErr == nil {
				writeErr = atomicReplace(temporaryPath, target)
			}
			if writeErr != nil {
				failures = append(failures, writeErr)
			}
			_ = os.Remove(temporaryPath)
		} else if err := os.Remove(target); err != nil && !os.IsNotExist(err) {
			failures = append(failures, err)
		}
		if document.Temporary != "" {
			_ = os.Remove(filepath.Join(filepath.Dir(target), document.Temporary))
		}
		_ = syncDirectory(filepath.Dir(target))
	}
	return errors.Join(failures...)
}

func recoverTransactions(root string) error {
	transactions := runtimePath(root, "edit-transactions")
	entries, err := os.ReadDir(transactions)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		directory := filepath.Join(transactions, entry.Name())
		content, err := os.ReadFile(filepath.Join(directory, "journal.json"))
		if os.IsNotExist(err) {
			if removeErr := os.RemoveAll(directory); removeErr != nil {
				return removeErr
			}
			continue
		}
		if err != nil {
			return blocked("RECOVERY_FAILED", "Writer transaction journal cannot be read", "transaction")
		}
		var journal transactionJournal
		if err := json.Unmarshal(content, &journal); err != nil {
			return blocked("RECOVERY_FAILED", "Writer transaction journal is invalid", "transaction")
		}
		if journal.Phase == "PREPARING" {
			for _, document := range journal.Documents {
				target, pathErr := safeProjectPath(root, document.LogicalPath, true)
				if pathErr != nil {
					return blocked("RECOVERY_FAILED", "Interrupted writer preparation path is invalid", "transaction")
				}
				_ = os.Remove(filepath.Join(filepath.Dir(target), document.Temporary))
			}
		} else if journal.Phase != "COMMITTED" {
			if err := restoreTransaction(root, directory, journal); err != nil {
				return blocked("RECOVERY_FAILED", "Interrupted writer transaction could not be restored", "transaction")
			}
		}
		if err := os.RemoveAll(directory); err != nil {
			return err
		}
	}
	return nil
}

func (b *Backend) commitDocuments(root, identifier string, documents []storedDocument) (resultErr error) {
	transactionRoot := runtimePath(root, "edit-transactions")
	if err := os.MkdirAll(transactionRoot, 0o700); err != nil {
		return err
	}
	if err := os.Chmod(transactionRoot, 0o700); err != nil {
		return err
	}
	directory := filepath.Join(transactionRoot, identifier)
	if err := os.Mkdir(directory, 0o700); err != nil {
		return err
	}
	cleanup := true
	committed := false
	journal := transactionJournal{TransactionID: identifier, Phase: "PREPARING", Replacing: -1}
	defer func() {
		if !cleanup && !committed {
			if err := restoreTransaction(root, directory, journal); err != nil {
				resultErr = blocked("ROLLBACK_FAILED", "Writer transaction failed and rollback did not complete", "transaction")
			} else if resultErr == nil {
				resultErr = blocked("WRITE_FAILED", "Writer transaction failed and original bytes were restored", "transaction")
			}
			cleanup = true
		}
		if cleanup {
			for _, document := range journal.Documents {
				if target, err := safeProjectPath(root, document.LogicalPath, true); err == nil {
					_ = os.Remove(filepath.Join(filepath.Dir(target), document.Temporary))
				}
			}
			_ = os.RemoveAll(directory)
		}
	}()
	sort.Slice(documents, func(i, j int) bool { return documents[i].LogicalPath < documents[j].LogicalPath })
	for index, document := range documents {
		target, err := safeProjectPath(root, document.LogicalPath, false)
		if err != nil {
			return err
		}
		info, err := os.Stat(target)
		if err != nil {
			return err
		}
		backupName := fmt.Sprintf("%03d.before", index)
		temporaryName := fmt.Sprintf(".platform-installer-%s-%03d.tmp", identifier, index)
		journal.Documents = append(journal.Documents, transactionDocument{LogicalPath: document.LogicalPath,
			Existed: document.Existed, Mode: uint32(info.Mode().Perm()), Backup: backupName, Temporary: temporaryName})
	}
	journalPath := filepath.Join(directory, "journal.json")
	if err := persistJournal(journalPath, journal); err != nil {
		return err
	}
	for index, document := range documents {
		target, err := safeProjectPath(root, document.LogicalPath, false)
		if err != nil {
			return err
		}
		info, err := os.Stat(target)
		if err != nil {
			return err
		}
		backupName := journal.Documents[index].Backup
		if err := writeSynced(filepath.Join(directory, backupName), document.Before, 0o600); err != nil {
			return err
		}
		temporaryPath := filepath.Join(filepath.Dir(target), journal.Documents[index].Temporary)
		temporary, err := os.OpenFile(temporaryPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, info.Mode().Perm())
		if err != nil {
			return err
		}
		if err := temporary.Chmod(info.Mode().Perm()); err != nil {
			temporary.Close()
			return err
		}
		if _, err := temporary.Write(document.After); err != nil {
			temporary.Close()
			return err
		}
		if err := temporary.Sync(); err != nil {
			temporary.Close()
			return err
		}
		if err := temporary.Close(); err != nil {
			return err
		}
	}
	journal.Phase = "PREPARED"
	if err := persistJournal(journalPath, journal); err != nil {
		return err
	}
	cleanup = false
	for index, document := range journal.Documents {
		journal.Phase, journal.Replacing = "REPLACING", index
		if err := persistJournal(journalPath, journal); err != nil {
			return err
		}
		target, err := safeProjectPath(root, document.LogicalPath, false)
		if err != nil {
			return err
		}
		temporary := filepath.Join(filepath.Dir(target), document.Temporary)
		if err := b.replace(temporary, target); err != nil {
			if restoreErr := restoreTransaction(root, directory, journal); restoreErr != nil {
				return blocked("ROLLBACK_FAILED", "Writer transaction failed and rollback did not complete", "transaction")
			}
			cleanup = true
			return blocked("WRITE_FAILED", "Writer transaction failed and original bytes were restored", "transaction")
		}
		if err := syncDirectory(filepath.Dir(target)); err != nil {
			if restoreErr := restoreTransaction(root, directory, journal); restoreErr != nil {
				return blocked("ROLLBACK_FAILED", "Writer transaction failed and rollback did not complete", "transaction")
			}
			cleanup = true
			return blocked("WRITE_FAILED", "Writer transaction failed and original bytes were restored", "transaction")
		}
	}
	journal.Phase = "COMMITTED"
	if err := persistJournal(journalPath, journal); err != nil {
		return err
	}
	committed = true
	cleanup = true
	return nil
}

func acquireWriterLock(ctx context.Context, root string, wait time.Duration) (func(), error) {
	runtime := runtimePath(root)
	if err := os.MkdirAll(runtime, 0o700); err != nil {
		return nil, err
	}
	if err := os.Chmod(runtime, 0o700); err != nil {
		return nil, err
	}
	path := filepath.Join(runtime, "project-writer.lock")
	deadline := time.Now().Add(wait)
	for {
		file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err == nil {
			_, _ = fmt.Fprintf(file, "%d\n%d\n", os.Getpid(), time.Now().UnixNano())
			_ = file.Sync()
			_ = file.Close()
			return func() { _ = os.Remove(path) }, nil
		}
		if !os.IsExist(err) {
			return nil, err
		}
		if info, statErr := os.Stat(path); statErr == nil && time.Since(info.ModTime()) > 2*time.Minute {
			_ = os.Remove(path)
			continue
		}
		if time.Now().After(deadline) {
			return nil, blocked("PROJECT_LOCKED", "Project writer lock is busy", "project")
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(25 * time.Millisecond):
		}
	}
}

func resultBlocked(err error) EditCommitResult {
	finding := blocked("WRITE_FAILED", "Edit plan could not be committed", "project").finding()
	if typed, ok := err.(*writerError); ok {
		finding = typed.finding()
	}
	return EditCommitResult{APIVersion: EditResultAPIVersion, Kind: "EditCommitResult",
		Status: "BLOCKED", Changed: false, Finding: &finding}
}

func (b *Backend) CommitEditPlan(ctx context.Context, planID string) EditCommitResult {
	plan, found := b.plans.Get(planID)
	if !found {
		return resultBlocked(blocked("PLAN_EXPIRED", "Edit plan is absent or expired", "planId"))
	}
	release, err := acquireWriterLock(ctx, plan.ProjectRoot, b.lockWait)
	if err != nil {
		return resultBlocked(err)
	}
	defer release()
	if err := recoverTransactions(plan.ProjectRoot); err != nil {
		return resultBlocked(err)
	}
	documents, revision, err := collectProjectDocuments(plan.ProjectRoot)
	if err != nil {
		return resultBlocked(err)
	}
	digests := make(map[string]string, len(documents))
	for _, document := range documents {
		digests[document.LogicalPath] = document.Digest
	}
	for _, expected := range plan.Public.AffectedDocuments {
		if digests[expected.LogicalPath] != expected.BeforeDigest {
			return resultBlocked(blocked("DOCUMENT_CHANGED", "An affected document changed after planning", "document"))
		}
	}
	if revision != plan.Public.BaseProjectRevision {
		return resultBlocked(blocked("PROJECT_CHANGED", "Project changed after planning", "project"))
	}
	transactionStarted := b.now()
	if err := b.commitDocuments(plan.ProjectRoot, planID, plan.Documents); err != nil {
		return resultBlocked(err)
	}
	transactionDuration := b.now().Sub(transactionStarted)
	b.plans.Discard(planID)
	_, newRevision, revisionErr := collectProjectDocuments(plan.ProjectRoot)
	owned, ownedErr := discoverOwnedPaths(plan.ProjectRoot)
	snapshotStarted := b.now()
	var snapshot *coreadapter.Snapshot
	if revisionErr == nil && ownedErr == nil {
		snapshot, err = b.core.BuildSnapshot(ctx, plan.ProjectRoot, owned)
	} else {
		err = errors.Join(revisionErr, ownedErr)
	}
	snapshotDuration := b.now().Sub(snapshotStarted)
	if err != nil || snapshot.Status != "PASS" {
		return EditCommitResult{APIVersion: EditResultAPIVersion, Kind: "EditCommitResult",
			Status: "COMMITTED_REFRESH_FAILED", Changed: true,
			OldProjectRevision: plan.Public.BaseProjectRevision, NewProjectRevision: newRevision,
			AffectedDocuments: plan.Public.AffectedDocuments, ApplyRequired: true,
			Timing: CommitTiming{Transaction: transactionDuration, Snapshot: snapshotDuration}}
	}
	return EditCommitResult{APIVersion: EditResultAPIVersion, Kind: "EditCommitResult",
		Status: "COMMITTED", Changed: true, OldProjectRevision: plan.Public.BaseProjectRevision,
		NewProjectRevision: snapshot.ProjectRevision, AffectedDocuments: plan.Public.AffectedDocuments,
		Snapshot: snapshot, ApplyRequired: true,
		Timing: CommitTiming{Transaction: transactionDuration, Snapshot: snapshotDuration}}
}

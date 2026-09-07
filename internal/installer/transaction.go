package installer

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"platform-installer/internal/coreadapter"
)

const maxTransactionDocuments = 1024

type transactionParent struct {
	LogicalPath string `json:"logicalPath"`
	Identity    string `json:"identity"`
}

type transactionDocument struct {
	LogicalPath      string              `json:"logicalPath"`
	Existed          bool                `json:"existed"`
	Mode             uint32              `json:"mode"`
	Backup           string              `json:"backup"`
	Temporary        string              `json:"temporary"`
	BeforeDigest     string              `json:"beforeDigest,omitempty"`
	BeforeIdentity   string              `json:"beforeIdentity,omitempty"`
	BeforeSecurity   string              `json:"beforeSecurity,omitempty"`
	AfterDigest      string              `json:"afterDigest"`
	OutputIdentity   string              `json:"outputIdentity,omitempty"`
	RollbackIdentity string              `json:"rollbackIdentity,omitempty"`
	CreatedParents   []transactionParent `json:"createdParents,omitempty"`
}

type transactionJournal struct {
	TransactionID string                `json:"transactionId"`
	Phase         string                `json:"phase"`
	Replacing     int                   `json:"replacingIndex"`
	Published     int                   `json:"publishedCount"`
	Documents     []transactionDocument `json:"documents"`
}

func writeSynced(path string, content []byte, mode os.FileMode) error {
	file, err := createWriterFile(path, mode)
	if err != nil {
		return err
	}
	if err := hardenWriterFile(file, mode); err != nil {
		_ = file.Close()
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
	temporaryPath := filepath.Join(directory, "journal.next")
	temporary, err := createWriterFile(temporaryPath, 0o600)
	if err != nil {
		return err
	}
	defer os.Remove(temporaryPath)
	if err := hardenWriterFile(temporary, 0o600); err != nil {
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

var persistTransactionJournal = persistJournal

func validTransactionID(identifier string) bool {
	if len(identifier) != 32 {
		return false
	}
	for _, character := range identifier {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}

func pendingTransactionID(name string) (string, bool) {
	if len(name) != 43 || name[0] != '.' || !strings.HasSuffix(name, ".preparing") {
		return "", false
	}
	identifier := name[1:33]
	return identifier, validTransactionID(identifier)
}

func validDigest(value string) bool {
	if len(value) != 71 || !strings.HasPrefix(value, "sha256:") {
		return false
	}
	for _, character := range value[7:] {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') {
			return false
		}
	}
	return true
}

func validIdentity(value string) bool {
	if value == "" || len(value) > 128 {
		return false
	}
	for _, character := range value {
		if (character < '0' || character > '9') && (character < 'a' || character > 'f') && character != ':' {
			return false
		}
	}
	return true
}

func validManagedTransactionPath(logical string) bool {
	if logical == "project.yml" || logical == "ansible.cfg" || logical == "inventory/hosts.yml" || logical == desiredDocument {
		return true
	}
	parts := strings.Split(logical, "/")
	if len(parts) != 4 || parts[0] != "inventory" || parts[1] != "host_vars" || parts[3] != "platform-installer.yml" {
		return false
	}
	if parts[2] == "" || len(parts[2]) > 128 || parts[2] == "." || parts[2] == ".." {
		return false
	}
	for _, character := range parts[2] {
		if (character < 'a' || character > 'z') && (character < 'A' || character > 'Z') &&
			(character < '0' || character > '9') && character != '.' && character != '_' && character != '-' {
			return false
		}
	}
	return true
}

func decodeTransactionJournal(content []byte) (transactionJournal, error) {
	var journal transactionJournal
	decoder := json.NewDecoder(bytes.NewReader(content))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&journal); err != nil {
		return transactionJournal{}, err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return transactionJournal{}, errors.New("transaction journal has trailing content")
	}
	return journal, nil
}

func validateTransactionJournal(root, directory string, journal transactionJournal) error {
	identifier := filepath.Base(directory)
	if !validTransactionID(identifier) || journal.TransactionID != identifier || len(journal.Documents) == 0 || len(journal.Documents) > maxTransactionDocuments {
		return errors.New("transaction identity or document count is invalid")
	}
	if journal.Published < 0 || journal.Published > len(journal.Documents) {
		return errors.New("transaction published count is invalid")
	}
	switch journal.Phase {
	case "PREPARING":
		if journal.Published != 0 || journal.Replacing != -1 {
			return errors.New("preparing transaction indices are invalid")
		}
	case "PREPARED":
		if journal.Replacing != -1 {
			return errors.New("prepared transaction indices are invalid")
		}
	case "REPLACING":
		if journal.Replacing != journal.Published || journal.Replacing < 0 || journal.Replacing >= len(journal.Documents) {
			return errors.New("replacing transaction indices are invalid")
		}
	case "COMMITTED":
		if journal.Published != len(journal.Documents) || journal.Replacing != -1 {
			return errors.New("committed transaction indices are invalid")
		}
	default:
		return errors.New("transaction phase is invalid")
	}
	seenDocuments := make(map[string]bool)
	seenParents := make(map[string]bool)
	for index, document := range journal.Documents {
		if !validManagedTransactionPath(document.LogicalPath) || seenDocuments[strings.ToLower(document.LogicalPath)] || document.Mode == 0 || document.Mode > 0o777 || !validDigest(document.AfterDigest) {
			return errors.New("transaction document is invalid")
		}
		seenDocuments[strings.ToLower(document.LogicalPath)] = true
		if document.Backup != fmt.Sprintf("%03d.before", index) || document.Temporary != fmt.Sprintf(".platform-installer-%s-%03d.tmp", identifier, index) {
			return errors.New("transaction artifact name is invalid")
		}
		if document.Existed {
			if !validDigest(document.BeforeDigest) || !validIdentity(document.BeforeIdentity) || !validCanonicalSecurity(document.BeforeSecurity) {
				return errors.New("transaction before-state is invalid")
			}
		} else if document.BeforeDigest != "" || document.BeforeIdentity != "" || document.BeforeSecurity != "" {
			return errors.New("new transaction document has a before-state")
		}
		if journal.Phase != "PREPARING" && !validIdentity(document.OutputIdentity) {
			return errors.New("prepared transaction output identity is invalid")
		}
		if document.OutputIdentity != "" && !validIdentity(document.OutputIdentity) {
			return errors.New("transaction output identity is invalid")
		}
		if document.RollbackIdentity != "" && (!document.Existed || !validIdentity(document.RollbackIdentity)) {
			return errors.New("transaction rollback identity is invalid")
		}
		target, err := safeProjectPath(root, document.LogicalPath, true)
		if err != nil {
			return err
		}
		for _, parent := range document.CreatedParents {
			if (parent.Identity != "" && !validIdentity(parent.Identity)) ||
				(parent.Identity == "" && journal.Phase != "PREPARING") ||
				seenParents[strings.ToLower(parent.LogicalPath)] {
				return errors.New("transaction created parent is invalid")
			}
			parentPath, err := safeProjectPath(root, parent.LogicalPath, true)
			if err != nil {
				return err
			}
			relative, err := filepath.Rel(parentPath, filepath.Dir(target))
			if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
				return errors.New("transaction created parent is not a document ancestor")
			}
			seenParents[strings.ToLower(parent.LogicalPath)] = true
		}
	}
	return nil
}

func inspectWriterFile(path string) (bool, string, string, error) {
	linked, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return false, "", "", nil
	}
	if err != nil || pathEntryUnsafe(linked) || !linked.Mode().IsRegular() {
		return false, "", "", errors.New("writer target is unsafe")
	}
	file, err := os.Open(path)
	if err != nil {
		return false, "", "", err
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !os.SameFile(opened, linked) {
		return false, "", "", errors.New("writer target changed while opening")
	}
	identity, err := writerFileIdentity(file)
	if err != nil {
		return false, "", "", err
	}
	content, err := io.ReadAll(file)
	if err != nil {
		return false, "", "", err
	}
	after, err := file.Stat()
	if err != nil || !os.SameFile(opened, after) {
		return false, "", "", errors.New("writer target changed while reading")
	}
	return true, digestBytes(content), identity, nil
}

func openAndHarden(path string, mode os.FileMode) (*os.File, string, error) {
	file, err := openWriterSecurityHandle(path)
	if err != nil {
		return nil, "", err
	}
	linked, linkErr := os.Lstat(path)
	opened, statErr := file.Stat()
	if linkErr != nil || statErr != nil || pathEntryUnsafe(linked) || !os.SameFile(opened, linked) {
		file.Close()
		return nil, "", errors.New("writer path changed while opening")
	}
	if err := hardenWriterFile(file, mode); err != nil {
		file.Close()
		return nil, "", err
	}
	identity, err := writerFileIdentity(file)
	if err != nil {
		file.Close()
		return nil, "", err
	}
	return file, identity, nil
}

func inspectWriterDirectory(path string) (bool, string, error) {
	linked, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return false, "", nil
	}
	if err != nil || !linked.IsDir() || pathEntryUnsafe(linked) {
		return false, "", errors.New("writer directory is unsafe")
	}
	directory, err := os.Open(path)
	if err != nil {
		return false, "", err
	}
	defer directory.Close()
	opened, err := directory.Stat()
	if err != nil || !os.SameFile(opened, linked) {
		return false, "", errors.New("writer directory changed while opening")
	}
	identity, err := writerFileIdentity(directory)
	return true, identity, err
}

func missingManagedParents(root, logical string) ([]string, error) {
	target, err := safeProjectPath(root, logical, true)
	if err != nil {
		return nil, err
	}
	relative, err := filepath.Rel(root, filepath.Dir(target))
	if err != nil {
		return nil, err
	}
	if relative == "." {
		return nil, nil
	}
	current := root
	var missing []string
	parentMissing := false
	for _, part := range strings.Split(filepath.ToSlash(relative), "/") {
		current = filepath.Join(current, part)
		if parentMissing {
			item, _ := filepath.Rel(root, current)
			missing = append(missing, filepath.ToSlash(item))
			continue
		}
		info, statErr := os.Lstat(current)
		if statErr == nil {
			if !info.IsDir() || pathEntryUnsafe(info) {
				return nil, blocked("PATH_UNSAFE", "Managed document parent is unsafe", "document.logicalPath")
			}
			continue
		}
		if !os.IsNotExist(statErr) {
			return nil, statErr
		}
		parentMissing = true
		item, err := filepath.Rel(root, current)
		if err != nil {
			return nil, err
		}
		missing = append(missing, filepath.ToSlash(item))
	}
	return missing, nil
}

func safeRuntimeDirectory(root string, elements ...string) (string, error) {
	current := root
	for _, element := range append([]string{".runtime"}, elements...) {
		if element == "" || element == "." || element == ".." || filepath.Base(element) != element {
			return "", blocked("PATH_UNSAFE", "Writer runtime path is invalid", "transaction")
		}
		current = filepath.Join(current, element)
		info, err := os.Lstat(current)
		if err == nil {
			if !info.IsDir() || pathEntryUnsafe(info) {
				return "", blocked("PATH_UNSAFE", "Writer runtime path is unsafe", "transaction")
			}
			directory, _, err := openAndHarden(current, 0o700)
			if err != nil {
				return "", err
			}
			if err := directory.Close(); err != nil {
				return "", err
			}
			continue
		}
		if !os.IsNotExist(err) {
			return "", err
		}
		if err := os.Mkdir(current, 0o700); err != nil {
			return "", err
		}
		directory, _, err := openAndHarden(current, 0o700)
		if err != nil {
			return "", err
		}
		if err := directory.Close(); err != nil {
			return "", err
		}
	}
	return current, nil
}

func cleanupCreatedParents(root string, documents []transactionDocument) error {
	var failures []error
	for documentIndex := len(documents) - 1; documentIndex >= 0; documentIndex-- {
		parents := documents[documentIndex].CreatedParents
		for parentIndex := len(parents) - 1; parentIndex >= 0; parentIndex-- {
			parent := parents[parentIndex]
			path, err := safeProjectPath(root, parent.LogicalPath, true)
			if err != nil {
				failures = append(failures, err)
				continue
			}
			exists, identity, err := inspectWriterDirectory(path)
			if err != nil {
				failures = append(failures, err)
				continue
			}
			if !exists {
				continue
			}
			if parent.Identity == "" {
				// A crash can occur after mkdir but before its identity is journaled.
				// Preserve an unproven empty parent; it is not canonical document state.
				continue
			}
			if identity != parent.Identity {
				failures = append(failures, errors.New("transaction-created parent identity changed"))
				continue
			}
			if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
				// An external file may now legitimately use this transaction-created
				// directory. Leave a non-empty directory in place rather than deleting it.
				continue
			}
		}
	}
	return errors.Join(failures...)
}

func validateCleanupArtifacts(root, directory string, journal transactionJournal) error {
	for index, document := range journal.Documents {
		temporary := filepath.Join(directory, document.Temporary)
		exists, _, identity, err := inspectWriterFile(temporary)
		if err != nil {
			return err
		}
		if exists && document.OutputIdentity != "" && identity != document.OutputIdentity {
			return errors.New("transaction temporary identity changed")
		}
		rollback := filepath.Join(directory, fmt.Sprintf("%03d.rollback", index))
		exists, digest, identity, err := inspectWriterFile(rollback)
		if err != nil {
			return err
		}
		if exists && (document.RollbackIdentity == "" || identity != document.RollbackIdentity || digest != document.BeforeDigest) {
			return errors.New("transaction rollback temporary changed")
		}
		for _, parent := range document.CreatedParents {
			path, err := safeProjectPath(root, parent.LogicalPath, true)
			if err != nil {
				return err
			}
			exists, identity, err := inspectWriterDirectory(path)
			if err != nil {
				return err
			}
			if exists && parent.Identity != "" && identity != parent.Identity {
				return errors.New("transaction-created parent identity changed")
			}
		}
	}
	return nil
}

func cleanupPreparedArtifacts(root, directory string, journal transactionJournal) error {
	if err := validateCleanupArtifacts(root, directory, journal); err != nil {
		return err
	}
	var failures []error
	for index, document := range journal.Documents {
		temporary := filepath.Join(directory, document.Temporary)
		if err := os.Remove(temporary); err != nil && !errors.Is(err, os.ErrNotExist) {
			failures = append(failures, err)
		}
		if err := os.Remove(filepath.Join(directory, fmt.Sprintf("%03d.rollback", index))); err != nil && !errors.Is(err, os.ErrNotExist) {
			failures = append(failures, err)
		}
	}
	return errors.Join(append(failures, cleanupCreatedParents(root, journal.Documents))...)
}

func transactionSecurityMatches(target string, document transactionDocument) (bool, error) {
	if !document.Existed {
		return true, nil
	}
	return canonicalSecurityMatches(target, document.BeforeSecurity)
}

func restoreTransaction(root, directory string, journal transactionJournal) error {
	if err := validateTransactionJournal(root, directory, journal); err != nil {
		return err
	}
	if err := validateCleanupArtifacts(root, directory, journal); err != nil {
		return err
	}
	published := journal.Published
	if journal.Phase == "REPLACING" {
		document := journal.Documents[journal.Replacing]
		target, err := safeProjectPath(root, document.LogicalPath, true)
		if err != nil {
			return err
		}
		exists, digest, identity, err := inspectWriterFile(target)
		if err != nil {
			return err
		}
		securityMatches := !document.Existed
		if exists && document.Existed {
			securityMatches, err = transactionSecurityMatches(target, document)
			if err != nil {
				return err
			}
		}
		if exists && digest == document.AfterDigest && identity == document.OutputIdentity && securityMatches {
			published++
		} else if document.Existed {
			matchesBeforeIdentity := identity == document.BeforeIdentity || (document.RollbackIdentity != "" && identity == document.RollbackIdentity)
			if !exists || digest != document.BeforeDigest || !matchesBeforeIdentity || !securityMatches {
				return errors.New("replacing transaction target has an unknown state")
			}
		} else if exists {
			return errors.New("replacing transaction target has an unknown state")
		}
	}
	for index := 0; index < published; index++ {
		document := journal.Documents[index]
		target, err := safeProjectPath(root, document.LogicalPath, true)
		if err != nil {
			return err
		}
		exists, digest, identity, err := inspectWriterFile(target)
		if err != nil {
			return err
		}
		securityMatches := !document.Existed
		if exists && document.Existed {
			securityMatches, err = transactionSecurityMatches(target, document)
			if err != nil {
				return err
			}
		}
		matchesOutput := exists && digest == document.AfterDigest && identity == document.OutputIdentity && securityMatches
		matchesBefore := (!document.Existed && !exists) || (document.Existed && exists && digest == document.BeforeDigest &&
			(identity == document.BeforeIdentity || (document.RollbackIdentity != "" && identity == document.RollbackIdentity)) && securityMatches)
		if !matchesOutput && !matchesBefore {
			return errors.New("published transaction target was changed externally")
		}
		if document.Existed {
			backup := filepath.Join(directory, document.Backup)
			backupExists, backupDigest, _, err := inspectWriterFile(backup)
			if err != nil || !backupExists || backupDigest != document.BeforeDigest {
				return errors.New("transaction backup is invalid")
			}
		}
	}
	for index := published - 1; index >= 0; index-- {
		document := journal.Documents[index]
		target, _ := safeProjectPath(root, document.LogicalPath, true)
		exists, digest, identity, err := inspectWriterFile(target)
		if err != nil {
			return err
		}
		securityMatches := !document.Existed
		if exists && document.Existed {
			securityMatches, err = transactionSecurityMatches(target, document)
			if err != nil {
				return err
			}
		}
		matchesBefore := (!document.Existed && !exists) || (document.Existed && exists && digest == document.BeforeDigest &&
			(identity == document.BeforeIdentity || (document.RollbackIdentity != "" && identity == document.RollbackIdentity)) && securityMatches)
		if matchesBefore {
			continue
		}
		if !exists || digest != document.AfterDigest || identity != document.OutputIdentity || !securityMatches {
			return errors.New("published transaction target changed during rollback")
		}
		if document.Existed {
			temporaryPath := filepath.Join(directory, fmt.Sprintf("%03d.rollback", index))
			if document.RollbackIdentity == "" {
				content, err := os.ReadFile(filepath.Join(directory, document.Backup))
				if err != nil {
					return err
				}
				temporary, err := createWriterFile(temporaryPath, os.FileMode(document.Mode))
				if err != nil {
					return err
				}
				if err := hardenWriterFile(temporary, os.FileMode(document.Mode)); err == nil {
					err = applyCanonicalSecurity(document.BeforeSecurity, temporary)
					if err == nil {
						_, err = temporary.Write(content)
					}
					if err == nil {
						err = temporary.Sync()
					}
				}
				if err == nil {
					document.RollbackIdentity, err = writerFileIdentity(temporary)
				}
				closeErr := temporary.Close()
				if err == nil {
					err = closeErr
				}
				if err != nil {
					_ = os.Remove(temporaryPath)
					return err
				}
				journal.Documents[index].RollbackIdentity = document.RollbackIdentity
				if err := persistTransactionJournal(filepath.Join(directory, "journal.json"), journal); err != nil {
					return err
				}
			} else {
				rollbackExists, rollbackDigest, rollbackIdentity, err := inspectWriterFile(temporaryPath)
				if err != nil || !rollbackExists || rollbackDigest != document.BeforeDigest || rollbackIdentity != document.RollbackIdentity {
					return errors.New("transaction rollback temporary is invalid")
				}
			}
			rollbackSecurityMatches, rollbackSecurityErr := canonicalSecurityMatches(temporaryPath, document.BeforeSecurity)
			if rollbackSecurityErr != nil || !rollbackSecurityMatches {
				return errors.New("transaction rollback temporary security is invalid")
			}
			currentExists, currentDigest, currentIdentity, currentErr := inspectWriterFile(target)
			if currentErr != nil {
				return currentErr
			}
			currentSecurityMatches, currentSecurityErr := transactionSecurityMatches(target, document)
			if currentSecurityErr != nil || !currentExists || currentDigest != document.AfterDigest || currentIdentity != document.OutputIdentity || !currentSecurityMatches {
				return errors.New("published transaction target changed immediately before rollback")
			}
			if err := atomicReplace(temporaryPath, target); err != nil {
				return err
			}
			restored, restoredDigest, restoredIdentity, err := inspectWriterFile(target)
			if err != nil || !restored || restoredDigest != document.BeforeDigest || restoredIdentity != document.RollbackIdentity {
				return errors.New("transaction rollback output could not be verified")
			}
			securityMatches, securityErr := transactionSecurityMatches(target, document)
			if securityErr != nil || !securityMatches {
				return errors.New("transaction rollback security could not be verified")
			}
		} else if err := os.Remove(target); err != nil {
			return err
		}
		if err := syncDirectory(filepath.Dir(target)); err != nil {
			return err
		}
	}
	return cleanupPreparedArtifacts(root, directory, journal)
}

func cleanupTransactionDirectory(directory string, journal transactionJournal) error {
	if err := validateTransactionDirectory(directory, journal); err != nil {
		return err
	}
	entries, err := os.ReadDir(directory)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if err := os.Remove(filepath.Join(directory, entry.Name())); err != nil {
			return err
		}
	}
	return os.Remove(directory)
}

func validateTransactionDirectory(directory string, journal transactionJournal) error {
	allowed := map[string]bool{"journal.json": true, "journal.next": true}
	for _, document := range journal.Documents {
		allowed[document.Backup] = true
		allowed[document.Temporary] = true
	}
	for index := range journal.Documents {
		allowed[fmt.Sprintf("%03d.rollback", index)] = true
	}
	entries, err := os.ReadDir(directory)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		info, infoErr := entry.Info()
		if infoErr != nil || !allowed[entry.Name()] || entry.IsDir() || pathEntryUnsafe(info) || !info.Mode().IsRegular() {
			return errors.New("transaction directory contains unknown material")
		}
	}
	return nil
}

func recoverTransactions(root string) error {
	if err := assertSafeExistingAncestors(root); err != nil {
		return err
	}
	transactions, err := safeRuntimeDirectory(root, "edit-transactions")
	if err != nil {
		return err
	}
	entries, err := os.ReadDir(transactions)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		identifier, pending := pendingTransactionID(entry.Name())
		if !pending {
			continue
		}
		pendingDirectory := filepath.Join(transactions, entry.Name())
		info, statErr := os.Lstat(pendingDirectory)
		if statErr != nil || !info.IsDir() || pathEntryUnsafe(info) {
			return blocked("RECOVERY_FAILED", "Pending writer transaction directory is unsafe", "transaction")
		}
		pendingEntries, readErr := os.ReadDir(pendingDirectory)
		if readErr != nil {
			return blocked("RECOVERY_FAILED", "Pending writer transaction cannot be read", "transaction")
		}
		if len(pendingEntries) == 0 {
			if removeErr := os.Remove(pendingDirectory); removeErr != nil {
				return blocked("RECOVERY_FAILED", "Empty pending writer transaction cannot be removed", "transaction")
			}
			continue
		}
		content, readErr := os.ReadFile(filepath.Join(pendingDirectory, "journal.json"))
		journal, decodeErr := decodeTransactionJournal(content)
		finalDirectory := filepath.Join(transactions, identifier)
		if readErr != nil || decodeErr != nil || validateTransactionJournal(root, finalDirectory, journal) != nil || validateTransactionDirectory(pendingDirectory, journal) != nil {
			return blocked("RECOVERY_FAILED", "Pending writer transaction is invalid", "transaction")
		}
		if _, statErr := os.Lstat(finalDirectory); !os.IsNotExist(statErr) {
			return blocked("RECOVERY_FAILED", "Pending writer transaction conflicts with an active journal", "transaction")
		}
		if renameErr := os.Rename(pendingDirectory, finalDirectory); renameErr != nil {
			return blocked("RECOVERY_FAILED", "Pending writer transaction cannot be activated", "transaction")
		}
		if syncErr := syncDirectory(transactions); syncErr != nil {
			return syncErr
		}
	}
	entries, err = os.ReadDir(transactions)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if !entry.IsDir() || !validTransactionID(entry.Name()) {
			return blocked("RECOVERY_FAILED", "Writer transaction entry is invalid", "transaction")
		}
		directory := filepath.Join(transactions, entry.Name())
		info, statErr := os.Lstat(directory)
		if statErr != nil || !info.IsDir() || pathEntryUnsafe(info) {
			return blocked("RECOVERY_FAILED", "Writer transaction directory is unsafe", "transaction")
		}
		content, err := os.ReadFile(filepath.Join(directory, "journal.json"))
		if os.IsNotExist(err) {
			return blocked("RECOVERY_FAILED", "Writer transaction journal is missing", "transaction")
		}
		if err != nil {
			return blocked("RECOVERY_FAILED", "Writer transaction journal cannot be read", "transaction")
		}
		journal, err := decodeTransactionJournal(content)
		if err != nil || validateTransactionJournal(root, directory, journal) != nil {
			return blocked("RECOVERY_FAILED", "Writer transaction journal is invalid", "transaction")
		}
		if err := validateTransactionDirectory(directory, journal); err != nil {
			return blocked("RECOVERY_FAILED", "Writer transaction directory is invalid", "transaction")
		}
		if journal.Phase == "PREPARING" {
			if err := cleanupPreparedArtifacts(root, directory, journal); err != nil {
				return blocked("RECOVERY_FAILED", "Interrupted writer preparation could not be cleaned", "transaction")
			}
		} else if journal.Phase != "COMMITTED" {
			if err := restoreTransaction(root, directory, journal); err != nil {
				return blocked("RECOVERY_FAILED", "Interrupted writer transaction could not be restored", "transaction")
			}
		}
		if err := cleanupTransactionDirectory(directory, journal); err != nil {
			return err
		}
	}
	return nil
}

func (b *Backend) commitDocuments(root, identifier string, documents []storedDocument) (resultErr error) {
	if !validTransactionID(identifier) || len(documents) == 0 || len(documents) > maxTransactionDocuments {
		return blocked("WRITE_FAILED", "Writer transaction identity or document count is invalid", "transaction")
	}
	if err := assertSafeExistingAncestors(root); err != nil {
		return err
	}
	transactionRoot, err := safeRuntimeDirectory(root, "edit-transactions")
	if err != nil {
		return err
	}
	transactionRootHandle, _, err := openAndHarden(transactionRoot, 0o700)
	if err != nil {
		return err
	}
	if err := transactionRootHandle.Close(); err != nil {
		return err
	}
	directory := filepath.Join(transactionRoot, identifier)
	journal := transactionJournal{TransactionID: identifier, Phase: "PREPARING", Replacing: -1, Published: 0}
	sort.Slice(documents, func(i, j int) bool { return documents[i].LogicalPath < documents[j].LogicalPath })
	claimedParents := make(map[string]bool)
	for index, document := range documents {
		if !validManagedTransactionPath(document.LogicalPath) {
			return blocked("WRITE_FAILED", "Writer transaction document is outside the managed allow-list", "document")
		}
		target, err := safeProjectPath(root, document.LogicalPath, !document.Existed)
		if err != nil {
			return err
		}
		mode := os.FileMode(0o644)
		beforeDigest := ""
		beforeIdentity := ""
		beforeSecurity := ""
		if document.Existed {
			exists, currentDigest, currentIdentity, inspectErr := inspectWriterFile(target)
			if inspectErr != nil {
				return inspectErr
			}
			if !exists || currentDigest != digestBytes(document.Before) {
				return blocked("DOCUMENT_CHANGED", "An affected document changed before transaction preparation", "document")
			}
			info, statErr := os.Stat(target)
			if statErr != nil {
				return statErr
			}
			mode, beforeDigest, beforeIdentity = info.Mode().Perm(), currentDigest, currentIdentity
			beforeSecurity, err = captureCanonicalSecurity(target)
			if err != nil {
				return err
			}
		} else if _, statErr := os.Lstat(target); statErr == nil {
			return blocked("DOCUMENT_CHANGED", "A planned new document now exists", "document")
		} else if !os.IsNotExist(statErr) {
			return statErr
		}
		backupName := fmt.Sprintf("%03d.before", index)
		temporaryName := fmt.Sprintf(".platform-installer-%s-%03d.tmp", identifier, index)
		missingParents, parentErr := missingManagedParents(root, document.LogicalPath)
		if parentErr != nil {
			return parentErr
		}
		createdParents := make([]transactionParent, 0, len(missingParents))
		for _, parent := range missingParents {
			key := strings.ToLower(parent)
			if !claimedParents[key] {
				claimedParents[key] = true
				createdParents = append(createdParents, transactionParent{LogicalPath: parent})
			}
		}
		journal.Documents = append(journal.Documents, transactionDocument{LogicalPath: document.LogicalPath,
			Existed: document.Existed, Mode: uint32(mode), Backup: backupName, Temporary: temporaryName,
			BeforeDigest: beforeDigest, BeforeIdentity: beforeIdentity, BeforeSecurity: beforeSecurity, AfterDigest: digestBytes(document.After),
			CreatedParents: createdParents})
	}
	pendingDirectory := filepath.Join(transactionRoot, "."+identifier+".preparing")
	if err := os.Mkdir(pendingDirectory, 0o700); err != nil {
		return err
	}
	pending := true
	defer func() {
		if pending {
			_ = os.Remove(filepath.Join(pendingDirectory, "journal.next"))
			_ = os.Remove(filepath.Join(pendingDirectory, "journal.json"))
			_ = os.Remove(pendingDirectory)
		}
	}()
	directoryHandle, _, err := openAndHarden(pendingDirectory, 0o700)
	if err != nil {
		return err
	}
	if err := directoryHandle.Close(); err != nil {
		return err
	}
	if err := persistTransactionJournal(filepath.Join(pendingDirectory, "journal.json"), journal); err != nil {
		return err
	}
	if err := os.Rename(pendingDirectory, directory); err != nil {
		return err
	}
	pending = false
	journalPath := filepath.Join(directory, "journal.json")
	committed := false
	defer func() {
		if committed {
			_ = cleanupTransactionDirectory(directory, journal)
			return
		}
		var cleanupErr error
		if journal.Published > 0 || journal.Phase == "REPLACING" {
			cleanupErr = restoreTransaction(root, directory, journal)
		} else {
			cleanupErr = cleanupPreparedArtifacts(root, directory, journal)
		}
		if cleanupErr != nil {
			resultErr = blocked("ROLLBACK_FAILED", "Writer transaction failed and rollback did not complete", "transaction")
			return
		}
		_ = cleanupTransactionDirectory(directory, journal)
		if resultErr == nil {
			resultErr = blocked("WRITE_FAILED", "Writer transaction failed and original bytes were restored", "transaction")
		}
	}()
	if err := syncDirectory(transactionRoot); err != nil {
		return err
	}
	for documentIndex := range journal.Documents {
		for parentIndex := range journal.Documents[documentIndex].CreatedParents {
			parent := &journal.Documents[documentIndex].CreatedParents[parentIndex]
			path, err := safeProjectPath(root, parent.LogicalPath, true)
			if err != nil {
				return err
			}
			if err := os.Mkdir(path, 0o755); err != nil {
				return err
			}
			exists, createdIdentity, inspectErr := inspectWriterDirectory(path)
			if inspectErr != nil || !exists {
				return errors.New("transaction-created parent identity is unavailable")
			}
			parent.Identity = createdIdentity
			if err := finalizeCanonicalDirectory(path, 0o755); err != nil {
				return err
			}
			exists, identity, inspectErr := inspectWriterDirectory(path)
			if inspectErr != nil || !exists || identity != parent.Identity {
				return errors.New("transaction-created parent changed during hardening")
			}
			if err := persistTransactionJournal(journalPath, journal); err != nil {
				return err
			}
		}
	}
	for index, document := range documents {
		if _, err := safeProjectPath(root, document.LogicalPath, !document.Existed); err != nil {
			return err
		}
		backupName := journal.Documents[index].Backup
		if document.Existed {
			if err := writeSynced(filepath.Join(directory, backupName), document.Before, 0o600); err != nil {
				return err
			}
		}
		temporaryPath := filepath.Join(directory, journal.Documents[index].Temporary)
		mode := os.FileMode(journal.Documents[index].Mode)
		temporary, err := createWriterFile(temporaryPath, mode)
		if err != nil {
			return err
		}
		if err := hardenWriterFile(temporary, mode); err != nil {
			temporary.Close()
			return err
		}
		if document.Existed {
			if err := applyCanonicalSecurity(journal.Documents[index].BeforeSecurity, temporary); err != nil {
				temporary.Close()
				return errors.New("canonical document ACL could not be preserved")
			}
		}
		if _, err := temporary.Write(document.After); err != nil {
			temporary.Close()
			return err
		}
		if err := temporary.Sync(); err != nil {
			temporary.Close()
			return err
		}
		identity, err := writerFileIdentity(temporary)
		if err != nil {
			temporary.Close()
			return err
		}
		if err := temporary.Close(); err != nil {
			return err
		}
		journal.Documents[index].OutputIdentity = identity
		if err := persistTransactionJournal(journalPath, journal); err != nil {
			return err
		}
	}
	journal.Phase = "PREPARED"
	if err := persistTransactionJournal(journalPath, journal); err != nil {
		return err
	}
	for index, document := range journal.Documents {
		if err := assertSafeExistingAncestors(root); err != nil {
			return err
		}
		journal.Phase, journal.Replacing = "REPLACING", index
		if err := persistTransactionJournal(journalPath, journal); err != nil {
			return err
		}
		target, err := safeProjectPath(root, document.LogicalPath, !document.Existed)
		if err != nil {
			return err
		}
		if document.Existed {
			exists, digest, identity, inspectErr := inspectWriterFile(target)
			securityMatches, securityErr := transactionSecurityMatches(target, document)
			if inspectErr != nil || securityErr != nil || !exists || digest != document.BeforeDigest || identity != document.BeforeIdentity || !securityMatches {
				return blocked("DOCUMENT_CHANGED", "An affected document changed during transaction", "document")
			}
		} else {
			exists, _, _, inspectErr := inspectWriterFile(target)
			if inspectErr != nil || exists {
				return blocked("DOCUMENT_CHANGED", "A planned new document appeared during transaction", "document")
			}
		}
		temporary := filepath.Join(directory, document.Temporary)
		if err := b.replace(temporary, target); err != nil {
			return err
		}
		if err := finalizeCanonicalACL(target, document.Existed); err != nil {
			return err
		}
		if err := syncDirectory(filepath.Dir(target)); err != nil {
			return err
		}
		exists, digest, identity, err := inspectWriterFile(target)
		if err != nil || !exists || digest != document.AfterDigest || identity != document.OutputIdentity {
			return errors.New("published transaction output could not be verified")
		}
		securityMatches, securityErr := transactionSecurityMatches(target, document)
		if securityErr != nil || !securityMatches {
			return errors.New("published transaction security could not be verified")
		}
		journal.Phase, journal.Replacing, journal.Published = "PREPARED", -1, index+1
		if err := persistTransactionJournal(journalPath, journal); err != nil {
			return err
		}
	}
	journal.Phase, journal.Replacing, journal.Published = "COMMITTED", -1, len(journal.Documents)
	if err := persistTransactionJournal(journalPath, journal); err != nil {
		return err
	}
	committed = true
	return nil
}

func acquireWriterLock(ctx context.Context, root string, wait time.Duration) (func(), error) {
	runtime, err := safeRuntimeDirectory(root)
	if err != nil {
		return nil, err
	}
	runtimeHandle, _, err := openAndHarden(runtime, 0o700)
	if err != nil {
		return nil, err
	}
	if err := runtimeHandle.Close(); err != nil {
		return nil, err
	}
	path := filepath.Join(runtime, "project-writer.lock")
	deadline := time.Now().Add(wait)
	for {
		linked, statErr := os.Lstat(path)
		if statErr == nil && (!linked.Mode().IsRegular() || pathEntryUnsafe(linked)) {
			return nil, blocked("PATH_UNSAFE", "Writer lock path is unsafe", "project")
		}
		if statErr != nil && !os.IsNotExist(statErr) {
			return nil, statErr
		}
		file, err := openWriterLockFile(path)
		if err != nil {
			return nil, err
		}
		if err := hardenWriterFile(file, 0o600); err != nil {
			_ = file.Close()
			return nil, err
		}
		opened, err := file.Stat()
		current, currentErr := os.Lstat(path)
		if err != nil || currentErr != nil || !current.Mode().IsRegular() || pathEntryUnsafe(current) || !os.SameFile(opened, current) {
			_ = file.Close()
			return nil, blocked("PATH_UNSAFE", "Writer lock changed while opening", "project")
		}
		unlock, acquired, err := tryProcessFileLock(file)
		if err != nil {
			_ = file.Close()
			return nil, err
		}
		if acquired {
			if err := file.Truncate(0); err == nil {
				_, err = file.Seek(0, io.SeekStart)
			}
			if err == nil {
				_, err = fmt.Fprintf(file, "%d\n%d\n", os.Getpid(), time.Now().UnixNano())
			}
			if err == nil {
				err = file.Sync()
			}
			if err != nil {
				_ = unlock()
				_ = file.Close()
				return nil, err
			}
			return func() {
				_ = unlock()
				_ = file.Close()
			}, nil
		}
		_ = file.Close()
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

func resultBlockedFor(plan storedPlan, err error) EditCommitResult {
	result := resultBlocked(err)
	if plan.Public.APIVersion == EditPlanAPIVersionV2 {
		result.APIVersion = EditResultAPIVersionV2
	}
	return result
}

func (b *Backend) CommitEditPlan(ctx context.Context, planID string) EditCommitResult {
	return b.commitEditPlan(ctx, planID, EditResultAPIVersion)
}

// CommitEditPlanV2 preserves the UI-01D result contract even when the plan
// has already expired and its stored version can no longer be inspected.
func (b *Backend) CommitEditPlanV2(ctx context.Context, planID string) EditCommitResult {
	return b.commitEditPlan(ctx, planID, EditResultAPIVersionV2)
}

func (b *Backend) commitEditPlan(ctx context.Context, planID, missingPlanVersion string) EditCommitResult {
	plan, found := b.plans.Get(planID)
	if !found {
		result := resultBlocked(blocked("PLAN_EXPIRED", "Edit plan is absent or expired", "planId"))
		result.APIVersion = missingPlanVersion
		return result
	}
	resultVersion := EditResultAPIVersion
	if plan.Public.APIVersion == EditPlanAPIVersionV2 {
		resultVersion = EditResultAPIVersionV2
	}
	release, err := acquireWriterLock(ctx, plan.ProjectRoot, b.lockWait)
	if err != nil {
		return resultBlockedFor(plan, err)
	}
	defer release()
	if err := assertSafeExistingAncestors(plan.ProjectRoot); err != nil {
		return resultBlockedFor(plan, err)
	}
	if err := recoverTransactions(plan.ProjectRoot); err != nil {
		return resultBlockedFor(plan, err)
	}
	documents, revision, err := collectProjectDocuments(plan.ProjectRoot)
	if err != nil {
		return resultBlockedFor(plan, err)
	}
	digests := make(map[string]string, len(documents))
	for _, document := range documents {
		digests[document.LogicalPath] = document.Digest
	}
	for _, expected := range plan.Public.AffectedDocuments {
		if absentDocument(expected) {
			if _, present := digests[expected.LogicalPath]; present {
				return resultBlockedFor(plan, blocked("DOCUMENT_CHANGED", "A planned new document appeared after review", "document"))
			}
		} else if digests[expected.LogicalPath] != presentBeforeDigest(expected) {
			return resultBlockedFor(plan, blocked("DOCUMENT_CHANGED", "An affected document changed after planning", "document"))
		}
	}
	if revision != plan.Public.BaseProjectRevision {
		return resultBlockedFor(plan, blocked("PROJECT_CHANGED", "Project changed after planning", "project"))
	}
	transactionStarted := b.now()
	if err := b.commitDocuments(plan.ProjectRoot, planID, plan.Documents); err != nil {
		return resultBlockedFor(plan, err)
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
		return EditCommitResult{APIVersion: resultVersion, Kind: "EditCommitResult",
			Status: "COMMITTED_REFRESH_FAILED", Changed: true,
			OldProjectRevision: plan.Public.BaseProjectRevision, NewProjectRevision: newRevision,
			AffectedDocuments: plan.Public.AffectedDocuments, ApplyRequired: true,
			Timing: CommitTiming{Transaction: transactionDuration, Snapshot: snapshotDuration}}
	}
	return EditCommitResult{APIVersion: resultVersion, Kind: "EditCommitResult",
		Status: "COMMITTED", Changed: true, OldProjectRevision: plan.Public.BaseProjectRevision,
		NewProjectRevision: snapshot.ProjectRevision, AffectedDocuments: plan.Public.AffectedDocuments,
		Snapshot: snapshot, ApplyRequired: true,
		Timing: CommitTiming{Transaction: transactionDuration, Snapshot: snapshotDuration}}
}

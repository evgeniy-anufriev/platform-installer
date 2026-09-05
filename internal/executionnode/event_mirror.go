package executionnode

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"sync"
)

const (
	maxMirroredEventBytes  = 64 * 1024
	maxMirrorBytes         = 128 * 1024 * 1024
	maxMirrorMetadataBytes = 4096
	maxMirroredEvents      = maxObservedExecutionEvents
)

type EventMirror struct {
	mu     sync.Mutex
	runID  string
	path   string
	file   *os.File
	lock   *os.File
	root   *os.Root
	unlock func() error
	last   int
	first  int
	events map[int][]byte
	bytes  int64
	closed bool
}

func OpenEventMirror(runtimeRoot, runID, nodeFingerprint string) (*EventMirror, error) {
	destination, err := EventMirrorPath(runtimeRoot, runID)
	if err != nil {
		return nil, err
	}
	if !validSHA256Fingerprint(nodeFingerprint) {
		return nil, errors.New("EXECUTION_MIRROR_INPUT_INVALID")
	}
	root, _ := filepath.Abs(runtimeRoot)
	if err := ensureMirrorRoot(root); err != nil {
		return nil, err
	}
	if err := rejectSymlinkComponents(root); err != nil {
		return nil, err
	}
	linkedRoot, linkRootErr := os.Lstat(root)
	if linkRootErr != nil || isUnsafeFilesystemLink(linkedRoot) || !linkedRoot.IsDir() {
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	rooted, err := os.OpenRoot(root)
	if err != nil {
		return nil, errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	openedRoot, openRootErr := rooted.Stat(".")
	if openRootErr != nil || !os.SameFile(linkedRoot, openedRoot) {
		_ = rooted.Close()
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	for _, directory := range []string{"executions", filepath.Join("executions", runID)} {
		if err := ensureRootedPrivateDirectory(rooted, directory); err != nil {
			_ = rooted.Close()
			return nil, err
		}
	}
	runDirectory := filepath.Join("executions", runID)
	linkedRun, linkRunErr := rooted.Lstat(runDirectory)
	runRoot, runRootErr := rooted.OpenRoot(runDirectory)
	if linkRunErr != nil || runRootErr != nil || isUnsafeFilesystemLink(linkedRun) || !linkedRun.IsDir() {
		if runRoot != nil {
			_ = runRoot.Close()
		}
		_ = rooted.Close()
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	openedRun, openRunErr := runRoot.Stat(".")
	if openRunErr != nil || !os.SameFile(linkedRun, openedRun) {
		_ = runRoot.Close()
		_ = rooted.Close()
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	_ = rooted.Close()
	lockFile, err := runRoot.OpenFile(".mirror.lock", os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	linkedLock, linkLockErr := runRoot.Lstat(".mirror.lock")
	openedLock, openLockErr := lockFile.Stat()
	if linkLockErr != nil || openLockErr != nil || isUnsafeFilesystemLink(linkedLock) || !openedLock.Mode().IsRegular() || !os.SameFile(linkedLock, openedLock) || hardenMirrorHandle(lockFile) != nil {
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	unlock, lockErr := lockEventMirror(lockFile)
	if lockErr != nil {
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_IN_USE")
	}
	if err := bindEventMirror(runRoot, runID, nodeFingerprint); err != nil {
		_ = unlock()
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, err
	}
	file, err := runRoot.OpenFile("events.jsonl", os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		_ = unlock()
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	linkedInfo, linkErr := runRoot.Lstat("events.jsonl")
	openedInfo, openErr := file.Stat()
	if linkErr != nil || openErr != nil || isUnsafeFilesystemLink(linkedInfo) || !openedInfo.Mode().IsRegular() || !os.SameFile(linkedInfo, openedInfo) {
		_ = file.Close()
		_ = unlock()
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	if err := hardenMirrorHandle(file); err != nil {
		_ = file.Close()
		_ = unlock()
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, errors.New("EXECUTION_MIRROR_PERMISSIONS_FAILED")
	}
	mirror := &EventMirror{runID: runID, path: destination, file: file, lock: lockFile, root: runRoot, unlock: unlock, events: map[int][]byte{}}
	if err := mirror.recover(); err != nil {
		_ = unlock()
		_ = file.Close()
		_ = lockFile.Close()
		_ = runRoot.Close()
		return nil, err
	}
	return mirror, nil
}

type eventMirrorIdentity struct {
	APIVersion      string `json:"apiVersion"`
	RunID           string `json:"runId"`
	NodeFingerprint string `json:"nodeFingerprint"`
}

func bindEventMirror(root *os.Root, runID, nodeFingerprint string) error {
	expected := eventMirrorIdentity{APIVersion: "platform.installer/execution-mirror/v1alpha1", RunID: runID, NodeFingerprint: nodeFingerprint}
	encoded, _ := json.Marshal(expected)
	file, err := root.OpenFile("mirror.json", os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err == nil {
		defer file.Close()
		if hardenMirrorHandle(file) != nil {
			return errors.New("EXECUTION_MIRROR_PERMISSIONS_FAILED")
		}
		if written, writeErr := file.Write(append(encoded, '\n')); writeErr != nil || written != len(encoded)+1 || file.Sync() != nil {
			return errors.New("EXECUTION_MIRROR_WRITE_FAILED")
		}
		return nil
	}
	if !os.IsExist(err) {
		return errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	file, err = root.Open("mirror.json")
	if err != nil {
		return errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	defer file.Close()
	linked, linkErr := root.Lstat("mirror.json")
	opened, openErr := file.Stat()
	if linkErr != nil || openErr != nil || isUnsafeFilesystemLink(linked) || !opened.Mode().IsRegular() || !os.SameFile(linked, opened) || hardenMirrorHandle(file) != nil {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	data, readErr := io.ReadAll(io.LimitReader(file, maxMirrorMetadataBytes+1))
	if readErr != nil || len(data) > maxMirrorMetadataBytes {
		return errors.New("EXECUTION_MIRROR_IDENTITY_INVALID")
	}
	actual := eventMirrorIdentity{}
	if json.Unmarshal(data, &actual) != nil || actual != expected || !bytes.Equal(bytes.TrimSpace(data), encoded) {
		return errors.New("EXECUTION_MIRROR_NODE_CONFLICT")
	}
	return nil
}

func ensureMirrorRoot(root string) error {
	if _, err := os.Lstat(root); err == nil {
		return nil
	} else if !os.IsNotExist(err) {
		return errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	parent := filepath.Dir(root)
	if parent == root || filepath.Base(root) == "." || filepath.Base(root) == string(filepath.Separator) {
		return errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	if err := rejectSymlinkComponents(parent); err != nil {
		return err
	}
	linkedParent, err := os.Lstat(parent)
	if err != nil || isUnsafeFilesystemLink(linkedParent) || !linkedParent.IsDir() {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	parentRoot, err := os.OpenRoot(parent)
	if err != nil {
		return errors.New("EXECUTION_MIRROR_OPEN_FAILED")
	}
	defer parentRoot.Close()
	openedParent, err := parentRoot.Stat(".")
	if err != nil || !os.SameFile(linkedParent, openedParent) {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	name := filepath.Base(root)
	if err := parentRoot.Mkdir(name, 0o700); err != nil && !os.IsExist(err) {
		return errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	linkedRoot, linkErr := parentRoot.Lstat(name)
	openedRoot, openErr := parentRoot.OpenRoot(name)
	if linkErr != nil || openErr != nil || isUnsafeFilesystemLink(linkedRoot) || !linkedRoot.IsDir() {
		if openedRoot != nil {
			_ = openedRoot.Close()
		}
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	openedInfo, statErr := openedRoot.Stat(".")
	_ = openedRoot.Close()
	if statErr != nil || !os.SameFile(linkedRoot, openedInfo) {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	return nil
}

func EventMirrorPath(runtimeRoot, runID string) (string, error) {
	if runtimeRoot == "" || !validRuntimeToken(runID) {
		return "", errors.New("EXECUTION_MIRROR_INPUT_INVALID")
	}
	root, err := filepath.Abs(runtimeRoot)
	if err != nil {
		return "", errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	destination := filepath.Join(root, "executions", runID, "events.jsonl")
	if !containedPath(root, destination) {
		return "", errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	return destination, nil
}

func (m *EventMirror) Path() string { return m.path }

func (m *EventMirror) LastSequence() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.last
}

func (m *EventMirror) knownEvents() map[int][]byte {
	m.mu.Lock()
	defer m.mu.Unlock()
	result := make(map[int][]byte, len(m.events))
	for sequence, encoded := range m.events {
		result[sequence] = append([]byte(nil), encoded...)
	}
	return result
}

func (m *EventMirror) Append(event ExecutionEvent) (bool, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.closed {
		return false, errors.New("EXECUTION_MIRROR_CLOSED")
	}
	if validateExecutionEvent(event, m.runID) != nil {
		return false, errors.New("EXECUTION_MIRROR_EVENT_INVALID")
	}
	encoded, err := canonicalEvent(event)
	if err != nil || len(encoded)+1 > maxMirroredEventBytes {
		return false, errors.New("EXECUTION_MIRROR_EVENT_INVALID")
	}
	if prior, ok := m.events[event.Sequence]; ok {
		if bytes.Equal(prior, encoded) {
			return false, nil
		}
		return false, errors.New("EXECUTION_MIRROR_DUPLICATE_CONFLICT")
	}
	if m.last != 0 && event.Sequence != m.last+1 {
		return false, errors.New("EXECUTION_MIRROR_SEQUENCE_GAP")
	}
	if m.bytes+int64(len(encoded)+1) > maxMirrorBytes {
		return false, errors.New("EXECUTION_MIRROR_LIMIT")
	}
	if len(m.events) >= maxMirroredEvents {
		return false, errors.New("EXECUTION_MIRROR_LIMIT")
	}
	line := append(encoded, '\n')
	if _, err := m.file.Seek(0, io.SeekEnd); err != nil {
		return false, errors.New("EXECUTION_MIRROR_WRITE_FAILED")
	}
	written, err := m.file.Write(line)
	if err != nil || written != len(line) {
		return false, errors.New("EXECUTION_MIRROR_WRITE_FAILED")
	}
	if err := m.file.Sync(); err != nil {
		return false, errors.New("EXECUTION_MIRROR_SYNC_FAILED")
	}
	m.events[event.Sequence] = append([]byte(nil), encoded...)
	if m.first == 0 {
		m.first = event.Sequence
	}
	m.last = event.Sequence
	m.bytes += int64(len(line))
	return true, nil
}

func (m *EventMirror) Events(after int) []ExecutionEvent {
	m.mu.Lock()
	defer m.mu.Unlock()
	result := make([]ExecutionEvent, 0)
	start := after + 1
	if start < m.first {
		start = m.first
	}
	for sequence := start; sequence <= m.last; sequence++ {
		var event ExecutionEvent
		if err := json.Unmarshal(m.events[sequence], &event); err == nil {
			result = append(result, event)
		}
	}
	return result
}

func (m *EventMirror) Reset() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.closed {
		return errors.New("EXECUTION_MIRROR_CLOSED")
	}
	if err := m.file.Truncate(0); err != nil {
		return errors.New("EXECUTION_MIRROR_WRITE_FAILED")
	}
	if _, err := m.file.Seek(0, io.SeekStart); err != nil || m.file.Sync() != nil {
		return errors.New("EXECUTION_MIRROR_SYNC_FAILED")
	}
	m.last = 0
	m.first = 0
	m.bytes = 0
	m.events = map[int][]byte{}
	return nil
}

func (m *EventMirror) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.closed {
		return nil
	}
	m.closed = true
	unlockErr := m.unlock()
	lockErr := m.lock.Close()
	fileErr := m.file.Close()
	rootErr := m.root.Close()
	if unlockErr != nil {
		return unlockErr
	}
	if lockErr != nil {
		return lockErr
	}
	if fileErr != nil {
		return fileErr
	}
	return rootErr
}

func (m *EventMirror) recover() error {
	info, err := m.file.Stat()
	if err != nil || info.Size() > maxMirrorBytes {
		return errors.New("EXECUTION_MIRROR_LIMIT")
	}
	data, err := io.ReadAll(io.LimitReader(m.file, maxMirrorBytes+1))
	if err != nil || int64(len(data)) > maxMirrorBytes {
		return errors.New("EXECUTION_MIRROR_READ_FAILED")
	}
	if len(data) > 0 && data[len(data)-1] != '\n' {
		complete := bytes.LastIndexByte(data, '\n')
		truncateAt := int64(0)
		if complete >= 0 {
			truncateAt = int64(complete + 1)
		}
		if err := m.file.Truncate(truncateAt); err != nil || m.file.Sync() != nil {
			return errors.New("EXECUTION_MIRROR_RECOVERY_FAILED")
		}
		data = data[:truncateAt]
	}
	scanner := bufio.NewScanner(bytes.NewReader(data))
	scanner.Buffer(make([]byte, 4096), maxMirroredEventBytes)
	for scanner.Scan() {
		encoded := append([]byte(nil), scanner.Bytes()...)
		var event ExecutionEvent
		if json.Unmarshal(encoded, &event) != nil || validateExecutionEvent(event, m.runID) != nil {
			return errors.New("EXECUTION_MIRROR_CORRUPT")
		}
		canonical, err := canonicalEvent(event)
		if err != nil || !bytes.Equal(canonical, encoded) || m.last != 0 && event.Sequence != m.last+1 {
			return errors.New("EXECUTION_MIRROR_CORRUPT")
		}
		m.events[event.Sequence] = canonical
		if len(m.events) > maxMirroredEvents {
			return errors.New("EXECUTION_MIRROR_LIMIT")
		}
		if m.first == 0 {
			m.first = event.Sequence
		}
		m.last = event.Sequence
	}
	if err := scanner.Err(); err != nil {
		return errors.New("EXECUTION_MIRROR_CORRUPT")
	}
	m.bytes = int64(len(data))
	_, err = m.file.Seek(0, io.SeekEnd)
	return err
}

func canonicalEvent(event ExecutionEvent) ([]byte, error) {
	if err := validateExecutionEvent(event, event.RunID); err != nil {
		return nil, err
	}
	return json.Marshal(event)
}

func ensureRootedPrivateDirectory(root *os.Root, relative string) error {
	if err := root.Mkdir(relative, 0o700); err != nil && !os.IsExist(err) {
		return errors.New("EXECUTION_MIRROR_PATH_INVALID")
	}
	info, err := root.Lstat(relative)
	if err != nil || isUnsafeFilesystemLink(info) || !info.IsDir() || !mirrorDirectoryPrivate(info) {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	directory, err := root.Open(relative)
	if err != nil {
		return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
	}
	defer directory.Close()
	opened, err := directory.Stat()
	if err != nil || !os.SameFile(info, opened) || hardenMirrorHandle(directory) != nil {
		return errors.New("EXECUTION_MIRROR_PERMISSIONS_FAILED")
	}
	return nil
}

func rejectSymlinkComponents(candidate string) error {
	clean := filepath.Clean(candidate)
	volume := filepath.VolumeName(clean)
	remainder := clean[len(volume):]
	current := volume + string(filepath.Separator)
	for _, part := range splitPath(remainder) {
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if os.IsNotExist(err) {
			return nil
		}
		if err != nil {
			return errors.New("EXECUTION_MIRROR_PATH_INVALID")
		}
		if isUnsafeFilesystemLink(info) {
			return errors.New("EXECUTION_MIRROR_PATH_UNSAFE")
		}
	}
	return nil
}

func splitPath(value string) []string {
	result := []string{}
	for _, part := range bytes.FieldsFunc([]byte(value), func(r rune) bool { return r == '/' || r == '\\' }) {
		result = append(result, string(part))
	}
	return result
}

func containedPath(root, candidate string) bool {
	relative, err := filepath.Rel(filepath.Clean(root), filepath.Clean(candidate))
	return err == nil && relative != ".." && !filepath.IsAbs(relative) && relative != "" && !startsWithParent(relative)
}

func startsWithParent(relative string) bool {
	return len(relative) >= 3 && relative[:3] == ".."+string(filepath.Separator)
}

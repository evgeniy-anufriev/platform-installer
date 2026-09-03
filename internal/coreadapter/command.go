package coreadapter

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

type boundedBuffer struct {
	buffer    bytes.Buffer
	remaining int
}

func (b *boundedBuffer) Write(content []byte) (int, error) {
	written := len(content)
	if b.remaining > 0 {
		limit := len(content)
		if limit > b.remaining {
			limit = b.remaining
		}
		_, _ = b.buffer.Write(content[:limit])
		b.remaining -= limit
	}
	return written, nil
}

// CommandAdapter invokes the existing target-free UI-BE-02 Ansible entrypoint.
type CommandAdapter struct {
	Executable string
	WorkingDir string
	Playbook   string
	Catalog    string
	Env        []string
	Timeout    time.Duration
}

func (a *CommandAdapter) BuildSnapshot(ctx context.Context, projectRoot string, owned []string) (*Snapshot, error) {
	if a.Executable == "" || a.Playbook == "" || a.Catalog == "" {
		return nil, errors.New("core adapter is not configured")
	}
	timeout := a.Timeout
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	boundedContext, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	temporary, err := os.MkdirTemp("", "platform-installer-core-")
	if err != nil {
		return nil, err
	}
	defer os.RemoveAll(temporary)
	response := filepath.Join(temporary, "snapshot.json")
	variables := filepath.Join(temporary, "request.json")
	request := map[string]any{
		"platform_project_root":          projectRoot,
		"platform_service_catalog_path":  a.Catalog,
		"platform_installer_owned_paths": owned,
	}
	encoded, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(variables, encoded, 0o600); err != nil {
		return nil, err
	}
	inventory := filepath.Join(projectRoot, "inventory", "hosts.yml")
	command := exec.CommandContext(boundedContext, a.Executable, "-i", inventory, a.Playbook, "-e", "@"+variables)
	command.Dir = a.WorkingDir
	command.Env = append(os.Environ(), a.Env...)
	command.Env = append(command.Env,
		"ANSIBLE_CALLBACKS_ENABLED=platform.core.project_snapshot_json",
		"PLATFORM_PROJECT_SNAPSHOT_OUTPUT="+response,
	)
	var diagnostics boundedBuffer
	diagnostics.remaining = 16384
	command.Stdout = io.Discard
	command.Stderr = &diagnostics
	err = command.Run()
	if err != nil {
		return nil, fmt.Errorf("core snapshot command failed: %w", err)
	}
	data, err := os.ReadFile(response)
	if err != nil {
		return nil, fmt.Errorf("core snapshot response missing: %w", err)
	}
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal(data, &envelope); err != nil {
		return nil, fmt.Errorf("core snapshot response invalid: %w", err)
	}
	if _, blocked := envelope["adapterError"]; blocked {
		return nil, errors.New("core snapshot was blocked")
	}
	snapshot, err := DecodeSnapshot(data)
	if err != nil {
		return nil, err
	}
	if snapshot.ProjectRevision == "" {
		return nil, errors.New("core snapshot response has no project revision")
	}
	return snapshot, nil
}

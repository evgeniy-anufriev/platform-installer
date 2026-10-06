//go:build dev

package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"unicode/utf8"
)

// Only replaces the OS picker result. The bound import method and all its
// descriptor, file-handle, decryption, session and post-read guards still run.
func configureQASecretFileSelection(app *App) error {
	encoded := os.Getenv("PLATFORM_QA_SECRET_FILE_SELECTIONS")
	if encoded == "" {
		return nil
	}
	if len(encoded) > 16*4096 || !utf8.ValidString(encoded) {
		return errors.New("QA_SECRET_FILE_SELECTION_INVALID")
	}
	var paths []string
	if json.Unmarshal([]byte(encoded), &paths) != nil || len(paths) == 0 || len(paths) > 16 {
		return errors.New("QA_SECRET_FILE_SELECTION_INVALID")
	}
	for _, path := range paths {
		if !utf8.ValidString(path) || len(path) == 0 || len(path) > 4096 || !filepath.IsAbs(path) {
			return errors.New("QA_SECRET_FILE_SELECTION_INVALID")
		}
		for _, char := range path {
			if char == 0 || char < 32 {
				return errors.New("QA_SECRET_FILE_SELECTION_INVALID")
			}
		}
	}
	var mu sync.Mutex
	app.chooseSecretFile = func(ctx context.Context, _ DialogOptions) (string, error) {
		mu.Lock()
		defer mu.Unlock()
		if ctx.Err() != nil {
			return "", ctx.Err()
		}
		if len(paths) == 0 {
			return "", errors.New("QA_SECRET_FILE_SELECTION_EXHAUSTED")
		}
		path := paths[0]
		paths[0] = ""
		paths = paths[1:]
		return path, nil
	}
	return nil
}

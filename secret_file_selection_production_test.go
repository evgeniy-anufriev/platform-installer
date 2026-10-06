//go:build !dev

package main

import (
	"context"
	"encoding/json"
	"path/filepath"
	"testing"
)

func TestProductionIgnoresQASecretFileSelections(t *testing.T) {
	valid, _ := json.Marshal([]string{filepath.Join(t.TempDir(), "selected.age")})
	for _, encoded := range []string{"malformed", string(valid)} {
		t.Setenv("PLATFORM_QA_SECRET_FILE_SELECTIONS", encoded)
		a := NewApp(unavailableProjectReader{}, lifecycleStub{})
		called := false
		a.chooseSecretFile = func(context.Context, DialogOptions) (string, error) {
			called = true
			return "sentinel", nil
		}
		if configureQASecretFileSelection(a) != nil {
			t.Fatal("production consumed QA configuration")
		}
		got, err := a.chooseSecretFile(context.Background(), DialogOptions{})
		if !called || err != nil || got != "sentinel" {
			t.Fatal("production picker replaced")
		}
	}
}

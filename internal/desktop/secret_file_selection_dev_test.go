//go:build dev

package desktop

import (
	"context"
	"encoding/json"
	"path/filepath"
	"testing"
)

func TestQASecretFileSelectionsFiniteOrderedAndCancellation(t *testing.T) {
	paths := []string{filepath.Join(t.TempDir(), "one.age"), filepath.Join(t.TempDir(), "two.age")}
	encoded, _ := json.Marshal(paths)
	t.Setenv("PLATFORM_QA_SECRET_FILE_SELECTIONS", string(encoded))
	a := NewApp(unavailableProjectReader{}, lifecycleStub{})
	if err := configureQASecretFileSelection(a); err != nil {
		t.Fatal("configuration failed")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := a.chooseSecretFile(ctx, DialogOptions{}); err == nil {
		t.Fatal("cancelled selection accepted")
	}
	for _, expected := range paths {
		got, err := a.chooseSecretFile(context.Background(), DialogOptions{})
		if err != nil || got != expected {
			t.Fatal("selection order changed")
		}
	}
	if _, err := a.chooseSecretFile(context.Background(), DialogOptions{}); err == nil {
		t.Fatal("exhausted queue must not reopen native dialog")
	}
}

func TestQASecretFileSelectionsRejectMalformedInput(t *testing.T) {
	for _, encoded := range []string{"null", "[]", "{}", "[1]", `["relative.age"]`, `["\u0000"]`, string([]byte{0xff})} {
		t.Run("invalid", func(t *testing.T) {
			t.Setenv("PLATFORM_QA_SECRET_FILE_SELECTIONS", encoded)
			a := NewApp(unavailableProjectReader{}, lifecycleStub{})
			if configureQASecretFileSelection(a) == nil {
				t.Fatal("invalid selection admitted")
			}
		})
	}
}

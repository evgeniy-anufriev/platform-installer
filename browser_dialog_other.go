//go:build browser && !windows

package main

import (
	"context"
	"errors"
)

type unavailableBrowserDialogProvider struct{}

func newBrowserDialogProvider() DialogProvider { return unavailableBrowserDialogProvider{} }

func (unavailableBrowserDialogProvider) OpenDirectory(context.Context, DialogOptions) (string, error) {
	return "", errors.New("NATIVE_DIALOG_UNAVAILABLE")
}

func (unavailableBrowserDialogProvider) OpenFile(context.Context, DialogOptions) (string, error) {
	return "", errors.New("NATIVE_DIALOG_UNAVAILABLE")
}

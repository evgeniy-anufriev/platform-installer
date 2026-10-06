package main

import (
	"context"
	"errors"
)

type DialogOptions struct {
	Title   string
	Filters []DialogFilter
}

type DialogFilter struct {
	DisplayName string
	Pattern     string
}

type DialogProvider interface {
	OpenDirectory(context.Context, DialogOptions) (string, error)
	OpenFile(context.Context, DialogOptions) (string, error)
}

type secretFileChooser func(context.Context, DialogOptions) (string, error)

type ApplicationEventPublisher interface {
	Publish(context.Context, string, any)
}

func WithDialogProvider(provider DialogProvider) AppOption {
	return func(app *App) { app.dialogs = provider }
}

func WithApplicationEventPublisher(publisher ApplicationEventPublisher) AppOption {
	return func(app *App) {
		if publisher != nil {
			app.events = publisher
		}
	}
}

func (a *App) openDirectory(ctx context.Context, options DialogOptions) (string, error) {
	if a.dialogs == nil {
		return "", errors.New("NATIVE_DIALOG_UNAVAILABLE")
	}
	return a.dialogs.OpenDirectory(ctx, options)
}

func (a *App) openFile(ctx context.Context, options DialogOptions) (string, error) {
	if a.chooseSecretFile != nil {
		return a.chooseSecretFile(ctx, options)
	}
	if a.dialogs == nil {
		return "", errors.New("NATIVE_DIALOG_UNAVAILABLE")
	}
	return a.dialogs.OpenFile(ctx, options)
}

type noopEventPublisher struct{}

func (noopEventPublisher) Publish(context.Context, string, any) {}

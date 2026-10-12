//go:build !browser

package desktop

import (
	"context"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type wailsDialogProvider struct{}

func (wailsDialogProvider) OpenDirectory(ctx context.Context, options DialogOptions) (string, error) {
	return runtime.OpenDirectoryDialog(ctx, runtime.OpenDialogOptions{Title: options.Title})
}

func (wailsDialogProvider) OpenFile(ctx context.Context, options DialogOptions) (string, error) {
	filters := make([]runtime.FileFilter, 0, len(options.Filters))
	for _, filter := range options.Filters {
		filters = append(filters, runtime.FileFilter{DisplayName: filter.DisplayName, Pattern: filter.Pattern})
	}
	return runtime.OpenFileDialog(ctx, runtime.OpenDialogOptions{Title: options.Title, Filters: filters})
}

type wailsEventPublisher struct{}

func (wailsEventPublisher) Publish(ctx context.Context, name string, payload any) {
	if ctx == nil {
		return
	}
	runtime.EventsEmit(ctx, name, payload)
}

func NewWailsApp(settings LaunchSettings) (*App, error) {
	return newConfiguredApp(settings, wailsDialogProvider{}, wailsEventPublisher{})
}

func WailsLifecycle(app *App) (func(context.Context), func(context.Context)) {
	if app == nil {
		return nil, nil
	}
	return app.startup, app.shutdown
}

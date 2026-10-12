//go:build browser && !windows

package desktop

import "errors"

func openBrowser(string) error { return errors.New("BROWSER_LAUNCH_UNAVAILABLE") }

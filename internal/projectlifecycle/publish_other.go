//go:build !windows && !linux

package projectlifecycle

import "errors"

func atomicPublish(string, string) error { return errors.New("PROJECT_PUBLISH_UNSUPPORTED") }

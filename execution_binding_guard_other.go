//go:build !windows

package main

import (
	"crypto/sha256"
	"errors"
	"os"
)

func holdVerifiedBindingFile(string, os.FileInfo, [sha256.Size]byte, int64) (func(), error) {
	return nil, errors.New("EXECUTION_NODE_UI_WINDOWS_REQUIRED")
}

func hardenBindingPath(*os.File) error { return errors.New("EXECUTION_NODE_UI_WINDOWS_REQUIRED") }

func removeSessionKnownHosts(string, os.FileInfo, string, os.FileInfo) {}
func removeSessionDirectory(string, os.FileInfo)                       {}

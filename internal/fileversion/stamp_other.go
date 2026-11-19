//go:build !linux && !windows

package fileversion

import "os"

func Read(*os.File) (Stamp, bool) { return Stamp{}, false }

//go:build !windows

package installer

import "os"

func pathEntryUnsafe(info os.FileInfo) bool { return info.Mode()&os.ModeSymlink != 0 }

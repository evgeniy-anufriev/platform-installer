package fileversion

import (
	"os"

	"golang.org/x/sys/unix"
)

func Read(file *os.File) (Stamp, bool) {
	var info unix.Stat_t
	if unix.Fstat(int(file.Fd()), &info) != nil ||
		info.Mode&unix.S_IFMT != unix.S_IFREG || info.Ino == 0 || info.Nlink != 1 {
		return Stamp{}, false
	}
	return Stamp{Device: uint64(info.Dev), Inode: info.Ino,
		Changed: int64(info.Ctim.Sec), ChangedExtra: int64(info.Ctim.Nsec),
		Modified: info.Mtim.Nano(), Size: info.Size}, true
}

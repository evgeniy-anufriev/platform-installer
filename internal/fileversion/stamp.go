// Package fileversion observes the filesystem change indicator for read-only
// preview caches. Execution must continue to verify the actual contents.
package fileversion

type Stamp struct {
	Device, Inode           uint64
	Changed, ChangedExtra   int64
	Created, Modified, Size int64
}

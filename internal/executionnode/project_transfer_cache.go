package executionnode

import (
	"archive/tar"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// Hash precisely the service archive inputs, including unowned inventory and
// package assets. ProjectRevision alone deliberately excludes generated state.
// A cache hit needs no temporary archive and sends no project bytes over SSH.
func projectTransferIdentity(root string) (string, string, error) {
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", "", err
	}
	hash := sha256.New()
	writer := tar.NewWriter(hash)
	if err := writeProjectArchive(writer, absolute); err != nil {
		return "", "", err
	}
	if err := writer.Close(); err != nil {
		return "", "", err
	}
	slot := sha256.Sum256([]byte(absolute))
	return hex.EncodeToString(slot[:]), "sha256:" + hex.EncodeToString(hash.Sum(nil)), nil
}

// One replaceable archive per local project on this node, root-private. The
// lock protects lookup/extraction and publication; Core's request directories
// remain independent and retain their existing ownership/cleanup protocol.
const projectArchiveCacheScript = `set -eu
command -v flock >/dev/null || { printf 'MISS'; exit 0; }
slot=$1; expected=$2; action=$3; run_id=$4; purpose=$5; source=${6-}
base=/var/lib/platform-installer/execution/project-archives
install -d -m 0700 "$base" "$base/$slot"
exec 9>"$base/$slot/lock"
flock -x 9
archive=$base/$slot/project.tar
if [ "$action" = publish ]; then
  [ "sha256:$(sha256sum "$source" | awk '{print $1}')" = "$expected" ]
  install -m 0600 "$source" "$base/$slot/pending.tar"
  mv -f "$base/$slot/pending.tar" "$archive"
  exit 0
fi
[ -f "$archive" ] || { printf 'MISS'; exit 0; }
[ "sha256:$(sha256sum "$archive" | awk '{print $1}')" = "$expected" ] || { printf 'MISS'; exit 0; }
install -d -m 0700 /var/lib/platform-installer/execution/runs
run=/var/lib/platform-installer/execution/runs/$run_id
mkdir -m 0700 "$run"
mkdir -m 0700 "$run/project"
printf '%s\n' "$expected" > "$run/project-archive.digest"
tar -xf "$archive" -C "$run/project"
if [ "$purpose" = snapshot ]; then
  printf '{"kind":"readonly","runId":"%s"}\n' "$run_id" > "$run/.snapshot-owner.json"
fi
printf 'HIT'
`

func (t OpenSSHTransport) projectArchiveCache(ctx context.Context, node Node, slot, digest, action, runID, purpose, source string) (bool, error) {
	if len(slot) != 64 || !validSHA256(digest) || !validRuntimeToken(runID) || (purpose != "plan" && purpose != "snapshot") {
		return false, errors.New("PROJECT_TRANSFER_FAILED")
	}
	if _, err := hex.DecodeString(slot); err != nil {
		return false, errors.New("PROJECT_TRANSFER_FAILED")
	}
	output, err := t.ssh(ctx, node, "sudo", []string{"-n", "sh", "-s", "--", slot, digest, action, runID, purpose, source}, []byte(projectArchiveCacheScript))
	return strings.TrimSpace(string(output)) == "HIT", err
}

func writeProjectArchive(writer *tar.Writer, absolute string) error {
	info, err := os.Lstat(absolute)
	if err != nil || !info.IsDir() || isUnsafeFilesystemLink(info) {
		return errors.New("SERVICE_PROJECT_INVALID")
	}
	for _, entry := range []string{"inventory", "project.yml", "ansible.cfg", "application-packages", "library-packages"} {
		candidate := filepath.Join(absolute, entry)
		if _, err := os.Lstat(candidate); err != nil {
			if errors.Is(err, os.ErrNotExist) && entry != "inventory" {
				continue
			}
			return errors.New("SERVICE_PROJECT_INVALID")
		}
		if err := appendTarPath(writer, absolute, candidate); err != nil {
			return err
		}
	}
	return nil
}

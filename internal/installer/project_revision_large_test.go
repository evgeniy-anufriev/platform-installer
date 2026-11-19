package installer

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRevisionStreamsPackageAndDetectsSameSizeSameTimeChange(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "library-packages", "demo", "1.0.0", "assets")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "database.dump")
	data := bytes.Repeat([]byte("original"), 1<<17)
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	before, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	rows, err := observeApplicationPackageDocuments(root, true)
	if err != nil || len(rows) != 1 {
		t.Fatalf("rows=%d err=%v", len(rows), err)
	}
	if rows[0].content != nil || rows[0].Digest != digestBytes(data) {
		t.Fatal("revision must retain only the streamed digest")
	}
	// Verify canonical revision bytes stay compatible with the old algorithm.
	expected := digestBytes([]byte(rows[0].LogicalPath + "\x00" + digestBytes(data) + "\x00"))
	if before != expected {
		t.Fatal("canonical revision changed")
	}
	preview, err := PreviewProjectRevision(root)
	if err != nil || preview != before {
		t.Fatalf("initial preview: %q, %v", preview, err)
	}
	preview, err = PreviewProjectRevision(root)
	if err != nil || preview != before {
		t.Fatalf("cached preview: %q, %v", preview, err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	data[0] ^= 1
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(path, info.ModTime(), info.ModTime()); err != nil {
		t.Fatal(err)
	}
	after, err := ProjectRevision(root)
	if err != nil || after == before {
		t.Fatal("same-size, same-time byte change escaped fresh revision")
	}
	preview, err = PreviewProjectRevision(root)
	if err != nil || preview != after {
		t.Fatalf("changed preview: %q, %v", preview, err)
	}
}

type boundedRevisionSink struct {
	bytes   int64
	largest int
}

func (w *boundedRevisionSink) Write(p []byte) (int, error) {
	w.bytes += int64(len(p))
	if len(p) > w.largest {
		w.largest = len(p)
	}
	return len(p), nil
}

func TestStreamLargeRevisionAssetBoundedAndGuarded(t *testing.T) {
	root := t.TempDir()
	f, err := os.Create(filepath.Join(root, "large.dump"))
	if err != nil {
		t.Fatal(err)
	}
	const size = 700 << 20
	if err := f.Truncate(size); err != nil {
		t.Fatal(err)
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}
	dir, err := openExportSourceDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	defer dir.close()
	w := &boundedRevisionSink{}
	n, _, err := dir.streamFile([]string{"large.dump"}, size, w)
	if err != nil || n != size || w.bytes != size || w.largest > 64<<10 {
		t.Fatalf("n=%d sink=%+v err=%v", n, w, err)
	}
	if _, _, err := dir.streamFile([]string{"large.dump"}, size-1, io.Discard); err == nil || !strings.Contains(err.Error(), "EXPORT_LIMIT_EXCEEDED") {
		t.Fatal("size guard lost")
	}
}

func TestPreviewDigestHitReadsNoAssetBytes(t *testing.T) {
	root := t.TempDir()
	name := "arbitrary.bin"
	if err := os.WriteFile(filepath.Join(root, name), []byte("sample data"), 0600); err != nil {
		t.Fatal(err)
	}
	dir, err := openExportSourceDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	defer dir.close()
	first := &boundedRevisionSink{}
	read := &previewAssetRead{}
	size, _, err := dir.streamFile([]string{name}, 0, first, read)
	if err != nil || size != 11 || first.bytes != size || !read.cacheable {
		t.Fatalf("first observation: size=%d reads=%d stamp=%t err=%v", size, first.bytes, read.cacheable, err)
	}
	read.remember(digestBytes([]byte("sample data")))
	second := &boundedRevisionSink{}
	next := &previewAssetRead{}
	if _, _, err := dir.streamFile([]string{name}, 0, second, next); err != nil || second.bytes != 0 || next.digest == "" {
		t.Fatalf("cached observation read %d bytes: %v", second.bytes, err)
	}
	fresh := &boundedRevisionSink{}
	if _, _, err := dir.streamFile([]string{name}, 0, fresh); err != nil || fresh.bytes != size {
		t.Fatalf("fresh verification read %d bytes: %v", fresh.bytes, err)
	}
}

func BenchmarkPreviewProjectTwoAssets(b *testing.B) {
	root := b.TempDir()
	dir := filepath.Join(root, "library-packages", "demo", "1.0.0", "assets")
	if err := os.MkdirAll(dir, 0700); err != nil {
		b.Fatal(err)
	}
	for _, name := range []string{"database.dump", "arbitrary.bin"} {
		f, err := os.Create(filepath.Join(dir, name))
		if err != nil {
			b.Fatal(err)
		}
		if _, err := io.CopyN(f, zeroRevisionReader{}, 512<<20); err != nil {
			b.Fatal(err)
		}
		if err := f.Close(); err != nil {
			b.Fatal(err)
		}
	}
	if _, err := PreviewProjectRevision(root); err != nil {
		b.Fatal(err)
	}
	for _, item := range []struct {
		name string
		read func(string) (string, error)
	}{{"fresh", ProjectRevision}, {"cached", PreviewProjectRevision}} {
		b.Run(item.name, func(b *testing.B) {
			for i := 0; i < b.N; i++ {
				if _, err := item.read(root); err != nil {
					b.Fatal(err)
				}
			}
		})
	}
}

// Keep fixture creation outside the timer. Run the identical benchmark on both
// revisions with -benchtime=1x -count=3 to measure the affected local stage.
func BenchmarkProjectRevisionPackage(b *testing.B) {
	root := b.TempDir()
	dir := filepath.Join(root, "library-packages", "demo", "1.0.0", "assets")
	if err := os.MkdirAll(dir, 0700); err != nil {
		b.Fatal(err)
	}
	f, err := os.Create(filepath.Join(dir, "database.dump"))
	if err != nil {
		b.Fatal(err)
	}
	const size = 700 << 20
	if _, err := io.CopyN(f, zeroRevisionReader{}, size); err != nil {
		b.Fatal(err)
	}
	if err := f.Close(); err != nil {
		b.Fatal(err)
	}
	b.SetBytes(size)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := ProjectRevision(root); err != nil {
			b.Fatal(err)
		}
	}
}

type zeroRevisionReader struct{}

func (zeroRevisionReader) Read(p []byte) (int, error) { clear(p); return len(p), nil }

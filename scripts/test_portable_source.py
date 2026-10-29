"""Packaging regressions; no Core/Ansible execution required."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import subprocess
import sys

import portable_source


class VendorPackagingTests(unittest.TestCase):
    def test_dependency_cache_is_source_but_runtime_cache_is_not(self):
        for prefix in ("vendor/", "third_party/wails/vendor/"):
            self.assertTrue(portable_source.included(prefix + "example.org/lib/cache/cache.go"))
            self.assertFalse(portable_source.included(prefix + "example.org/lib/cache/cache_test.go"))
        self.assertFalse(portable_source.included("cache/runtime.go"))

    def test_missing_declared_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = []
            for vendor in ("vendor", "third_party/wails/vendor"):
                directory = root / vendor
                directory.mkdir(parents=True)
                (directory / "modules.txt").write_text(
                    "# example.org/lib v1.0.0\n## explicit\nexample.org/lib/cache\n",
                    encoding="utf-8",
                )
                names.append(vendor + "/example.org/lib/cache/cache.go")
            portable_source.validate_vendor_packages(root, names)
            with self.assertRaisesRegex(ValueError, "Missing vendored Go package"):
                portable_source.validate_vendor_packages(root, names[:1])


class NewlineFormatTests(unittest.TestCase):
    def test_verify_part_cli_without_other_parts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = b"hello\nworld\n"
            name = "source-0001.txt"
            part = root / name
            manifest = dict(format=portable_source.FORMAT, maxPartBytes=portable_source.LIMIT,
                            files=1, parts=[dict(name=name, bytes=len(original), sha256=portable_source.digest(original)),
                                            dict(name="source-0002.txt", bytes=0, sha256=portable_source.digest(b""))])
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            command = [sys.executable, portable_source.__file__, "verify-part", str(root), name]
            for data in (original, original.replace(b"\n", b"\r\n")):
                part.write_bytes(data)
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("PASS:", result.stdout)
            for data in (b"jello\nworld\n", original + b"\n", b"\xef\xbb\xbf" + original):
                part.write_bytes(data)
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("checksum/size mismatch", result.stderr)
            for invalid in ("source-9999.txt", "../source-0001.txt", "source-0002.txt"):
                result = subprocess.run(command[:-1] + [invalid], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
            manifest["format"] = portable_source.LEGACY_FORMAT
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            part.write_bytes(original.replace(b"\n", b"\r\n"))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            part.write_bytes(original)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_transport_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contents = [b"", b"hello\nworld\n", b"hello\r\nworld\r\n",
                        b"mixed\r\nline\n", b"bare\r", b"\x00\xff\r\n",
                        ("\ufeffПривет\r\n" * 9000).encode("utf-8")]
            files = []
            for index, content in enumerate(contents):
                path = root / (str(index) + ".txt")
                path.write_bytes(content)
                files.append((path.name, 0o644, path))
            package = root / "package"
            with patch.object(portable_source, "source_files", return_value=files), patch.object(portable_source, "git", return_value=b"fixture"):
                portable_source.pack(root, package)
            manifest, original = portable_source.read_package(package)
            self.assertEqual(manifest["format"], portable_source.FORMAT)
            self.assertEqual([data for _, data in original], contents)
            for part in manifest["parts"]:
                path = package / part["name"]
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
                self.assertLessEqual(path.stat().st_size, portable_source.LIMIT)
            portable_source.unpack(package, root / "restored")
            for name, _, path in files:
                self.assertEqual((root / "restored" / name).read_bytes(), path.read_bytes())
            part_path = package / manifest["parts"][0]["name"]
            valid = part_path.read_bytes()
            for damaged in (valid.replace(b"hello", b"jello", 1), valid + b"\r\n", b"\xef\xbb\xbf" + valid):
                part_path.write_bytes(damaged)
                with self.assertRaises(ValueError):
                    portable_source.read_package(package)
            part_path.write_bytes(valid.replace(b"\r\n", b"\n"))
            self.assertEqual(portable_source.read_package(package)[1], original)

    def test_legacy_remains_byte_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"legacy\r\n"
            record = dict(path="file.txt", mode=0o644, size=len(content), sha256=portable_source.digest(content), index=0, count=1, encoding="utf-8", payloadBytes=len(content))
            data = portable_source.HEADER + json.dumps(record).encode() + b"\n" + content + portable_source.FOOTER
            part = root / "source-0001.txt"
            part.write_bytes(data)
            (root / "manifest.json").write_text(json.dumps(dict(format=portable_source.LEGACY_FORMAT, maxPartBytes=portable_source.LIMIT, files=1, sourceBytes=len(content), textFiles=1, binaryFiles=0, parts=[dict(name=part.name, bytes=len(data), sha256=portable_source.digest(data))])), encoding="utf-8")
            self.assertEqual(portable_source.read_package(root)[1][0][1], content)
            part.write_bytes(data.replace(b"\r\n", b"\n"))
            with self.assertRaises(ValueError):
                portable_source.read_package(root)


if __name__ == "__main__":
    unittest.main()

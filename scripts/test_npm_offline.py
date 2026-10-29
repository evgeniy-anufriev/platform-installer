"""Offline npm payload integrity and CLI regression tests (no network)."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import npm_offline as npm
import portable_source as portable


class OfflinePayloadTests(unittest.TestCase):
    def test_complete_payload_crlf_corruption_and_stale_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontend").mkdir()
            package = {"packageManager": "npm@11.17.0"}
            content = b"\x1f\x8b\0fixture\r\n"
            integrity = "sha512-" + base64.b64encode(hashlib.sha512(content).digest()).decode()
            entry = {"resolved": "https://registry.npmjs.org/example/-/example-1.0.tgz", "integrity": integrity}
            lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/example": entry}}
            (root / "frontend/package.json").write_text(json.dumps(package), encoding="utf-8")
            lock_path = root / "frontend/package-lock.json"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            name = next(iter(npm.archives(lock)))
            archive = root / "archive.tgz"
            archive.write_bytes(content)
            output = root / "output"
            npm.pack_payload([(name, 0o644, archive)], output, package, lock, npm.LINUX_PROFILE)
            manifest, records = npm.verify_package(output, root)
            self.assertEqual(records[0][1], content)
            part = output / manifest["parts"][0]["name"]
            original = part.read_bytes()
            part.write_bytes(original.replace(b"\n", b"\r\n"))
            npm.verify_package(output, root)
            result = subprocess.run([sys.executable, npm.__file__, "verify-part", str(output), part.name], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            part.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "checksum/size"):
                npm.verify_package(output, root)
            part.write_bytes(original)
            lock["packages"]["node_modules/example"]["version"] = "changed"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                npm.verify_package(output, root)
            result = subprocess.run([sys.executable, npm.__file__, "ci", str(output), str(root)], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse((root / ".runtime").exists())
            lock["packages"]["node_modules/example"]["resolved"] = "http://registry.npmjs.org/example.tgz"
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                npm.archives(lock)

    def test_platform_filter_omits_only_incompatible_optional_packages(self):
        entry = {"resolved": "https://registry.npmjs.org/example.tgz",
                 "integrity": "sha512-" + base64.b64encode(bytes(64)).decode()}
        lock = {"packages": {"node_modules/common": dict(entry),
                             "node_modules/windows": dict(entry, optional=True, os=["win32"]),
                             "node_modules/linux": dict(entry, optional=True, os=["linux"], cpu=["x64"], libc=["glibc"])}}
        lock["packages"]["node_modules/windows"]["integrity"] = "sha512-" + base64.b64encode(bytes([1]) * 64).decode()
        lock["packages"]["node_modules/linux"]["integrity"] = "sha512-" + base64.b64encode(bytes([2]) * 64).decode()
        self.assertEqual(len(npm.archives(lock)), 2)
        self.assertEqual(len(npm.archives(lock, "all")), 3)
        lock["packages"]["node_modules/windows"]["optional"] = False
        with self.assertRaisesRegex(ValueError, "incompatible"):
            npm.archives(lock)


if __name__ == "__main__":
    unittest.main()

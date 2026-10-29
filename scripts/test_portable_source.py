"""Packaging regressions; no Core/Ansible execution required."""
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()

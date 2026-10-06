"""Negative fixture tests for the production shared-file write guard."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parent
MARKER = "# Platform Installer V2 managed test unit\n"


@unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("sudo"), "RED OS Ansible/sudo required")
class GuardRootDestinationTests(unittest.TestCase):
    def test_owned_file_foreign_file_symlink_and_directory(self):
        collections = os.pathsep.join(
            [str(ROOT / "services/docker/ansible_collections"), str(ROOT / "ansible-core/collections")]
        )
        with tempfile.TemporaryDirectory(prefix="docker-file-guard-qa-") as directory:
            root = Path(directory)
            target = root / "unit"
            foreign = root / "foreign"
            foreign.write_text("foreign configuration\n", encoding="utf-8")
            cases = (
                ("absent", True),
                ("owned", True),
                ("foreign-content", False),
                ("foreign-owner", False),
                ("symlink", False),
                ("directory", False),
            )
            for case, accepted in cases:
                with self.subTest(case=case):
                    if target.is_symlink() or target.is_file():
                        target.unlink()
                    elif target.is_dir():
                        target.rmdir()
                    if case in ("owned", "foreign-content", "foreign-owner"):
                        target.write_text(MARKER if case != "foreign-content" else "foreign\n", encoding="utf-8")
                        if case != "foreign-owner":
                            subprocess.run(["sudo", "-n", "chown", "root", str(target)], check=True)
                    elif case == "symlink":
                        target.symlink_to(foreign)
                    elif case == "directory":
                        target.mkdir()
                    result = subprocess.run(
                        [
                            "ansible-playbook", str(TESTS / "guard_root_destination.yml"),
                            "-e", f"docker_guard_qa_path={target}",
                        ],
                        cwd=ROOT,
                        env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": collections},
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                    self.assertEqual(result.returncode == 0, accepted, result.stdout[-1800:])
                    if not accepted:
                        self.assertIn("DOCKER_SHARED_DESTINATION_", result.stdout)


if __name__ == "__main__":
    unittest.main()

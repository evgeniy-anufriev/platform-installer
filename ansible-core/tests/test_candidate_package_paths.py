import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import execution_protocol


class CandidatePackagePathsTests(unittest.TestCase):
    def test_data_only_package_closure(self):
        for name in (
            "library-packages/demo/1.0.0/library.yml",
            "library-packages/demo/1.0.0/files/.env",
            "library-packages/demo/1.0.0/roles/library_demo/defaults/main.yml",
            "application-packages/gateway/1.0.0/application.yml",
            "application-packages/gateway/1.0.0/roles/application_gateway/templates/compose.yml.j2",
            "application-packages/gateway/1.0.0/configuration/settings.json",
        ):
            with self.subTest(name=name):
                self.assertTrue(execution_protocol._candidate_logical_path(name))

    def test_executable_runtime_and_escaping_inputs_rejected(self):
        for name in (
            "library-packages/demo/1.0.0/roles/library_demo/tasks/main.yml",
            "application-packages/gateway/1.0.0/plugins/action/test.py",
            "library-packages/demo/1.0.0/secrets/admin-token",
            "library-packages/demo/1.0.0/assets/../../secret.txt",
            "library-packages/demo/latest/library.yml",
            "library-packages/demo/1.0.0/assets/script.sh",
        ):
            with self.subTest(name=name):
                self.assertFalse(execution_protocol._candidate_logical_path(name))

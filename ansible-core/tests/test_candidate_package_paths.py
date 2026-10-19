import sys
from pathlib import Path
import unittest
import tarfile
from types import SimpleNamespace

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
            "application-packages/gateway/1.0.0/assets/mock.jar",
            "application-packages/gateway/1.0.0/assets/StartupMock.java",
            "application-packages/gateway/1.0.0/assets/pressures.csv",
            "application-packages/gateway/1.0.0/assets/script.sh",
            "application-packages/gateway/1.0.0/configuration/data.unknown",
            "application-packages/gateway/1.0.0/assets/noextension",
        ):
            with self.subTest(name=name):
                self.assertTrue(execution_protocol._candidate_logical_path(name))

    def test_package_only_eight_mib_limit_in_candidate_archive(self):
        required = [tarfile.TarInfo(name) for name in ('project.yml', 'ansible.cfg', 'inventory/hosts.yml')]
        source = tarfile.TarInfo('application-packages/gateway/1.0.0/assets/mock.jar')
        source.size = 8 * 1024 * 1024
        archive = SimpleNamespace(getmembers=lambda: required + [source])
        self.assertEqual(required + [source], execution_protocol._candidate_members(archive))
        source.size += 1
        with self.assertRaises(execution_protocol.LifecycleError):
            execution_protocol._candidate_members(archive)
        source.name = 'inventory/group_vars/all/large.yml'
        source.size = 4 * 1024 * 1024 + 1
        with self.assertRaises(execution_protocol.LifecycleError):
            execution_protocol._candidate_members(archive)

    def test_executable_runtime_and_escaping_inputs_rejected(self):
        for name in (
            "library-packages/demo/1.0.0/roles/library_demo/tasks/main.yml",
            "application-packages/gateway/1.0.0/plugins/action/test.py",
            "library-packages/demo/1.0.0/secrets/admin-token",
            "library-packages/demo/1.0.0/assets/../../secret.txt",
            "library-packages/demo/latest/library.yml",
        ):
            with self.subTest(name=name):
                self.assertFalse(execution_protocol._candidate_logical_path(name))

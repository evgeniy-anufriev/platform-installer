"""Target-free Ansible acceptance for directory and archive reconciliation."""
import hashlib
import os
import pwd
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

import yaml


TASKS = Path(__file__).resolve().parents[1] / "collections/ansible_collections/platform/core/roles/application_runtime/tasks"


class ConfigTreeQATest(unittest.TestCase):
    def test_directory_and_archive_repeat_without_changes(self):
        with tempfile.TemporaryDirectory(prefix="application-config-trees-") as temporary:
            root = Path(temporary)
            source = root / "provider.jar"
            source.write_bytes(b"provider-v1")
            archive = root / "themes.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                info = tarfile.TarInfo("themes/index.txt")
                info.size = len(b"theme-v1")
                import io
                stream.addfile(info, io.BytesIO(b"theme-v1"))
            instance = root / "instance"
            provider_dest = instance / "config/providers/provider.jar"
            archive_dest = instance / "config/themes/index.txt"
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            job = {
                "instancePath": str(instance), "account": pwd.getpwuid(os.getuid()).pw_name,
                "archiveChecksums": {"themes": checksum},
                "configs": [],
                "directoryConfigs": [{"destination": "providers", "members": [{"destination": "providers/provider.jar"}],
                                      "subdirectories": [], "directory_mode": "0755"}],
                "archiveConfigs": [{"destination": "themes", "path": str(archive)}],
            }
            placement_tasks = yaml.safe_load((TASKS / "apply_instance.yml").read_text(encoding="utf-8"))[:4]
            placement_tasks[-1]["ansible.builtin.include_tasks"] = str(TASKS / "apply_directory.yml")
            play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": {"application_runtime_job": job,
                              "application_archive": {"destination": "themes", "path": str(archive)}},
                     "tasks": placement_tasks + [
                         {"ansible.builtin.copy": {"src": str(source), "dest": str(provider_dest), "mode": "0644"}},
                         {"ansible.builtin.include_tasks": str(TASKS / "apply_archive.yml")},
                     ]}]
            playbook = root / "playbook.yml"
            playbook.write_text(yaml.safe_dump(play), encoding="utf-8")

            def run():
                result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(playbook)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                self.assertEqual(0, result.returncode, result.stdout[-3000:])
                return result.stdout

            run()
            self.assertEqual(b"provider-v1", provider_dest.read_bytes())
            self.assertEqual(b"theme-v1", archive_dest.read_bytes())
            self.assertIn("changed=0", run())
            (instance / "config/providers/stale.jar").write_bytes(b"stale")
            run()
            self.assertFalse((instance / "config/providers/stale.jar").exists())
            self.assertIn("changed=0", run())
            backup = instance / ("config/.archive-previous-" + hashlib.sha256(b"themes").hexdigest())
            (instance / "config/themes").rename(backup)
            run()
            self.assertEqual(b"theme-v1", archive_dest.read_bytes())
            self.assertFalse(backup.exists())
            self.assertIn("changed=0", run())

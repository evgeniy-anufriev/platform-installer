import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/postgresql/roles/postgresql/tasks"


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible runtime required")
class PostgresPackageBatchRuntimeTests(unittest.TestCase):
    def test_sources_remain_independent_and_only_one_package_transaction_is_selected(self):
        reconcile = yaml.safe_load((TASKS / "reconcile.yml").read_text())
        query = copy.deepcopy(reconcile[0])
        query["ansible.builtin.include_tasks"] = str(TASKS / "resolve_packages.yml")
        install = copy.deepcopy(next(t for t in reconcile if "ansible.builtin.package" in t))
        self.assertEqual(1, sum("ansible.builtin.package" in t for t in reconcile))
        # Execute the production name/vars/when with a harmless target action.
        install["ansible.builtin.set_fact"] = {"selected_packages": install.pop("ansible.builtin.package")["name"]}
        with tempfile.TemporaryDirectory(prefix="platform-postgres-packages-") as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            cli = root / "bin/dnf"
            cli.write_text("#!/usr/bin/python3\nimport json,pathlib,sys\n"
                           "root=pathlib.Path(__file__).resolve().parents[1]\n"
                           "state=json.loads((root/'state').read_text())\n"
                           "with (root/'calls').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')\n"
                           "major=any(x.startswith('postgresql16-') for x in sys.argv)\n"
                           "failover=any(x.startswith('pg_auto_failover-') for x in sys.argv)\n"
                           "family=state['family'];rc=0\n"
                           "if failover:\n"
                           " print('pg_auto_failover-16-2.2-1.x86_64')\n"
                           "else:\n"
                           " names=['postgresql16-16.14-1.x86_64','postgresql16-server-16.14-1.x86_64','postgresql16-contrib-16.14-1.x86_64'] if major else ['postgresql-16.14-1.x86_64','postgresql-server-16.14-1.x86_64','postgresql-contrib-16.14-1.x86_64']\n"
                           " if family=='major' and not major:names=[]\n"
                           " if family=='incomplete':names=names[:1 if major else 2]\n"
                           " if family=='error-output' and not major:rc=1\n"
                           " print('\\n'.join(names))\n"
                           "sys.exit(rc)\n")
            cli.chmod(0o700)
            for base, failover, family, success, query_count, count in (
                    (True, True, "legacy", True, 2, 4),
                    (True, False, "legacy", True, 1, 3),
                    (False, True, "legacy", True, 1, 1),
                    (False, False, "legacy", True, 0, 0),
                    (True, True, "major", True, 3, 4),
                    (True, True, "error-output", True, 3, 4),
                    (True, True, "incomplete", False, 2, 0)):
                with self.subTest(base=base, failover=failover, family=family):
                    (root / "state").write_text(json.dumps({"family": family}))
                    (root / "calls").write_text("")
                    variables = {"ansible_facts": {"pkg_mgr": "dnf"}, "platform_postgresql_verify_only": False,
                        "platform_postgresql_mode": "pg_auto_failover", "platform_postgresql_version": "16.14",
                        "platform_postgresql_pg_auto_failover_version": "2.2",
                        "platform_resolved_artifact_sources": {
                            "postgresql-runtime": {"source": "REPOSITORY" if base else "OFFLINE_BUNDLE"},
                            "pg-auto-failover": {"source": "REPOSITORY" if failover else "OFFLINE_BUNDLE"}}}
                    play = root / "play.yml"
                    play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                        "vars": variables, "tasks": [query, install, {"ansible.builtin.assert": {"that": [
                            "selected_packages | default([]) | length == " + str(count)]}}]}]))
                    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                        env=dict(os.environ, PATH=str(root / "bin") + ":" + os.environ["PATH"]),
                        capture_output=True, text=True, timeout=60)
                    self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)
                    calls = (root / "calls").read_text().splitlines()
                    self.assertEqual(query_count, len(calls))

    def test_binary_discovery_repeats_only_after_install_or_missing_binary(self):
        reconcile = yaml.safe_load((TASKS / "reconcile.yml").read_text())
        task = copy.deepcopy(next(t for t in reconcile if "Определение каталога исполняемых файлов PostgreSQL после установки" in t["name"]))
        task.pop("ansible.builtin.include_tasks")
        task["ansible.builtin.set_fact"] = {"repeated": True}
        with tempfile.TemporaryDirectory(prefix="platform-postgres-binary-") as directory:
            root = Path(directory)
            for changed, exists in ((False, True), (False, False), (True, True), (True, False)):
                play = root / "play.yml"
                play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                    "vars": {"_platform_postgresql_package_install": {"changed": changed},
                             "_platform_postgresql_binary_candidate_stats": {"results": [{"stat": {"exists": exists}}]}},
                    "tasks": [task, {"ansible.builtin.assert": {"that": [
                        "(repeated | default(false) | bool) == " + str(changed or not exists).lower()]}}]}]))
                result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

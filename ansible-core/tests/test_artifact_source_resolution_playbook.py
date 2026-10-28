import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64


def authority(requirement_id, name, offline):
    return {"apiVersion": "platform.installer/artifact-source-authority/v1alpha1", "kind": "ArtifactSourceAuthority", "sourcePolicy": "REPOSITORY_THEN_OFFLINE", "repository": {"kind": "REPOSITORY"}, "requirement": {"id": "test:" + requirement_id, "serviceDeployment": "test", "requirementId": requirement_id, "name": name, "version": "4.3.1", "os": "redos", "architecture": "x86_64"}, "offlineBundle": {"kind": "OFFLINE_BUNDLE", "bundleDigest": DIGEST, "ref": "runtime/artifacts/test/%s.tgz" % requirement_id, "sha256": DIGEST, "size": 1, "type": "archive"} if offline else None}


@unittest.skipUnless(shutil.which("ansible-playbook"), "requires Ansible")
class ArtifactSourceResolutionPlaybookTests(unittest.TestCase):
    def test_batch_query_keeps_per_requirement_policy_and_failed_batch_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools"
            tools.mkdir()
            dnf = tools / "dnf"
            dnf.write_text("#!/usr/bin/python3\nimport json,pathlib,sys\n"
                           "root=pathlib.Path(__file__).resolve().parents[1]\n"
                           "names=sys.argv[sys.argv.index('--queryformat')+2:]\n"
                           "with (root/'calls').open('a') as f:f.write(json.dumps(names)+'\\n')\n"
                           "if (root/'fail-batch').exists() and len(names)>1:sys.exit(1)\n"
                           "rows={'repository':'repository\\t4.3.1\\tx86_64', 'wrong-version':'wrong-version\\t4.2.0\\tx86_64', 'wrong-arch':'wrong-arch\\t4.3.1\\taarch64'}\n"
                           "for name in names:\n if name in rows:print(rows[name])\n"
                           "sys.exit(0 if any(n in rows for n in names) else 1)\n")
            dnf.chmod(0o700)
            names = ["repository", "wrong-version", "wrong-arch", "missing"]
            variables = {"platform_execution_service_deployment": "test",
                         "platform_artifact_source_authorities_by_deployment": {"test": {
                             name: authority(name, name, name != "missing") for name in names}},
                         "platform_artifact_requirements": [{"id": name, "name": name} for name in names]}
            play = root / "play.yml"
            play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": variables, "tasks": [
                    {"ansible.builtin.include_role": {"name": "platform.core.artifact_source_resolution"}},
                    {"ansible.builtin.assert": {"that": [
                        "platform_resolved_artifact_sources.repository.source == 'REPOSITORY'",
                        "platform_resolved_artifact_sources['wrong-version'].source == 'OFFLINE_BUNDLE'",
                        "platform_resolved_artifact_sources['wrong-arch'].source == 'OFFLINE_BUNDLE'",
                        "platform_resolved_artifact_sources.missing.source == 'BLOCKED'"]}},
                ]}]))
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core/collections"),
                               PATH=str(tools) + os.pathsep + os.environ.get("PATH", ""))
            for failed_batch in (False, True):
                with self.subTest(failed_batch=failed_batch):
                    marker = root / "fail-batch"
                    if failed_batch:
                        marker.touch()
                    (root / "calls").write_text("")
                    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                            env=environment, capture_output=True, text=True, timeout=60)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    calls = [json.loads(line) for line in (root / "calls").read_text().splitlines()]
                    self.assertEqual(sorted(names), calls[0])
                    self.assertEqual(5 if failed_batch else 1, len(calls))

    def test_delivery_root_uses_bundle_with_manual_override_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory = root / 'hosts.yml'
            inventory.write_text(json.dumps({'all': {'hosts': {
                'bundle': {'ansible_connection': 'local', 'platform_execution_bundle_root': '/tmp/exact-bundle', 'expected': '/tmp/exact-bundle'},
                'manual': {'ansible_connection': 'local', 'platform_execution_bundle_root': '/tmp/exact-bundle', 'platform_execution_runtime_root': '/tmp/manual', 'expected': '/tmp/manual'},
                'legacy': {'ansible_connection': 'local', 'expected': '/var/lib/platform-installer/runtime/current'},
            }}}), encoding='utf-8')
            playbook = root / 'play.yml'
            playbook.write_text('''- hosts: all
  gather_facts: false
  vars:
    platform_artifact_delivery_requirements: []
  tasks:
    - include_role:
        name: platform.core.artifact_delivery
        public: true
    - assert:
        that: platform_execution_runtime_root == expected
''', encoding='utf-8')
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core' / 'collections'))
            completed = subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook)],
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_unset_resolution_fact_is_populated_for_repository_and_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); tools = root / "tools"; tools.mkdir()
            dnf = tools / "dnf"
            dnf.write_text("#!/bin/sh\ncase \"$*\" in *repository*) printf 'repository\\t4.3.1\\tx86_64\\n'; exit 0;; *) exit 1;; esac\n", encoding="utf-8")
            dnf.chmod(0o700)
            inventory = root / "hosts.yml"; inventory.write_text("all:\n  hosts:\n    localhost:\n      ansible_connection: local\n", encoding="utf-8")
            variables = {"platform_execution_service_deployment": "test", "platform_artifact_source_authorities_by_deployment": {"test": {"repository": authority("repository", "repository", False), "offline": authority("offline", "offline", True)}}, "platform_artifact_requirements": [{"id": "repository", "name": "repository"}, {"id": "offline", "name": "offline"}]}
            playbook = root / "play.yml"
            playbook.write_text("---\n- hosts: all\n  gather_facts: false\n  vars: %s\n  tasks:\n    - include_role:\n        name: platform.core.artifact_source_gate\n    - assert:\n        that:\n          - platform_resolved_artifact_sources.repository.source == 'REPOSITORY'\n          - platform_resolved_artifact_sources.offline.source == 'OFFLINE_BUNDLE'\n" % json.dumps(variables), encoding="utf-8")
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core" / "collections"), PATH=str(tools) + os.pathsep + os.environ.get("PATH", ""))
            completed = subprocess.run(["ansible-playbook", "-i", str(inventory), str(playbook)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, check=False)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()

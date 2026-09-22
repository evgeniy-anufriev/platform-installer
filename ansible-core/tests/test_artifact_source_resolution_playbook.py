import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64


def authority(requirement_id, name, offline):
    return {"apiVersion": "platform.installer/artifact-source-authority/v1alpha1", "kind": "ArtifactSourceAuthority", "sourcePolicy": "REPOSITORY_THEN_OFFLINE", "repository": {"kind": "REPOSITORY"}, "requirement": {"id": "test:" + requirement_id, "serviceDeployment": "test", "requirementId": requirement_id, "name": name, "version": "4.3.1", "os": "redos", "architecture": "x86_64"}, "offlineBundle": {"kind": "OFFLINE_BUNDLE", "bundleDigest": DIGEST, "ref": "runtime/artifacts/test/%s.tgz" % requirement_id, "sha256": DIGEST, "size": 1, "type": "archive"} if offline else None}


@unittest.skipUnless(shutil.which("ansible-playbook"), "requires Ansible")
class ArtifactSourceResolutionPlaybookTests(unittest.TestCase):
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

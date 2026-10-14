import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from execution_lifecycle import LifecycleError, digest
import execution_target_trust as trust
import execution_controller
from execution_controller import _environment
from ansible_collections.platform.core.plugins.action.project_snapshot import snapshot_execution_connection


def fixture(tmp_path):
    state = tmp_path / "execution"
    run_id = "installer-123456"
    run = state / "runs" / run_id
    run.mkdir(parents=True, mode=0o700)
    manifest = {
        "projectIdentity": "test-project", "projectRevision": "sha256:" + "1" * 64,
        "planFingerprint": "sha256:" + "2" * 64,
        "runtimeRelease": {"bundleDigest": "sha256:" + "3" * 64},
        "operations": [{"operation": "PKI_APPLY"}],
        "targetConnections": {
            "node1": {"address": "192.0.2.1", "port": 22, "mode": "ssh", "unsupportedOptions": False},
            "node2": {"address": "192.0.2.2", "port": 2222, "mode": "ssh", "unsupportedOptions": False},
        },
    }
    manifest_path = run / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_path.chmod(0o600)
    kind = "ssh-ed25519"
    key = base64.b64encode(len(kind).to_bytes(4, "big") + kind.encode() + b"a" * 32).decode()
    request = {
        "stagingId": run_id, "projectIdentity": manifest["projectIdentity"],
        "projectRevision": manifest["projectRevision"],
        "planFingerprint": manifest["planFingerprint"],
        "runtimeRelease": manifest["runtimeRelease"],
        "manifestDigest": digest(manifest),
        "approvals": [
            {"hostId": "node1", "address": "192.0.2.1", "port": 22, "keyType": kind, "publicKey": key},
            {"hostId": "node2", "address": "192.0.2.2", "port": 2222, "keyType": kind, "publicKey": key},
        ],
    }
    return state, run, manifest, request


class TargetHostTrustTests(unittest.TestCase):
    def test_stage_and_verify_exact_plan_trust(self):
        with tempfile.TemporaryDirectory() as root:
            state, run, manifest, request = fixture(Path(root))
            trust.stage(str(state), request)
            self.assertEqual(str(run / "known_hosts"), trust.verify(str(state), request["stagingId"], manifest))
            self.assertEqual(0o600, (run / "known_hosts").stat().st_mode & 0o777)
            self.assertIn(b"[192.0.2.2]:2222", (run / "known_hosts").read_bytes())
            with self.assertRaisesRegex(LifecycleError, "TARGET_HOST_TRUST_INVALID"):
                trust.stage(str(state), request)

    def test_stage_rejects_mismatched_endpoint_or_binding(self):
        changes = (
            lambda request: request["approvals"][0].update(address="192.0.2.99"),
            lambda request: request["approvals"][1].update(port=22),
            lambda request: request["approvals"].pop(),
            lambda request: request.update(planFingerprint="sha256:" + "f" * 64),
        )
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                state, run, _, request = fixture(Path(root))
                change(request)
                with self.assertRaisesRegex(LifecycleError, "TARGET_HOST_TRUST_INVALID"):
                    trust.stage(str(state), request)
                self.assertFalse((run / "known_hosts").exists())

    def test_stage_rejects_local_connection_and_override(self):
        for field, value in (("mode", "local"), ("unsupportedOptions", True)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                state, run, manifest, request = fixture(Path(root))
                manifest["targetConnections"]["node1"][field] = value
                (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                request["manifestDigest"] = digest(manifest)
                with self.assertRaisesRegex(LifecycleError, "TARGET_HOST_TRUST_INVALID"):
                    trust.stage(str(state), request)

    def test_ssh_destination_alias_blocks_before_target_command(self):
        with tempfile.TemporaryDirectory() as root:
            state, run, manifest, request = fixture(Path(root))
            host = {"ansibleHost": "192.0.2.1", "ansiblePort": 22}
            manifest["targetConnections"]["node1"] = snapshot_execution_connection(
                {"ansible_ssh_host": "192.0.2.99"}, host)
            manifest_path = run / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            request["manifestDigest"] = digest(manifest)
            request["approvals"] = [request["approvals"][0], request["approvals"][1]]
            with self.assertRaisesRegex(LifecycleError, "TARGET_HOST_TRUST_INVALID"):
                trust.stage(str(state), request)

            journal = type("Journal", (), {
                "root": str(state), "run_id": request["stagingId"], "directory": str(run),
            })()
            operation = {"operationId": "pki:apply", "operation": "PKI_APPLY"}
            with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook"]), \
                 mock.patch.object(execution_controller.subprocess, "Popen") as launch:
                with self.assertRaises((LifecycleError, OSError)):
                    execution_controller._dispatch("/runtime/release", journal, {"operations": [operation]}, [False])
            launch.assert_not_called()

    def test_replacement_or_marker_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            state, run, manifest, request = fixture(Path(root))
            trust.stage(str(state), request)
            (run / "known_hosts").write_text("192.0.2.1 ssh-ed25519 bogus\n", encoding="ascii")
            with self.assertRaisesRegex(LifecycleError, "TARGET_HOST_TRUST_INVALID"):
                trust.verify(str(state), request["stagingId"], manifest)
            (run / "known_hosts").unlink()
            (run / "known_hosts").symlink_to(run / "manifest.json")
            with self.assertRaises(OSError):
                trust.verify(str(state), request["stagingId"], manifest)

    def test_controller_ssh_environment_is_run_local(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {"ANSIBLE_SSH_EXTRA_ARGS": "-o StrictHostKeyChecking=no"}):
            path = Path(root)
            journal = type("Journal", (), {"root": str(path), "directory": str(path / "installer-123456"), "run_id": "installer-123456"})()
            environment = _environment(str(path), journal, {"phaseId": "pki", "operationId": "pki:apply", "serviceDeployment": None}, True)
            self.assertEqual("True", environment["ANSIBLE_HOST_KEY_CHECKING"])
            self.assertNotIn("ANSIBLE_SSH_EXTRA_ARGS", environment)
            for option in ("-F none", "StrictHostKeyChecking=yes", "GlobalKnownHostsFile=none", "KnownHostsCommand=none", "UpdateHostKeys=no"):
                self.assertIn(option, environment["ANSIBLE_SSH_ARGS"])
            self.assertIn("UserKnownHostsFile=" + str(path / "installer-123456" / "known_hosts"), environment["ANSIBLE_SSH_ARGS"])


if __name__ == "__main__":
    unittest.main()

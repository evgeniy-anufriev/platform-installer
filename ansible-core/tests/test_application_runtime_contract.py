"""Focused typed preflight/security tests; real Compose QA is separate."""
import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import shutil
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UTILS = ROOT / "ansible-core/collections/ansible_collections/platform/core/plugins/module_utils"
sys.path.insert(0, str(UTILS))
from application_runtime import bundle_archive, selected_archive, runtime_reference, pinned_registry_reference, prepare_runtime, validate_compose, validate_config_contents, safe_relative
from artifact_authority import assemble_authority
from schema_validation import SchemaValidator
from application_libraries import load_package
import application_libraries as APP
import hashlib

spec = importlib.util.spec_from_file_location("artifact_source_a2", UTILS.parent / "filter/artifact_source.py")
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)
DIGEST = "sha256:" + "a" * 64


class ApplicationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.requirement = {"id": "api:image", "name": "probe:qa", "artifactType": "container-image",
                            "imageId": DIGEST, "platform": {"os": "linux", "architecture": "amd64"}, "localReference": "probe:locked"}
        self.offline = {"kind": "OFFLINE_BUNDLE", "bundleDigest": DIGEST, "ref": "runtime/artifacts/probe/image.tar",
                        "sha256": DIGEST, "size": 12, "type": "archive"}
        self.authority = assemble_authority(self.requirement, self.offline, {"kind": "REPOSITORY", "reference": "registry.local/probe", "manifestDigest": DIGEST}, image=True)

    def source(self, rc=0, payload=None, platform=None):
        return SOURCE.resolve_artifact_source(self.authority, self.requirement, "node1", platform or self.requirement["platform"],
                                              json.dumps(payload or {"config": {"digest": DIGEST}}), rc)

    def test_registry_priority_and_typed_schema(self):
        result = self.source()
        self.assertEqual("REPOSITORY", result["source"])
        validator = SchemaValidator(str(ROOT / "contracts"))
        self.assertEqual([], validator.validate(result, str(ROOT / "contracts/artifact-source/v1alpha2/schema.json")))

    def test_registry_missing_falls_back_but_auth_transport_failure_blocks(self):
        self.assertEqual("OFFLINE_BUNDLE", self.source(rc=2)["source"])
        self.assertEqual("BLOCKED", self.source(rc=1)["source"])

    def test_wrong_platform_or_manifest_identity(self):
        self.assertEqual("BLOCKED", self.source(platform={"os": "linux", "architecture": "arm64"})["source"])
        self.assertEqual("OFFLINE_BUNDLE", self.source(payload={"config": {"digest": "sha256:" + "b" * 64}})["source"])

    def test_requirement_rebinding_cannot_change_image(self):
        with self.assertRaises(ValueError):
            SOURCE.resolve_artifact_source(self.authority, dict(self.requirement, imageId="sha256:" + "b" * 64), "node1")

    def test_legacy_rpm_authority_version_remains_v1(self):
        self.assertEqual("platform.installer/artifact-source-authority/v1alpha1", assemble_authority({"name": "rpm"})["apiVersion"])

    def test_runtime_packages_use_the_standard_validator_interface(self):
        validator = SchemaValidator(str(ROOT / "contracts"))
        root = ROOT / "examples/valid/application-runtime"
        loader = lambda path: json.loads(Path(path).read_text())
        package = load_package(str(root), "apigateway@1.0.0", "application", loader, validator)
        self.assertIn(package["render"]["compose_template"], package["files"])

    def runtime_fixture(self, root=None):
        root = root or ROOT / "examples/valid/application-runtime"
        loader = lambda path: json.loads(Path(path).read_text())
        validator = SchemaValidator(str(ROOT / "contracts"))
        app = load_package(str(root), "apigateway@1.0.0", "application", loader, validator)
        lib = load_package(str(root), "sdku@1.0.0", "library", loader, validator)
        settings = app["definition"]["defaults"]
        row = {"libraryId": "sdku", "instanceId": "apigateway-sdku", "hostId": "node1", "resources": {},
               "applicationName": "apigateway", "applicationVersion": "1.0.0", "libraryRef": "sdku@1.0.0", "runtimeRef": "docker",
               "settings": settings, "packageIdentity": {"application": app["digest"], "library": lib["digest"]}}
        snapshot = {"validation": {"status": "PASS"}, "applicationLibraries": {"status": "PASS", "libraries": {
            "sdku": {"instances": {"apigateway-sdku": {"placements": {"node1": {}}, "credentialRequirements": [], "agentRequired": False, "connections": {}}}}}},
            "effectiveConfiguration": {"services": {"docker": {"configuration": {"accountName": {"state": "RESOLVED", "value": "platform-docker"}}}}}}
        lock = loader(root / "inventory/group_vars/all/platform-installer.yml")["platform_artifact_lock"]
        return str(root), snapshot, [row], {}, lock, validator, loader

    def prepare_fixture(self, image_patch=None):
        inputs = self.runtime_fixture()
        inputs[4]["x-container-images"]["images"][inputs[2][0]["settings"]["image"]].update(image_patch or {})
        return prepare_runtime(*inputs)

    def test_runtime_preparation_reads_shared_packages_once_for_many_placements(self):
        inputs = self.runtime_fixture()
        rows = inputs[2]
        instance = inputs[1]["applicationLibraries"]["libraries"]["sdku"]["instances"]["apigateway-sdku"]
        for number in range(2, 31):
            host = "node%s" % number
            instance["placements"][host] = {}
            rows.append(dict(rows[0], hostId=host))
        with patch.object(APP, "package_inputs", wraps=APP.package_inputs) as scans, \
                patch.object(APP, "load_package", wraps=APP.load_package) as loads:
            jobs = prepare_runtime(*inputs)
        self.assertEqual(30, len(jobs))
        self.assertEqual(1, scans.call_count)
        self.assertEqual(2, loads.call_count)
        self.assertEqual(2, len({(call.args[2], call.args[1]) for call in loads.call_args_list}))

    def test_runtime_preparation_rechecks_changed_bytes_in_next_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "examples/valid/application-runtime", root, dirs_exist_ok=True)
            inputs = self.runtime_fixture(root)
            self.assertEqual(1, len(prepare_runtime(*inputs)))
            with (root / "library-packages/sdku/1.0.0/files/.env").open("a") as stream:
                stream.write("EXTRA=value\n")
            with self.assertRaisesRegex(ValueError, "APPLICATION_PACKAGE_CHANGED"):
                prepare_runtime(*inputs)

    def test_optional_fallback_is_not_an_eager_preparation_prerequisite(self):
        jobs = self.prepare_fixture()
        self.assertIsNone(jobs[0]["archivePath"])
        offline = jobs[0]["authority"]["offlineBundle"]
        loader = lambda path: json.loads(Path(path).read_text())
        self.assertIsNone(selected_archive(None, "REPOSITORY", offline, loader))
        self.assertIsNone(selected_archive("/nonexistent-bundle", "REPOSITORY", offline, loader))
        with self.assertRaisesRegex(ValueError, "APPLICATION_BUNDLE_REQUIRED"):
            selected_archive(None, "OFFLINE_BUNDLE", offline, loader)
        with self.assertRaises(ValueError):
            selected_archive("/nonexistent-bundle", "OFFLINE_BUNDLE", offline, loader)

    def test_runtime_reference_binds_full_image_digest_without_operator_input(self):
        a, b = runtime_reference(DIGEST), runtime_reference("sha256:" + "b" * 64)
        self.assertNotEqual(a, b)
        self.assertEqual("platform-application:sha256-" + "a" * 64, a)
        job = self.prepare_fixture()[0]
        self.assertEqual(runtime_reference(job["authority"]["requirement"]["imageId"]), job["authority"]["requirement"]["localReference"])
        with self.assertRaises(ValueError):
            self.prepare_fixture({"localReference": a})

    def test_registry_pinning_removes_tag_but_preserves_registry_port(self):
        for reference, expected in (("docker.io/library/nginx:1.28.0-alpine", "docker.io/library/nginx"),
                                    ("registry.example:5000/team/image:tag", "registry.example:5000/team/image"),
                                    ("registry.example:5000/team/image", "registry.example:5000/team/image")):
            self.assertEqual(expected + "@" + DIGEST, pinned_registry_reference(reference, DIGEST))

    def test_verified_archive_and_symlink_or_changed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "runtime/artifacts/probe/image.tar"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"locked archive")
            sha = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
            record = {"ref": "runtime/artifacts/probe/image.tar", "sha256": sha, "size": archive.stat().st_size}
            manifest = {"apiVersion": "platform.installer/execution-bundle/v1alpha1", "kind": "ExecutionRuntimeBundle",
                        "components": [{"path": record["ref"], "sha256": sha, "size": record["size"]}]}
            manifest_path = root / "manifest.yaml"
            manifest_path.write_text(json.dumps(manifest))
            digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            loader = lambda path: json.loads(Path(path).read_text())
            self.assertEqual(str(archive), bundle_archive(str(root), digest, record, loader))
            archive.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                bundle_archive(str(root), digest, record, loader)
            archive.unlink()
            archive.symlink_to(manifest_path)
            with self.assertRaises(ValueError):
                bundle_archive(str(root), digest, record, loader)

    def test_config_path_rejects_traversal_and_absolute(self):
        for path in ("../file", "/etc/file", "dir/../file", "dir\\file", "dir//file"):
            self.assertFalse(safe_relative(path))
        self.assertTrue(safe_relative("dir/file.conf"))

    def test_shared_env_and_config_reject_plaintext_secrets_and_unbounded_bytes(self):
        self.assertTrue(validate_config_contents([{"content": "REQUEST_TIMEOUT_MS=30000\nSERVER_ID=node1\n"}]))
        for content in ("password=example", "PG_TOKEN: example", "role_id=example", "x" * (1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                validate_config_contents([{"content": content}])

    def test_compose_rejects_identity_secret_privilege_and_external_mount(self):
        job = {"instanceId": "api-sdku", "projectId": "project", "libraryId": "sdku", "hostId": "node1",
               "placement": {"composeProject": "project-sdku-api-node1", "containerName": "project-api-node1"},
               "authority": self.authority, "settings": {"command": ["/usr/bin/probe"]}, "identityNames": [], "configs": []}
        service = {"image": "probe:locked", "container_name": "project-api-node1", "command": ["/usr/bin/probe"],
                   "labels": {"platform.installer.project": "project", "platform.installer.library": "sdku",
                              "platform.installer.instance": "api-sdku", "platform.installer.host": "node1", "platform.installer.config-digest": "c" * 64}}
        config = {"name": "project-sdku-api-node1", "services": {"api-sdku": service}}
        self.assertTrue(validate_compose(config, job, "/private/api", "/private/lib", "c" * 64))
        for patch in ({"privileged": True}, {"image": "unlocked:latest"}, {"entrypoint": ["/other/launcher"]}, {"environment": {"PGPASSWORD": "DO-NOT-PRINT"}},
                      {"volumes": [{"type": "bind", "source": "/etc", "target": "/host", "read_only": True}]},
                      {"labels": dict(service["labels"], **{"platform.installer.config-digest": "forged"})}):
            changed = copy.deepcopy(config)
            changed["services"]["api-sdku"].update(patch)
            with self.assertRaises(ValueError):
                validate_compose(changed, job, "/private/api", "/private/lib", "c" * 64)


if __name__ == "__main__":
    unittest.main()

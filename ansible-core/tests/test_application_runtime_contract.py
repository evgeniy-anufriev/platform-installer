"""Focused typed preflight/security tests; real Compose QA is separate."""
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
from application_runtime import bundle_archive, selected_archive, runtime_reference, pinned_registry_reference, image_requirement, prepare_runtime, validate_compose, validate_config_contents, safe_relative
from artifact_authority import assemble_authority
from schema_validation import SchemaValidator
from application_libraries import load_package
import application_libraries as APP
import hashlib
import base64
import subprocess

spec = importlib.util.spec_from_file_location("artifact_source_a2", UTILS.parent / "filter/artifact_source.py")
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)
DIGEST = "sha256:" + "a" * 64


class ApplicationRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ansible-playbook'), 'requires native Ansible')
    def test_rendered_json_configuration_remains_file_text(self):
        import yaml
        core = ROOT / 'ansible-core'
        tasks = yaml.safe_load((core / 'collections/ansible_collections/platform/core/roles/application_runtime/tasks/preflight.yml').read_text())
        render = next(task for task in tasks if task.get('name') == 'Рендеринг объявленных файлов конфигурации в частную память')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'config.json.j2')
            source.write_text('{"endpoint": "{{ example_endpoint }}"}\n', encoding='utf-8')
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': {'example_endpoint': 'https://example.internal', 'application_config_contents': [],
                              'application_runtime_job': {'configs': [{'template': True, 'path': str(source),
                                                                       'destination': 'config.json'}]}},
                     'tasks': [render, {'ansible.builtin.assert': {'that': [
                         'application_config_contents[0].content is string',
                         '(application_config_contents[0].content | from_json).endpoint == example_endpoint',
                         'application_config_contents | platform.core.application_validate_configs']}}]}]
            filename = Path(directory, 'probe.yml')
            filename.write_text(yaml.safe_dump(play), encoding='utf-8')
            environment = dict(os.environ, ANSIBLE_CONFIG=str(core / 'ansible.cfg'),
                               ANSIBLE_COLLECTIONS_PATH=str(core / 'collections'))
            completed = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(filename)],
                                       env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

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

    def test_skipped_provider_context_does_not_resolve_an_image_or_runtime_payload(self):
        import copy
        inputs = self.runtime_fixture()
        snapshot, rows = inputs[1], inputs[2]
        snapshot['project'] = {'id': 'project'}
        libraries = snapshot['applicationLibraries']['libraries']
        libraries['provider'] = copy.deepcopy(libraries['sdku'])
        provider_row = copy.deepcopy(rows[0])
        provider_row['libraryId'] = 'provider'
        provider_row['settings']['image'] = 'must-not-be-resolved:qa'
        rows.append(provider_row)
        snapshot['applicationExecutionScope'] = dict(installLibraries=['sdku'], providerLibraries=['provider'])
        contexts = []
        jobs = prepare_runtime(*inputs, script_contexts=contexts)
        self.assertEqual(['sdku'], [job['libraryId'] for job in jobs])
        self.assertEqual(['provider'], [job['libraryId'] for job in contexts])
        for key in ('authority', 'configs', 'pkiPlans', 'vault', 'agentTemplate', 'composeArgv'):
            self.assertNotIn(key, contexts[0])
        self.assertEqual({'parameters', 'endpoint'}, set(contexts[0]['settings']))
        self.assertNotIn('registryCredentials', contexts[0])

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

    def test_runtime_preparation_accepts_declared_library_kafka_topics(self):
        inputs = self.runtime_fixture()
        inputs[2][0]['resources']['events'] = dict(kind='kafka.topic', binding='kafka', mode='managed',
                                                  parameters=dict(name='sdku-main'))
        jobs = prepare_runtime(*inputs)
        self.assertEqual(1, len(jobs))
        self.assertEqual('kafka.topic', jobs[0]['resources']['events']['kind'])

    def test_runtime_preparation_accepts_projected_kafka_scram_account(self):
        inputs = self.runtime_fixture()
        instance = inputs[1]['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        instance['credentialRequirements'] = {'kafka': {}}
        instance['connections']['kafka'] = dict(serviceType='kafka', securityProtocol='SASL_SSL',
                                                saslMechanism='SCRAM-SHA-512')
        jobs = prepare_runtime(*inputs)
        self.assertEqual(1, len(jobs))
        self.assertEqual(inputs[2][0]['instanceId'], jobs[0]['instanceId'])

    def test_runtime_preparation_accepts_projected_application_account(self):
        inputs = self.runtime_fixture()
        instance = inputs[1]['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        instance['credentialRequirements'] = {'identity': {}}
        instance['connections']['identity'] = dict(serviceType='application', libraryId='provider',
                                                    applicationId='identity-api', protocol='https')
        jobs = prepare_runtime(*inputs)
        self.assertEqual(1, len(jobs))
        self.assertEqual('application', instance['connections']['identity']['serviceType'])

    def test_runtime_preparation_still_rejects_unsupported_account_provider(self):
        for service_type in ('vault', 'unsupported'):
            with self.subTest(service_type=service_type):
                inputs = self.runtime_fixture()
                instance = inputs[1]['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
                instance['credentialRequirements'] = {'other': {}}
                instance['connections']['other'] = dict(serviceType=service_type)
                with self.assertRaisesRegex(ValueError, 'APPLICATION_RUNTIME_DEFERRED_FEATURE'):
                    prepare_runtime(*inputs)

    def test_runtime_preparation_accepts_library_redis_name_references(self):
        inputs = self.runtime_fixture()
        resources = inputs[2][0]['resources']
        for key in ('dm-meta', 'alert-hdl', 'alert-class'):
            resources[key] = dict(kind='redis.key', binding='cache', parameters=dict(name='sdku-' + key))
        jobs = prepare_runtime(*inputs)
        self.assertEqual(1, len(jobs))
        self.assertEqual(resources, jobs[0]['resources'])

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

    def test_uppercase_image_tags_preserve_repository_and_digest_guards(self):
        image = {"imageId": DIGEST, "platform": {"os": "linux", "architecture": "amd64"}}
        for reference in ("evoscada-docker.artifacts.tn.tngrp.ru/data-manager:1.5.0-SNAPSHOT-7a795dc1-redos",
                          "registry.example:5000/team/image:SNAPSHOT"):
            with self.subTest(reference=reference):
                self.assertEqual(reference, image_requirement("dm", reference, image)["name"])
                self.assertEqual(reference.rsplit(":", 1)[0] + "@" + DIGEST,
                                 pinned_registry_reference(reference, DIGEST))
                self.assertEqual(reference + "@" + DIGEST,
                                 image_requirement("dm", reference + "@" + DIGEST, image)["name"])
        for reference in ("registry.example/Team/image:SNAPSHOT", "registry.example/image:BAD TAG",
                          "registry.example/image:SNAPSHOT;echo", "registry.example/image@sha256:" + "A" * 64):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                image_requirement("dm", reference, image)

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

    def test_shared_env_remains_bounded_but_declared_configs_accept_ordinary_values(self):
        self.assertTrue(validate_config_contents([{"content": "REQUEST_TIMEOUT_MS=30000\nSERVER_ID=node1\n"}]))
        self.assertTrue(validate_config_contents([{"destination": "script.lua", "content": "token=example\npassword=example"}]))
        self.assertTrue(validate_config_contents([{"destination": "large.conf", "content": "x" * (1024 * 1024 + 1)}]))
        with self.assertRaises(ValueError):
            validate_config_contents([{"content": "x" * (1024 * 1024 + 1)}])
        with self.assertRaises(ValueError):
            validate_config_contents([{"destination": "key.pem", "content": "-----BEGIN PRIVATE KEY-----"}])

    def test_binary_source_bytes_digest_bound_without_fixed_config_limit(self):
        def source(raw):
            return {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
                    "sha256": hashlib.sha256(raw).hexdigest()}
        self.assertTrue(validate_config_contents([source(b"PK\x00\xff" * (1024 * 1024))]))
        self.assertTrue(validate_config_contents([source(b"\x00password=example\xff")]))
        self.assertTrue(validate_config_contents([source(b"x" * (8 * 1024 * 1024 + 1))]))
        with self.assertRaises(ValueError):
            validate_config_contents([source(b"PRIVATE KEY-----")])
        with self.assertRaises(ValueError):
            validate_config_contents([dict(source(b"data"), sha256="0" * 64)])
        with self.assertRaises(ValueError):
            validate_config_contents([{"content": "!invalid", "encoding": "base64"}])

    @unittest.skipUnless(os.environ.get("PLATFORM_QA_CONFIG_INVENTORY"), "requires explicitly selected SSH QA target")
    def test_native_source_delivery_and_repeat(self):
        import yaml
        tasks = ROOT / "ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks"
        with tempfile.TemporaryDirectory(prefix="sdku-source-file-") as temporary:
            source = Path(temporary) / "mock.jar"
            raw = b"PK\x00\xff" * (1024 * 1024)
            source.write_bytes(raw)
            destination = temporary + "-target"
            materialize = yaml.safe_load((tasks / "apply_instance.yml").read_text())[:3]
            play = [{"hosts": "config_qa", "gather_facts": False, "vars": {
                "application_config": {"path": str(source), "destination": "lib/mock.jar", "mode": "0644"},
                "application_config_contents": [], "application_runtime_job": {
                    "instancePath": destination, "account": "platform-automation", "projectId": "qa",
                    "libraryId": "qa", "instanceId": "mock", "configContents": "{{ application_config_contents }}"}},
                "tasks": [{"include_tasks": str(tasks / "source_config.yml")},
                          {"assert": {"that": "application_config_contents | platform.core.application_validate_configs"}}]
                         + materialize + [{"stat": {"path": destination + "/config/lib/mock.jar", "checksum_algorithm": "sha256"}, "register": "actual"},
                           {"assert": {"that": "actual.stat.checksum == '" + hashlib.sha256(raw).hexdigest() + "'"}}],
                "post_tasks": [{"file": {"path": destination, "state": "absent"}, "when": "qa_cleanup | default(false) | bool"}]}]
            filename = Path(temporary) / "test.json"
            filename.write_text(json.dumps(play))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATHS=str(ROOT / "ansible-core/collections"))
            for repeat in (False, True):
                command = ["ansible-playbook", "-i", os.environ["PLATFORM_QA_CONFIG_INVENTORY"], str(filename)]
                result = subprocess.run(command, env=env, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout[-4000:] + result.stderr[-1000:])
                if repeat:
                    self.assertIn("changed=0", result.stdout)
            cleanup = subprocess.run(command + ["-e", "qa_cleanup=true"], env=env, capture_output=True, text=True)
            self.assertEqual(0, cleanup.returncode, cleanup.stdout[-1000:])

    def test_compose_checks_core_projection_but_allows_user_fields_and_bind_address(self):
        job = {"instanceId": "api-sdku", "projectId": "project", "libraryId": "sdku", "hostId": "node1",
               "placement": {"composeProject": "project-sdku-api-node1", "containerName": "project-api-node1"},
               "authority": {"requirement": {"localReference": "probe:locked"}},
               "settings": {"image": "probe:locked", "command": ["/usr/bin/probe"], "ports": {"http": {"published": 28180, "container": 8080}},
                            "environment": {"CORE_OPTION": "resolved"}},
               "identityNames": ["EVO_MANAGER_APP_ID"], "configs": []}
        service = {"image": "probe:locked", "container_name": "project-api-node1", "command": ["/usr/bin/probe"],
                   "labels": {"platform.installer.project": "project", "platform.installer.library": "sdku",
                              "platform.installer.instance": "api-sdku", "platform.installer.host": "node1",
                              "platform.installer.config-digest": "c" * 64, "user-label": "allowed"},
                   "environment": {"CORE_OPTION": "resolved", "EVO_MANAGER_APP_ID": "api-sdku", "CUSTOM_OPTION": "user-value"},
                   "ports": [{"host_ip": "127.0.0.1", "published": "28180", "target": 8080, "protocol": "tcp"}],
                   "logging": {"driver": "local"}}
        config = {"name": "project-sdku-api-node1", "services": {"api-sdku": service},
                  "volumes": {"user-data": {"driver": "local"}}, "x-user-extension": {"custom": True}}
        self.assertTrue(validate_compose(config, dict(job, configs=[]), "/private/api", "c" * 64))
        digest_job = dict(job, settings=dict(job["settings"], image="registry.example/probe@" + DIGEST))
        self.assertTrue(validate_compose(config, digest_job, "/private/api", "c" * 64))
        tagged_job = dict(job, settings=dict(job["settings"], image="registry.example/probe:SNAPSHOT"))
        tagged_config = dict(config, services={"api-sdku": dict(service, image="registry.example/probe:SNAPSHOT")})
        self.assertTrue(validate_compose(tagged_config, tagged_job, "/private/api", "c" * 64))
        service["ports"][0]["host_ip"] = "0.0.0.0"
        self.assertTrue(validate_compose(config, dict(job, configs=[]), "/private/api", "c" * 64))
        changed = dict(service, image="unlocked:latest")
        with self.assertRaisesRegex(ValueError, "APPLICATION_COMPOSE_IDENTITY_INVALID"):
            validate_compose(dict(config, services={"api-sdku": changed}), dict(job, configs=[]), "/private/api", "c" * 64)
        changed = dict(service, ports=[{"published": "28181", "target": 8080}])
        with self.assertRaisesRegex(ValueError, "APPLICATION_COMPOSE_PORT_INVALID"):
            validate_compose(dict(config, services={"api-sdku": changed}), dict(job, configs=[]), "/private/api", "c" * 64)

if __name__ == "__main__":
    unittest.main()

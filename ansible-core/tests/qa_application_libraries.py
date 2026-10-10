"""Real target-free Ansible acceptance; run only on the Execution Node."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FIXTURE = os.path.join(REPO, "examples/valid/application-libraries")


class StandaloneLibrariesQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a1-standalone-")
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "project")
        shutil.copytree(FIXTURE, self.root)
        self.vars = os.path.join(self.root, "inventory/group_vars/all/platform-installer.yml")
        self.defaults = os.path.join(self.root, "application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml")

    def edit(self, path, mutate):
        with open(path) as stream:
            data = json.load(stream)
        mutate(data)
        with open(path, "w") as stream:
            json.dump(data, stream, sort_keys=True)

    def snapshot(self):
        output = os.path.join(self.tmp.name, "snapshot.json")
        env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, "ansible-core/ansible.cfg"),
                   ANSIBLE_COLLECTIONS_PATH=os.path.join(REPO, "ansible-core/collections"),
                   ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json",
                   PLATFORM_PROJECT_SNAPSHOT_OUTPUT=output)
        command = ["ansible-playbook", "-i", os.path.join(self.root, "inventory/hosts.yml"),
                   os.path.join(REPO, "ansible-core/playbooks/project-snapshot-machine.yml"),
                   "-e", "platform_project_root=" + self.root,
                   "-e", "platform_service_catalog_path=" + os.path.join(REPO, "examples/catalog/service-catalog.yml")]
        completed = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        # Don't include raw Ansible output in assertion errors.
        self.assertEqual(0, completed.returncode, "Standalone Ansible failed; inspect protected temporary output")
        self.assertNotIn(b"changed=1", completed.stdout)
        with open(output) as stream:
            return json.load(stream)

    def test_two_libraries_multihost_and_parameter_isolation(self):
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"], [(f["code"], f.get("field")) for f in snapshot["findings"]])
        libraries = snapshot["applicationLibraries"]["libraries"]
        sdku = libraries["sdku"]["instances"]["apigateway-sdku"]
        cspa = libraries["cspa"]["instances"]["apigateway-cspa"]
        self.assertEqual({"node1", "node2"}, set(sdku["placements"]))
        self.assertEqual("DEBUG", sdku["placements"]["node1"]["parameters"]["log_level"])
        self.assertEqual("TRACE", sdku["placements"]["node2"]["parameters"]["log_level"])
        self.assertEqual("WARN", cspa["placements"]["node1"]["parameters"]["log_level"])
        self.assertEqual("test-user", sdku["credentialRequirements"]["redis"]["credentials"]["username"]["source"]["value"])
        self.assertEqual("sdku-redis-password", sdku["credentialRequirements"]["redis"]["credentials"]["password"]["source"]["ref"])
        self.assertEqual("postgres-sdku", sdku["connections"]["postgres"]["deploymentRef"])
        self.assertEqual("postgres-cspa", cspa["connections"]["postgres"]["deploymentRef"])
        self.assertEqual("node2", sdku["placements"]["node2"]["SERVER_ID"])
        self.assertEqual("project-sdku-apigateway-sdku-node1", sdku["placements"]["node1"]["composeProject"])
        self.assertEqual("CLIENT_SSL", sdku["connections"]["kafka"]["connectionRef"])
        self.assertTrue(sdku["agentRequired"])
        self.assertEqual({"account": "redis", "field": "password"}, sdku["secretBindings"]["REDIS_PASSWORD"]["source"])
        self.assertEqual({"library_secret": "java_keystore_password"}, sdku["secretBindings"]["JAVA_KEYSTORE_PASSWORD"]["source"])
        self.assertEqual(snapshot["snapshotFingerprint"], self.snapshot()["snapshotFingerprint"])

    def test_dotted_project_id_blocks_compose_projection(self):
        dotted_root = os.path.join(self.tmp.name, "project.test")
        os.rename(self.root, dotted_root)
        self.root = dotted_root
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_COMPOSE_PROJECT_INVALID", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_infrastructure_only_without_library_selection(self):
        def infrastructure(data):
            data.pop("platform_desired_state_contract")
            data["platform_desired_state"].pop("applicationLibraryDeployments")
        self.edit(self.vars, infrastructure)
        for host in ("node1", "node2"):
            self.edit(os.path.join(self.root, "inventory/host_vars", host, "platform-installer.yml"), lambda data: data.pop("platform_application_libraries"))
        shutil.rmtree(os.path.join(self.root, "application-packages"))
        shutil.rmtree(os.path.join(self.root, "library-packages"))
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        self.assertEqual("platform.installer/project-snapshot/v1alpha1", snapshot["apiVersion"])
        self.assertNotIn("applicationLibraries", snapshot)

    def test_no_accounts_no_agent_or_credentials(self):
        def no_secrets(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults.pop("provisioner")
        self.edit(self.defaults, no_secrets)
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        instance = snapshot["applicationLibraries"]["libraries"]["sdku"]["instances"]["apigateway-sdku"]
        self.assertFalse(instance["agentRequired"])
        self.assertEqual({}, instance["credentialRequirements"])
        self.assertIsNone(instance["approle"])

    def test_shared_only_requires_agent_without_account_hooks(self):
        def shared_only(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            bindings = defaults["provisioner"]["secret_bindings"]
            defaults["provisioner"]["secret_bindings"] = {"JAVA_KEYSTORE_PASSWORD": bindings["JAVA_KEYSTORE_PASSWORD"]}
        self.edit(self.defaults, shared_only)
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        for library in snapshot["applicationLibraries"]["libraries"].values():
            for instance in library["instances"].values():
                self.assertTrue(instance["agentRequired"])
                self.assertEqual({}, instance["credentialRequirements"])
                self.assertIsNotNone(instance["approle"])
                self.assertIn("A4_PROVIDER_PROVISIONING", instance["executionPrerequisites"])
                self.assertEqual({"JAVA_KEYSTORE_PASSWORD"}, set(instance["secretBindings"]))
            self.assertEqual({"java_keystore_password"}, set(library["sharedSecretRequirements"]))

    def test_ambiguous_secret_binding_blocks(self):
        self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["provisioner"]["secret_bindings"]["REDIS_PASSWORD"]["source"].update(library_secret="java_keystore_password"))
        snapshot = self.snapshot()
        self.assertNotEqual("PASS", snapshot["status"])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_unknown_shared_secret_blocks(self):
        self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["provisioner"]["secret_bindings"]["JAVA_KEYSTORE_PASSWORD"].update(source={"library_secret": "unknown"}))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_SECRET_BINDING_INVALID", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_shared_only_requires_vault_ref(self):
        def shared_only(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults["provisioner"]["secret_bindings"] = {"JAVA_KEYSTORE_PASSWORD": {"source": {"library_secret": "java_keystore_password"}}}
        self.edit(self.defaults, shared_only)
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["bindings"].pop("secrets"))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_VAULT_REQUIRED", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_missing_service_ref_skips_unused_hook(self):
        def no_accounts(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults.pop("provisioner")
        self.edit(self.defaults, no_accounts)
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["bindings"].pop("cache"))
        instance = self.snapshot()["applicationLibraries"]["libraries"]["sdku"]["instances"]["apigateway-sdku"]
        self.assertNotIn("redis", instance["connections"])

    def test_same_host_port_collision_blocks(self):
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["cspa"]["applications"]["gateway"]["overrides"]["ports"]["http"].update(published=18081))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_PORT_COLLISION", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_missing_kafka_selector_blocks(self):
        for library in ("sdku", "cspa"):
            path = os.path.join(self.root, "library-packages", library, "1.0.0/roles/library_" + library + "/defaults/main.yml")
            self.edit(path, lambda data: data["platform_library_definition"].pop("connection_defaults"))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_CONNECTION_INVALID", [f["code"] for f in snapshot["findings"]])

    def test_validate_entrypoint_consumes_shared_projection(self):
        output = os.path.join(self.tmp.name, "validation.json")
        env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, "ansible-core/ansible.cfg"),
                   ANSIBLE_COLLECTIONS_PATH=os.path.join(REPO, "ansible-core/collections"))
        completed = subprocess.run(["ansible-playbook", "-i", os.path.join(self.root, "inventory/hosts.yml"),
                                    os.path.join(REPO, "ansible-core/playbooks/validate.yml"),
                                    "-e", "platform_project_root=" + self.root,
                                    "-e", "platform_service_catalog_path=" + os.path.join(REPO, "examples/catalog/service-catalog.yml"),
                                    "-e", "platform_validation_artifact=" + output],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(0, completed.returncode, "Standalone validation failed")
        with open(output) as stream:
            self.assertEqual("PASS", json.load(stream)["status"])

    def test_plaintext_never_returned_in_projection(self):
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"]["parameters"].update(password="DO-NOT-PRINT"))
        snapshot = self.snapshot()
        self.assertNotIn("DO-NOT-PRINT", json.dumps(snapshot))
        self.assertIn("APPLICATION_PLAINTEXT_FORBIDDEN", [f["code"] for f in snapshot["findings"]])

    def test_free_resources_grants_endpoint_never_leak_secrets(self):
        with open(self.vars) as stream:
            original_vars = json.load(stream)
        with open(self.defaults) as stream:
            original_defaults = json.load(stream)
        for section in ("resources", "grants", "endpoint"):
            with self.subTest(section=section):
                with open(self.vars, "w") as stream:
                    json.dump(original_vars, stream)
                with open(self.defaults, "w") as stream:
                    json.dump(original_defaults, stream)
                if section == "resources":
                    self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["resources"]["applicationDatabase"]["parameters"].update(password="DO-NOT-PRINT"))
                elif section == "grants":
                    self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["accounts"]["redis"].update(grants=[{"token": "DO-NOT-PRINT"}]))
                else:
                    self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"].update(endpoint={"enabled": False, "haproxy": {"password": "DO-NOT-PRINT"}}))
                snapshot = self.snapshot()
                self.assertNotIn("DO-NOT-PRINT", json.dumps(snapshot))
                self.assertEqual("BLOCKED", snapshot["applicationLibraries"]["status"])
                self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])



if __name__ == "__main__":
    unittest.main()

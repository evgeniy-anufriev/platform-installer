"""Real Ansible process boundaries for PKI single-pass resolution.

Only synthetic local hosts and temporary roots are used. No Vault, system
services, credentials, privilege escalation or installed PKI are touched.
The standalone boundary test deliberately stops at the missing-secret guard;
it proves real mutation/include execution without issuing certificates.
"""

import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

if os.name == "posix":
    import grp
    import pwd


CORE = Path(__file__).resolve().parents[1]
TAG = "platform_installer_pki_materialization"
ROLE = "platform.core.pki_materialize"
MATCH_TASK = "Require fresh resolution to match the previously applied frozen PKI plans"


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class PKISinglePassResolutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pki-single-pass-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sequence = 0
        self.desired = {
            "certificateAuthorities": {"qa-ca": {"mode": "MANAGED", "commonName": "QA CA"}},
            "certificateProfiles": {"qa-cert": {"authorityRef": "qa-ca"}},
            "tlsProfiles": {"qa-tls": {
                "certificateProfileRef": "qa-cert", "scope": "DEPLOYMENT",
                "storePasswordSecretRef": "runtime:qa-missing-password",
            }},
            "serviceDeployments": {
                "alpha": {"serviceType": "kafka", "configuration": {"tlsProfile": "qa-tls"}},
                "bravo": {"serviceType": "kafka", "configuration": {"tlsProfile": "qa-tls"}},
            },
        }
        self.variables = {
            "platform_project_id": "single-pass-qa",
            "platform_pki_resolve_managed": True,
            "platform_pki_project_path": str(self.root / "absent-project.yml"),
            "platform_pki_inventory_path": str(self.root / "hosts.json"),
            "platform_desired_state": self.desired,
            "platform_pki_target_root": str(self.root / "pki-target"),
            "platform_pki_state_root": str(self.root / "pki-state"),
            "platform_pki_runtime_root": str(self.root / "pki-runtime"),
            "platform_pki_owner": pwd.getpwuid(os.getuid()).pw_name,
            "platform_pki_group": grp.getgrgid(os.getgid()).gr_name,
            "platform_pki_secret_files": {},
            "ansible_become": False,
        }
        local = {"ansible_connection": "local", "ansible_host": "127.0.0.1",
                 "ansible_python_interpreter": sys.executable}
        self.inventory = self.write_json("hosts.json", {"all": {
            "hosts": {"localhost": local},
            "children": {"platform_targets": {"hosts": {
                "qa-a": dict(local, platform_deployments={
                    "alpha": {"members": {"alpha-a": {"roles": ["server"]}}},
                    "bravo": {"members": {"bravo-a": {"roles": ["server"]}}},
                }),
                "qa-b": dict(local, platform_deployments={
                    "alpha": {"members": {"alpha-b": {"roles": ["server"]}}},
                }),
            }}},
        }})
        config = self.root / "ansible.cfg"
        config.write_text(
            "[defaults]\ncollections_path = " + str(CORE / "collections") +
            "\nretry_files_enabled = False\nhash_behaviour = merge\n"
            "fact_caching = memory\nstdout_callback = default\n"
            "forks = 1\n[privilege_escalation]\nbecome = False\n", encoding="utf-8")
        # Inherited tags, inventory, callbacks and persistent fact caches must
        # not silently turn these assertions into skipped tasks or remote work.
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith("ANSIBLE_")}
        self.environment.update({"ANSIBLE_CONFIG": str(config), "ANSIBLE_NOCOLOR": "1",
                                 "ANSIBLE_LOCAL_TEMP": str(self.root / "local-tmp"),
                                 "ANSIBLE_REMOTE_TEMP": str(self.root / "remote-tmp")})

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    @staticmethod
    def role(tasks_from=None):
        definition = {"name": ROLE}
        if tasks_from:
            definition["tasks_from"] = tasks_from
        return {"ansible.builtin.include_role": definition}

    @staticmethod
    def play(tasks, hosts="localhost"):
        return {"hosts": hosts, "connection": "local", "gather_facts": False,
                "become": False, "tasks": tasks}

    def run_play(self, plays, *, skip=False, extra=None, success=True):
        self.sequence += 1
        variables = copy.deepcopy(self.variables)
        variables.update(extra or {})
        variable_file = self.write_json(f"vars-{self.sequence}.json", variables)
        playbook = self.write_json(f"play-{self.sequence}.json", plays)
        command = [shutil.which("ansible-playbook"), "-i", str(self.inventory),
                   "--forks", "1", "--timeout", "10", "-e", "@" + str(variable_file), str(playbook)]
        if skip:
            command += ["--skip-tags", TAG]
        result = subprocess.run(command, cwd=self.root, env=self.environment,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                # Real PEM/PKCS12 materialization includes multiple
                                # Ansible process/module and keytool invocations.
                                timeout=180, check=False)
        if success:
            self.assertEqual(0, result.returncode, result.stdout[-12000:])
        else:
            self.assertNotEqual(0, result.returncode, result.stdout[-12000:])
        return result.stdout

    def resolve_in_fresh_process(self):
        """Export only the ordinary derived projection, never cached facts."""
        projection = self.root / "projection.json"
        self.run_play([self.play([
            self.role("resolve.yml"),
            {"ansible.builtin.copy": {"dest": str(projection), "mode": "0600",
                                      "content": "{{ platform_pki_managed_resolution.pki | to_json }}"}},
        ])])
        resolved = json.loads(projection.read_text(encoding="utf-8"))
        self.assertEqual("PASS", resolved["status"])
        return resolved

    def assert_no_pki_mutation(self):
        for name in ("pki-state", "pki-runtime", "pki-target", "service-mutation"):
            self.assertFalse((self.root / name).exists(), name)

    def mutation_marker(self):
        return {"ansible.builtin.file": {"path": str(self.root / "service-mutation"), "state": "touch"}}

    def test_new_process_publishes_requests_and_selects_exact_consumer(self):
        resolved = self.resolve_in_fresh_process()
        self.assertEqual(2, len(resolved["requests"]))
        self.assertEqual(3, len(resolved["materializationPlans"]))
        ids = [request["id"] for request in resolved["requests"]]
        wanted = next(request["id"] for request in resolved["requests"]
                      if any(consumer["deploymentId"] == "bravo"
                             for consumer in request["consumers"]))
        expected = next(plan for plan in resolved["materializationPlans"]
                        if plan["requestId"] == wanted and plan["hostId"] == "qa-a")
        output = self.run_play([
            self.play([
                {"ansible.builtin.assert": {"that": ["platform_pki_requests is not defined"]}},
                self.role(),
                {"ansible.builtin.assert": {"that": [
                    "platform_pki_requests | map(attribute='id') | sort | list == expected_ids | sort",
                    "platform_pki_material_changed is not defined",
                ]}},
            ]),
            self.play([
                self.role("select_consumer_plan.yml"),
                {"ansible.builtin.assert": {"that": [
                    "platform_pki_selected_consumer_plan == expected_plan",
                    "hostvars['localhost'].platform_pki_requests | length == 2",
                ]}},
            ], hosts="qa-a"),
        ], skip=True, extra={"platform_pki_materialization_plans": list(reversed(resolved["materializationPlans"])),
                             "platform_pki_consumer_tls_profile_id": "qa-tls",
                             "platform_execution_service_deployment": "bravo",
                             "expected_ids": ids, "expected_plan": expected})
        self.assertIn(MATCH_TASK, output)
        self.assertNotIn("Derive request-owned PKI paths", output)
        self.assertRegex(output, r"localhost\s+:.*changed=0.*failed=0")
        self.assertRegex(output, r"qa-a\s+:.*changed=0.*failed=0")
        self.assert_no_pki_mutation()

    def test_frozen_extra_vars_mismatch_fails_before_any_mutation(self):
        resolved = self.resolve_in_fresh_process()
        # Same IDs and fingerprints: complete plan equality must still catch
        # drift in another field, despite extra-vars shadowing set_fact.
        frozen = copy.deepcopy(resolved["materializationPlans"])
        frozen[0]["targetDirectory"] += "-tampered"
        output = self.run_play([self.play([self.role(), self.mutation_marker()])],
                               skip=True, success=False,
                               extra={"platform_pki_materialization_plans": frozen})
        self.assertRegex(output, re.escape(MATCH_TASK) + r"[^\n]*\n[^\n]*fatal:")
        self.assertNotIn("Prepare protected PKI execution roots", output)
        self.assert_no_pki_mutation()

    def test_default_managed_mode_remains_valid_after_requests_are_published(self):
        # Production relies on the role default, which is an expression over
        # request count. It becomes false after successful resolution.
        self.variables.pop("platform_pki_resolve_managed")
        resolved = self.resolve_in_fresh_process()
        output = self.run_play([self.play([
            self.role(),
            {"ansible.builtin.assert": {"that": [
                "platform_pki_requests | length == 2",
            ]}},
        ])], skip=True, extra={
            "platform_pki_materialization_plans": resolved["materializationPlans"],
        })
        self.assertIn(MATCH_TASK, output)
        self.assert_no_pki_mutation()

    def test_runtime_assert_remains_active_under_skip(self):
        resolved = self.resolve_in_fresh_process()
        output = self.run_play([self.play([self.role(), self.mutation_marker()])],
                               skip=True, success=False, extra={
                                   "platform_pki_materialization_plans": resolved["materializationPlans"],
                                   "platform_pki_reissue_request_ids": ["not-a-resolved-request"],
                               })
        self.assertIn("PKI_MATERIALIZATION_RUNTIME_INVALID", output)
        self.assert_no_pki_mutation()

    def test_missing_consumer_fails_before_service_mutation(self):
        resolved = self.resolve_in_fresh_process()
        output = self.run_play([
            self.play([self.role()]),
            self.play([self.role("select_consumer_plan.yml"), self.mutation_marker()], hosts="qa-a"),
        ], skip=True, success=False, extra={
            "platform_pki_materialization_plans": resolved["materializationPlans"],
            "platform_pki_consumer_tls_profile_id": "qa-tls",
            "platform_execution_service_deployment": "missing-deployment",
        })
        self.assertIn("PKI_CONSUMER_PLAN_REQUIRED", output)
        self.assert_no_pki_mutation()

    def test_skip_keeps_deploy_integrity_guard_for_missing_source(self):
        resolved = self.resolve_in_fresh_process()
        output = self.run_play([
            self.play([self.role()]),
            self.play([{"ansible.builtin.include_role": {"name": "platform.core.pki_deploy"}},
                       self.mutation_marker()], hosts="qa-a"),
        ], skip=True, success=False,
            extra={"platform_pki_materialization_plans": resolved["materializationPlans"]})
        self.assertIn("Require readable regular source PKI material", output)
        self.assertIn("fatal:", output)
        self.assertNotIn("Deploy target-owned PKI material atomically", output)
        self.assert_no_pki_mutation()

    def test_skip_reuses_matching_target_and_repairs_corrupt_target(self):
        """Real Ansible repeat does not redeploy matching PKI, but repairs drift."""
        resolved = self.resolve_in_fresh_process()
        plan = next(item for item in resolved["materializationPlans"]
                    if item["hostId"] == "qa-a")
        state = self.root / "pki-state" / "single-pass-qa"
        for source in (
            f"authorities/{plan['authorityId']}/ca.crt",
            f"requests/{plan['requestId']}/leaf.crt",
            f"requests/{plan['requestId']}/leaf.key",
            f"requests/{plan['requestId']}/keystore.p12",
            f"requests/{plan['requestId']}/truststore.p12",
        ):
            file = state / source
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"synthetic PKI material for integrity test")
        deploy = self.play([{"ansible.builtin.include_role": {"name": "platform.core.pki_deploy"}}], hosts="qa-a")
        variables = {"platform_pki_materialization_plans": [plan],
                     "platform_pki_project_id": "single-pass-qa"}
        first = self.run_play([deploy], extra=variables)
        self.assertIn("Record non-secret target materialization fingerprint", first)
        second = self.run_play([deploy], skip=True, extra=variables)
        self.assertRegex(second, r"qa-a\s+:.*changed=0.*failed=0")
        self.assertRegex(second, r"Repair PKI material that does not match the applied plan[^\n]*\n[^\n]*skipping:")
        target = Path(plan["targetDirectory"]) / "certificate.pem"
        target.write_bytes(b"tampered target")
        third = self.run_play([deploy], skip=True, extra=variables)
        self.assertIn("Deploy immutable PEM and Java PKI material", third)
        self.assertRegex(third, r"qa-a\s+:.*changed=[1-9][0-9]*.*failed=0")
        self.assertEqual(b"synthetic PKI material for integrity test", target.read_bytes())
        for drift in ("missing", "mode", "fingerprint"):
            with self.subTest(drift=drift):
                if drift == "missing":
                    target.unlink()
                elif drift == "mode":
                    target.chmod(0o600)
                else:
                    (target.parent / "materialization-fingerprint").write_text("stale\n")
                repaired = self.run_play([deploy], skip=True, extra=variables)
                self.assertRegex(repaired, r"qa-a\s+:.*changed=[1-9][0-9]*.*failed=0")
                self.assertEqual(b"synthetic PKI material for integrity test", target.read_bytes())
                self.assertEqual(0o644, target.stat().st_mode & 0o777)
                clean = self.run_play([deploy], skip=True, extra=variables)
                self.assertRegex(clean, r"qa-a\s+:.*changed=0.*failed=0")

    def test_standalone_without_skip_enters_real_mutation_and_request_include(self):
        output = self.run_play([self.play([self.role(), self.mutation_marker()])], success=False)
        self.assertIn("Derive request-owned PKI paths", output)
        self.assertRegex(output, r"Require runtime-only store password reference[^\n]*\n[^\n]*fatal:")
        state = self.root / "pki-state" / "single-pass-qa"
        self.assertTrue((state / "authorities").is_dir())
        self.assertTrue((state / "requests").is_dir())
        self.assertTrue((self.root / "pki-runtime").is_dir())
        self.assertEqual([], list(state.rglob("*.*")))
        self.assertFalse((self.root / "service-mutation").exists())

    def _pki_store_apply(self, password, *, success=True, reissue_ids=None):
        password_file = self.root / "runtime-password"
        password_file.write_text(password, encoding="utf-8")
        password_file.chmod(0o600)
        variables = {
            "platform_pki_secret_files": {"runtime:qa-missing-password": str(password_file)},
            "platform_pki_state_root": str(self.root / "pki-state"),
            "platform_pki_runtime_root": str(self.root / "pki-runtime"),
            "platform_pki_target_root": str(self.root / "pki-target"),
        }
        if reissue_ids is not None:
            variables["platform_pki_reissue_request_ids"] = reissue_ids
        output = self.run_play([self.play([self.role()])], extra=variables, success=success)
        self.assertNotIn(password, output)
        return output

    def test_changed_request_reissues_once_and_stale_recovery_only_finalizes(self):
        self.desired["certificateProfiles"]["qa-cert"]["usages"] = ["serverAuth"]
        self._pki_store_apply("qa-reissue-store-password")
        state = self.root / "pki-state" / "single-pass-qa"
        old_certificates = {path.parent.name: path.read_bytes()
                            for path in (state / "requests").glob("*/leaf.crt")}
        self.desired["certificateProfiles"]["qa-cert"]["usages"] = ["serverAuth", "clientAuth"]
        resolved = self.resolve_in_fresh_process()
        desired = {item["id"]: item["certificateRequestFingerprint"] for item in resolved["requests"]}
        self.assertEqual(set(old_certificates), set(desired))
        blocked = self._pki_store_apply("qa-reissue-store-password", success=False)
        self.assertIn("CERTIFICATE_REISSUE_REQUIRED", blocked)
        for request_id, old in old_certificates.items():
            self.assertEqual(old, (state / "requests" / request_id / "leaf.crt").read_bytes())

        self._pki_store_apply("qa-reissue-store-password", reissue_ids=sorted(desired))
        for request_id, old in old_certificates.items():
            request = state / "requests" / request_id
            self.assertNotEqual(old, (request / "leaf.crt").read_bytes())
            self.assertEqual(desired[request_id], (request / "request-fingerprint").read_text(encoding="ascii").strip())
            self.assertFalse((state / "reissues" / (request_id + ".fingerprint")).exists())
        repeated = self._pki_store_apply("qa-reissue-store-password")
        self.assertRegex(repeated, r"localhost\s+:.*changed=0.*failed=0")

        request_id = sorted(desired)[0]
        recovery = state / "reissues" / (request_id + ".fingerprint")
        recovery.write_text(desired[request_id] + "\n", encoding="ascii")
        recovery.chmod(0o600)
        current = (state / "requests" / request_id / "leaf.crt").read_bytes()
        self._pki_store_apply("qa-reissue-store-password", reissue_ids=[request_id])
        self.assertFalse(recovery.exists())
        self.assertEqual(current, (state / "requests" / request_id / "leaf.crt").read_bytes())

    def test_changed_authority_blocks_reissue_without_deleting_prior_material(self):
        self._pki_store_apply("qa-authority-change-password")
        request, authority = self._pki_request_material_paths()
        prior = {name: (request / name).read_bytes() for name in
                 ("leaf.key", "leaf.crt", "request-fingerprint", "keystore.p12", "truststore.p12")}
        prior_ca = (authority / "authority-fingerprint").read_bytes()
        self.desired["certificateProfiles"]["qa-cert"]["usages"] = ["serverAuth", "clientAuth"]
        self.desired["certificateAuthorities"]["qa-ca"]["validityDays"] = 3651
        selected = [item["id"] for item in self.resolve_in_fresh_process()["requests"]]
        blocked = self._pki_store_apply("qa-authority-change-password", success=False, reissue_ids=selected)
        self.assertIn("CERTIFICATE_REISSUE_REQUIRED", blocked)
        self.assertEqual(prior_ca, (authority / "authority-fingerprint").read_bytes())
        for name, content in prior.items():
            self.assertEqual(content, (request / name).read_bytes())

    def test_changed_request_with_missing_derived_store_reissues(self):
        self._pki_store_apply("qa-missing-store-password")
        request, _ = self._pki_request_material_paths()
        old_cert = (request / "leaf.crt").read_bytes()
        (request / "truststore.p12").unlink()
        self.desired["certificateProfiles"]["qa-cert"]["usages"] = ["serverAuth", "clientAuth"]
        selected = [item["id"] for item in self.resolve_in_fresh_process()["requests"]]
        self._pki_store_apply("qa-missing-store-password", reissue_ids=selected)
        self.assertTrue((request / "truststore.p12").is_file())
        self.assertNotEqual(old_cert, (request / "leaf.crt").read_bytes())

    def _pki_request_material_paths(self):
        state = self.root / "pki-state" / "single-pass-qa"
        requests = sorted((state / "requests").iterdir())
        self.assertGreaterEqual(len(requests), 1)
        request = requests[0]
        authority = next((state / "authorities").iterdir())
        return request, authority

    def test_store_password_rotation_preserves_pem_identity_and_repeat_is_clean(self):
        self._pki_store_apply("qa-initial-store-password")
        request, authority = self._pki_request_material_paths()
        unchanged = self._pki_store_apply("qa-initial-store-password")
        self.assertRegex(unchanged, r"localhost\s+:.*changed=0.*failed=0")
        authoritative = {
            path.name: path.read_bytes()
            for path in (request / "leaf.key", request / "leaf.crt",
                         request / "request-fingerprint", authority / "ca.crt")
        }

        changed = self._pki_store_apply("qa-replacement-store-password")
        self.assertRegex(changed, r"localhost\s+:.*changed=[1-9][0-9]*.*failed=0")
        for name, content in authoritative.items():
            path = authority / name if name == "ca.crt" else request / name
            self.assertEqual(content, path.read_bytes(), name)
        self.assertTrue((request / "keystore.p12").is_file())
        self.assertTrue((request / "truststore.p12").is_file())

        repeated = self._pki_store_apply("qa-replacement-store-password")
        self.assertRegex(repeated, r"localhost\s+:.*changed=0.*failed=0")
        old_password_file = self.root / "old-password"
        old_password_file.write_text("qa-initial-store-password", encoding="utf-8")
        old_password_file.chmod(0o600)
        old_password_check = subprocess.run([
            shutil.which("keytool"), "-list", "-storetype", "PKCS12",
            "-keystore", str(request / "keystore.p12"), "-storepass:file", str(old_password_file),
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        self.assertNotEqual(0, old_password_check.returncode)

    def test_missing_or_mixed_password_store_repairs_the_complete_pair(self):
        self._pki_store_apply("qa-original-store-password")
        request, authority = self._pki_request_material_paths()
        # Model the durable state left by interruption between the two atomic
        # replacements: one store uses the new password, the other the old.
        password_file = self.root / "replacement-password"
        password_file.write_text("qa-next-store-password", encoding="utf-8")
        password_file.chmod(0o600)
        (self.root / "replacement-truststore.p12").unlink(missing_ok=True)
        trust_alias = self.resolve_in_fresh_process()["materializationPlans"][0]["trustAlias"]
        subprocess.run([
            shutil.which("keytool"), "-importcert", "-noprompt", "-storetype", "PKCS12",
            "-alias", trust_alias, "-file", str(authority / "ca.crt"),
            "-keystore", str(self.root / "replacement-truststore.p12"),
            "-storepass:file", str(password_file),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (self.root / "replacement-truststore.p12").chmod(0o600)
        (self.root / "replacement-truststore.p12").replace(request / "truststore.p12")
        chain = subprocess.run([
            shutil.which("openssl"), "verify", "-CAfile", str(authority / "ca.crt"),
            str(request / "leaf.crt"),
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        self.assertEqual(0, chain.returncode, "synthetic authoritative PEM fixture must remain valid")

        healed = self._pki_store_apply("qa-next-store-password")
        self.assertRegex(healed, r"localhost\s+:.*changed=[1-9][0-9]*.*failed=0")
        repeated = self._pki_store_apply("qa-next-store-password")
        self.assertRegex(repeated, r"localhost\s+:.*changed=0.*failed=0")
        (request / "truststore.p12").unlink()
        repaired = self._pki_store_apply("qa-next-store-password")
        self.assertRegex(repaired, r"localhost\s+:.*changed=[1-9][0-9]*.*failed=0")
        for filename in ("keystore.p12", "truststore.p12"):
            check = subprocess.run([
                shutil.which("keytool"), "-list", "-storetype", "PKCS12",
                "-keystore", str(request / filename), "-storepass:file", str(self.root / "runtime-password"),
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            self.assertEqual(0, check.returncode, filename)

    def test_invalid_authoritative_pem_blocks_store_replacement(self):
        self._pki_store_apply("qa-before-invalid-pem")
        request, _ = self._pki_request_material_paths()
        stores_before = {name: (request / name).read_bytes()
                         for name in ("keystore.p12", "truststore.p12")}
        (request / "leaf.crt").write_text("not a certificate\n", encoding="ascii")

        output = self._pki_store_apply("qa-after-invalid-pem", success=False)
        self.assertIn("failed=1", output)
        for name, content in stores_before.items():
            self.assertEqual(content, (request / name).read_bytes(), name)

    def test_no_consumers_stays_empty_and_clean_with_and_without_skip(self):
        for skip in (False, True):
            with self.subTest(skip=skip):
                output = self.run_play([self.play([
                    self.role(),
                    {"ansible.builtin.assert": {"that": [
                        "platform_pki_requests == []", "platform_pki_materialization_plans == []",
                    ]}},
                ]), self.play([{"ansible.builtin.include_role": {"name": "platform.core.pki_deploy"}}],
                              hosts="platform_targets")], skip=skip, extra={
                                  "platform_desired_state": {"serviceDeployments": {}},
                                  "platform_pki_materialization_plans": [],
                              })
                self.assertRegex(output, r"localhost\s+:.*changed=0.*failed=0")
                self.assert_no_pki_mutation()

    def test_five_consumers_real_file_change_signals_and_activation_decisions(self):
        """Reuse real tasks; replace only service actions with observations.

        This proves file-change propagation and activation decisions, not a
        running daemon's reload, TLS handshake or full service acceptance.
        """
        import yaml

        roles = {
            "kafka": "kafka_kraft", "redis": "redis_tls", "vault": "vault_tls",
            "postgresql": "postgresql", "haproxy": "haproxy",
        }

        def tasks(service, filename):
            path = (CORE.parent / "services" / service / "ansible_collections" /
                    "platform" / service / "roles" / roles[service] / "tasks" / filename)
            return yaml.safe_load(path.read_text(encoding="utf-8"))

        def named(source, name):
            return copy.deepcopy(next(task for task in source if task.get("name") == name))

        for service in roles:
            with self.subTest(service=service):
                root = self.root / service
                source = root / "source"
                target = root / "member-a" / "pki"
                second = root / "member-b" / "pki"
                for directory in (source, target, second):
                    directory.mkdir(parents=True)
                filenames = ["ca-chain.pem", "certificate.pem", "private-key.pem",
                             "keystore.p12", "truststore.p12", "materialization-fingerprint"]
                for filename in filenames:
                    (source / filename).write_text("synthetic fixture " + filename, encoding="utf-8")
                variables = {
                    "platform_pki_selected_consumer_plan": {"targetDirectory": str(source)},
                    "platform_kafka_verify_only": False,
                    "platform_postgresql_verify_only": False,
                    "platform_redis_mode": "sentinel",
                    "redis_member": {"config_directory": str(target.parent), "roles": ["sentinel"]},
                    "_platform_kafka_tls_runtime": {"targetDirectory": str(source),
                                                    "consumerDirectory": str(target)},
                    "_platform_postgresql_tls_directory": str(target),
                    "platform_haproxy_pki_directory": str(source),
                    "_platform_vault_local_instances": [
                        {"id": "a", "host": "localhost", "instance_name": "qa-a", "config_directory": str(target.parent)},
                        {"id": "b", "host": "localhost", "instance_name": "qa-b", "config_directory": str(second.parent)},
                    ],
                    "_platform_vault_active_units": ["qa-a", "qa-b"],
                }
                for prefix in ("platform_kafka_member_config", "platform_kafka_member_environment",
                               "_platform_redis_config", "_platform_redis_unit",
                               "_platform_redis_acl_config", "_platform_redis_acl_file",
                               "_platform_redis_acl_legacy_password",
                               "_platform_sentinel_config", "_platform_sentinel_unit",
                               "_platform_sentinel_acl_config", "_platform_sentinel_acl_legacy_password"):
                    variables[prefix] = {"changed": False}
                for owner_service in roles:
                    variables[f"platform_{owner_service}_user"] = self.variables["platform_pki_owner"]
                    variables[f"platform_{owner_service}_group"] = self.variables["platform_pki_group"]
                handlers = []
                if service == "kafka":
                    member = tasks(service, "member.yml")
                    listener = tasks(service, "validate_ssl_listener.yml")
                    selected = [named(member, "Initialize Kafka member PKI change signal"),
                                named(listener, "Copy PKI material into Kafka-owned consumer directory"),
                                named(listener, "Aggregate Kafka member PKI change signal")]
                    restart = next(task for task in member
                                   if task.get("ansible.builtin.systemd", {}).get("state") == "restarted")
                    observations = [{"ansible.builtin.set_fact": {"activation": True}, "when": restart["when"]}]
                elif service == "redis":
                    member = tasks(service, "member.yml")
                    selected = [named(member, "Materialize Redis member TLS files")]
                    restarts = [task for task in member
                                if task.get("ansible.builtin.systemd_service", task.get("ansible.builtin.systemd", {})).get("state") == "restarted"]
                    self.assertEqual(2, len(restarts))
                    observations = [{"ansible.builtin.set_fact": {"activation_" + str(index): True},
                                     "when": task["when"]} for index, task in enumerate(restarts)]
                elif service == "vault":
                    provision = tasks(service, "provision.yml")
                    selected = [named(provision, "Initialize this host's exact changed-member restart set"),
                                named(provision, "Materialize the API certificate, private key and CA for each Vault unit"),
                                named(provision, "Record members whose PKI files changed")]
                    state = tasks(service, "bootstrap_follower.yml")[0]["ansible.builtin.systemd_service"]["state"]
                    observations = [{"ansible.builtin.set_fact": {"activation_state": state},
                                     "vars": {"vault_member": variables["_platform_vault_local_instances"][0]}}]
                elif service == "postgresql":
                    selected = [named(tasks(service, "install_tls.yml"),
                                      "Materialize PostgreSQL-owned PEM files from PKI-01 projection")]
                    handlers = [{"name": selected[0]["notify"],
                                 "ansible.builtin.set_fact": {"activation": True}}]
                    observations = [{"ansible.builtin.meta": "flush_handlers"}]
                else:
                    for index, filename in enumerate(filenames[:3], 1):
                        name = {1: "02-ca-chain.pem", 2: "01-certificate.pem", 3: "03-private-key.pem"}[index]
                        (source / name).write_text("synthetic " + filename, encoding="utf-8")
                    prepare = tasks(service, "prepare.yml")
                    selected = [named(prepare, "Build HAProxy PEM bundle atomically without logging key data"),
                                named(prepare, "Record whether HAProxy TLS material changed")]
                    # Only test ownership differs from the production assemble task.
                    selected[0]["ansible.builtin.assemble"].update(
                        owner=self.variables["platform_pki_owner"], group=self.variables["platform_pki_group"])
                    state = named(tasks(service, "start.yml"), "Start or reload validated HAProxy service")["ansible.builtin.systemd_service"]["state"]
                    observations = [{"ansible.builtin.set_fact": {"activation_state": state}}]

                # Fresh processes exclude stale aggregate facts. Corrupt one
                # consumer file after the clean repeat to require activation.
                for phase in range(3):
                    changed = phase != 1
                    if phase == 2:
                        destination = source / "haproxy.pem" if service == "haproxy" else target / "private-key.pem"
                        destination.write_text("synthetic drift", encoding="utf-8")
                    assertions = ["platform_pki_material_changed is not defined"]
                    if service == "vault":
                        expected = ["a", "b"] if phase == 0 else (["a"] if changed else [])
                        assertions += ["_platform_vault_restart_member_ids == " + repr(expected)]
                    if service in ("vault", "haproxy"):
                        assertions += ["activation_state == '" + ("restarted" if changed else "started") + "'"]
                    elif service == "redis":
                        assertions += [f"activation_{index} == {changed}" for index in range(2)]
                    else:
                        assertions += [f"activation == {changed}"]
                    play = self.play([
                        {"ansible.builtin.set_fact": {"activation": False, "activation_0": False, "activation_1": False}},
                        *copy.deepcopy(selected), *copy.deepcopy(observations),
                        {"ansible.builtin.assert": {"that": assertions}},
                    ])
                    play["handlers"] = handlers
                    self.run_play([play], extra=variables, skip=True)


if __name__ == "__main__":
    unittest.main()

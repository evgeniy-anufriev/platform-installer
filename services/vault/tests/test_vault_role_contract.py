from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / "services/vault/ansible_collections/platform/vault/roles/vault_tls"


class VaultRoleContractTests(unittest.TestCase):
    def test_role_and_playbook_yaml_is_parseable(self):
        roots = [ROOT / "services/vault/ansible_collections/platform/vault/roles/vault_tls",
                 ROOT / "services/vault/playbooks"]
        for root in roots:
            for path in sorted(root.rglob("*.yml")):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertIsNotNone(yaml.safe_load(path.read_text(encoding="utf-8")))

    def test_role_serializes_apply_with_target_shared_flock_and_always_release(self):
        main = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        block = next(task["block"] for task in main if task["name"].startswith("Serialize Vault apply"))
        acquire = yaml.safe_load((ROLE / "tasks/acquire_lock.yml").read_text(encoding="utf-8"))
        release = yaml.safe_load((ROLE / "tasks/release_lock.yml").read_text(encoding="utf-8"))
        lock_start = next(task["ansible.builtin.command"]["argv"] for task in acquire
                          if task["name"].startswith("Hold the shared Vault bootstrap lock"))
        self.assertIn("--property=Type=notify", lock_start)
        self.assertIn("--property=NotifyAccess=all", lock_start)
        self.assertIn("--no-fork", lock_start)
        self.assertIn("/usr/bin/systemd-notify --ready", lock_start[-1])
        self.assertFalse(any("Type=simple" in str(task) for task in acquire))
        self.assertTrue(any("systemd_service" in str(task) for task in release))
        self.assertIn("always", next(task for task in main if task["name"].startswith("Serialize Vault apply")))
        lock = next(task["ansible.builtin.include_tasks"] for task in block if task["name"].startswith("Acquire"))
        self.assertTrue(lock["apply"]["run_once"])
        self.assertIn("_platform_vault_instances[0].host", lock["apply"]["delegate_to"])
        self.assertNotIn("rm -rf", str(acquire + release))

    def test_config_keeps_api_tls_and_raft_join_pki_roles_distinct(self):
        template = (ROLE / "templates/vault.hcl.j2").read_text(encoding="utf-8")
        self.assertIn('tls_disable = false', template)
        self.assertIn('tls_min_version = "tls12"', template)
        self.assertIn("leader_client_cert_file", template)
        self.assertNotIn("cluster_tls_cert_file", template)
        self.assertIn("disable_mlock = true", template)

    def test_3_1_and_3_3_fixtures_use_three_member_slots(self):
        for name, hosts in (("raft-ha-31.yml", 1), ("raft-ha-33.yml", 3)):
            fixture = yaml.safe_load((ROOT / "services/vault/examples" / name).read_text(encoding="utf-8"))
            self.assertEqual(fixture["platform_vault_mode"], "raft-ha")
            self.assertEqual(len(fixture["platform_vault_instances"]), 3)
            self.assertEqual(len({member["host"] for member in fixture["platform_vault_instances"]}), hosts)

    def test_seed_bootstrap_is_ordered_and_never_reinitializes_initialized_vault(self):
        tasks = yaml.safe_load((ROLE / "tasks/bootstrap.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in tasks]
        self.assertLess(names.index("Start the canonical Vault seed before any Raft follower"),
                        names.index("Initialize a new seed exactly once"))
        self.assertLess(names.index("Initialize a new seed exactly once"),
                        names.index("Durably stage the minimal init response before any unseal operation"))
        self.assertLess(names.index("Durably stage the minimal init response before any unseal operation"),
                        names.index("Unseal the seed with the configured threshold"))
        self.assertLess(names.index("Unseal the seed with the configured threshold"),
                        names.index("Join and unseal each Raft follower after the seed is healthy"))
        init = tasks[names.index("Initialize a new seed exactly once")]
        self.assertIn("not (_platform_vault_seed_init.json.initialized | bool)", init["when"])
        self.assertTrue(init["no_log"])
        material_tasks = [task for task in tasks if "_platform_vault_bootstrap_material" in str(task)
                          or "_platform_vault_effective_unseal_keys" in str(task)
                          or "/sys/unseal" in str(task)]
        self.assertTrue(material_tasks)
        self.assertTrue(all(task.get("no_log") for task in material_tasks))

    def test_standalone_output_is_private_no_overwrite_and_verify_is_read_only(self):
        output = yaml.safe_load((ROLE / "tasks/prepare_output.yml").read_text(encoding="utf-8"))
        output_text = str(output)
        self.assertIn("/secrets/", output_text)
        self.assertIn("0700", output_text)
        self.assertIn("0600", output_text)
        self.assertIn("'follow': False", output_text)
        bootstrap = yaml.safe_load((ROLE / "tasks/bootstrap.yml").read_text(encoding="utf-8"))
        copies = [task for task in bootstrap if "ansible.builtin.copy" in task]
        self.assertTrue(copies)
        self.assertTrue(all(task["ansible.builtin.copy"].get("force") is False for task in copies))
        verify = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        self.assertTrue(all("GET" == task.get("ansible.builtin.uri", {}).get("method", "GET") for task in verify
                            if "ansible.builtin.uri" in task))

    def test_audit_configuration_blocks_incompatible_owned_paths_before_writes(self):
        tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in tasks]
        self.assertLess(names.index("Refuse incompatible existing audit, KV or userpass configuration before mutation"),
                        names.index("Enable the cluster-wide file audit device only when absent"))
        for task in tasks:
            if "ansible.builtin.uri" in task and task["ansible.builtin.uri"].get("method") != "GET":
                self.assertTrue(task.get("no_log"))

    def test_vault_systemd_unit_uses_shared_audit_namespace_binding(self):
        unit = (ROLE / "templates/vault.service.j2").read_text(encoding="utf-8")
        self.assertIn("BindPaths={{ vault_member.log_directory }}:/var/log/platform-vault-audit", unit)
        self.assertIn("ReadWritePaths={{ vault_member.data_directory }} /var/log/platform-vault-audit", unit)

    def test_audit_rotation_is_bounded_and_signals_only_its_vault_instance(self):
        rotation = (ROLE / "templates/vault-audit.logrotate.j2").read_text(encoding="utf-8")
        self.assertIn("daily", rotation)
        self.assertIn("maxsize 100M", rotation)
        self.assertIn("rotate 14", rotation)
        self.assertIn("create 0600 {{ platform_vault_user }} {{ platform_vault_group }}", rotation)
        self.assertIn("su {{ platform_vault_user }} {{ platform_vault_group }}", rotation)
        self.assertIn("--signal=HUP {{ vault_member.instance_name }}.service", rotation)
        self.assertNotIn("copytruncate", rotation)

        provision = yaml.safe_load((ROLE / "tasks/provision.yml").read_text(encoding="utf-8"))
        package = next(task for task in provision if task["name"] == "Install the standard audit log rotation utility")
        timer = next(task for task in provision if task["name"] == "Enable and start the standard logrotate timer")
        self.assertEqual(package["ansible.builtin.package"], {"name": "logrotate", "state": "present"})
        self.assertTrue(timer["ansible.builtin.systemd_service"]["enabled"])

    def test_audit_free_space_gate_runs_during_preflight_before_provision(self):
        preflight = yaml.safe_load((ROLE / "tasks/preflight.yml").read_text(encoding="utf-8"))
        df_task = next(task for task in preflight if task["name"] == "Check free space for bounded Vault audit retention")
        self.assertEqual(df_task["ansible.builtin.command"]["argv"], ["df", "-PkP", "--", "/var/log"])
        gate = next(task for task in preflight if task["name"] == "Require space for one current and fourteen rotated audit files")
        self.assertIn("1600000", str(gate["ansible.builtin.assert"]))
        main = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        block = next(task["block"] for task in main if task["name"].startswith("Serialize Vault apply"))
        names = [task["name"] for task in block]
        self.assertLess(names.index("Run Vault preflight before package or service changes"),
                        names.index("Run Vault provisioning and configuration"))

    def test_existing_unit_and_rotation_files_require_exact_managed_identity(self):
        preflight = yaml.safe_load((ROLE / "tasks/preflight.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in preflight]
        self.assertIn("Inspect exact Vault unit files without following links", names)
        self.assertIn("Inspect exact Vault audit rotation files without following links", names)
        self.assertIn("Require existing unit files to carry this deployment member identity", names)
        self.assertIn("Require existing rotation files to carry this deployment member identity", names)
        for template in ("vault.service.j2", "vault-audit.logrotate.j2"):
            first = (ROLE / "templates" / template).read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, "# platform-vault-managed: {{ platform_vault_deployment_id }}/{{ vault_member.id }}")

    def test_artifact_source_gate_matches_existing_service_mode_policy(self):
        vault = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        vault_gate = next(task for task in vault if task["name"].startswith("Serialize Vault apply"))
        vault_gate = next(task for task in vault_gate["block"]
                          if task["name"].startswith("Require approved Vault artifact source"))
        expected = "platform_resolved_artifact_sources is defined or (platform_artifact_source_authority_active | default(false))"
        self.assertEqual(vault_gate["when"], expected)

        peers = [
            ROOT / "services/keepalived/ansible_collections/platform/keepalived/roles/keepalived/tasks/main.yml",
            ROOT / "services/redis/ansible_collections/platform/redis/roles/redis_tls/tasks/main.yml",
            ROOT / "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/main.yml",
            ROOT / "services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/main.yml",
        ]
        for path in peers:
            tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
            peer_gate = next(task for task in tasks if task.get("ansible.builtin.include_role", {}).get("name") == "platform.core.artifact_source_gate")
            self.assertEqual(peer_gate["when"], vault_gate["when"], path.as_posix())

        provision = yaml.safe_load((ROLE / "tasks/provision.yml").read_text(encoding="utf-8"))
        package = next(task for task in provision if task["name"].startswith("Install pinned Vault"))
        self.assertIn("platform_resolved_artifact_sources is not defined", package["when"])

    def test_preflight_checks_each_owned_path_component_before_data_reads(self):
        preflight = yaml.safe_load((ROLE / "tasks/preflight.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in preflight]
        inspect = names.index("Inspect every fixed root/deployment/member/PKI component without following links")
        data_find = names.index("Inspect only immediate existing member data entries")
        self.assertLess(inspect, data_find)
        helper = yaml.safe_load((ROLE / "tasks/validate_owned_paths.yml").read_text(encoding="utf-8"))
        self.assertTrue(any(task.get("ansible.builtin.stat", {}).get("follow") is False for task in helper))
        checks = str(next(task["ansible.builtin.set_fact"] for task in preflight
                          if task["name"].startswith("Add each fixed deployment")))
        for suffix in ("config_directory", "config_directory ~ '/pki'", "data_directory", "log_directory"):
            self.assertIn(suffix, checks)

    def test_lock_contention_and_path_boundary_validation_playbooks_cover_required_cases(self):
        lock = yaml.safe_load((ROOT / "services/vault/playbooks/validate-lock.yml").read_text(encoding="utf-8"))
        lock_text = str(lock)
        for phrase in ("contention", "ordinary release", "failed-holder", "recovery"):
            self.assertIn(phrase, lock_text)

        paths = yaml.safe_load((ROOT / "services/vault/playbooks/validate-path-boundaries.yml").read_text(encoding="utf-8"))
        block = next(task["block"] for task in paths[0]["tasks"] if "block" in task)
        cases = next(task["loop"] for task in block
                     if task["name"].startswith("Reject symlinks"))
        self.assertEqual({(case["root"], case["component"]) for case in cases}, {
            ("config", "deployment"), ("config", "member"), ("config", "pki"),
            ("data", "deployment"), ("data", "member"),
            ("log", "deployment"), ("log", "member"),
        })


if __name__ == "__main__":
    unittest.main()

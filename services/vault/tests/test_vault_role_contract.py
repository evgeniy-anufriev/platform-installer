from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / "services/vault/ansible_collections/platform/vault/roles/vault_tls"


class VaultRoleContractTests(unittest.TestCase):
    def test_instance_unit_uses_deployment_numeric_member_and_legacy_is_fail_closed(self):
        normalize = (ROLE / "tasks/normalize.yml").read_text(encoding="utf-8")
        validate = (ROLE / "tasks/validate.yml").read_text(encoding="utf-8")
        preflight = (ROLE / "tasks/preflight.yml").read_text(encoding="utf-8")
        clear = (ROOT / "services/vault/ansible_collections/platform/vault/plugins/modules/clear_member.py").read_text(encoding="utf-8")
        self.assertIn("(platform_vault_name ~ '@') ~ platform_vault_deployment_id", normalize)
        self.assertIn("^.+-[1-9][0-9]*$", validate)
        self.assertIn("VAULT_LEGACY_UNIT_REQUIRES_S11_CLEANUP", preflight)
        self.assertIn("service_name + '@'", clear)
        self.assertNotIn("hashlib", clear)

    def test_cluster_shared_mount_configuration_runs_only_on_canonical_seed(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.playbook.conditional import Conditional
        from ansible.template import Templar

        main = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        block = next(task["block"] for task in main if task["name"].startswith("Serialize Vault apply"))
        configure = next(task for task in block if task["name"].startswith("Configure audit, KV v2 and userpass"))
        self.assertEqual(configure["ansible.builtin.include_tasks"], "configure.yml")
        self.assertIn("inventory_hostname == _platform_vault_instances[0].host", configure["when"])
        self.assertNotIn("delegate_to", configure)
        loader = DataLoader()
        for hosts in (("node1",), ("node1", "node2", "node3")):
            for current in hosts:
                variables = {"platform_vault_verify_only": False,
                             "inventory_hostname": current,
                             "_platform_vault_instances": [{"host": host} for host in hosts]}
                conditional = Conditional(loader=loader)
                conditional.when = [configure["when"]]
                with self.subTest(hosts=hosts, current=current):
                    self.assertEqual(conditional.evaluate_conditional(
                        Templar(loader=loader, variables=variables), variables), current == hosts[0])
        variables["platform_vault_verify_only"] = True
        conditional = Conditional(loader=loader)
        conditional.when = [configure["when"]]
        self.assertFalse(conditional.evaluate_conditional(
            Templar(loader=loader, variables=variables), variables))

    def test_follower_unseal_inherits_outer_member_without_recursive_override(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar

        bootstrap = yaml.safe_load((ROLE / "tasks/bootstrap.yml").read_text(encoding="utf-8"))
        followers = next(task for task in bootstrap if task["name"].startswith("Join and unseal each Raft follower"))
        self.assertEqual(followers["loop_control"]["loop_var"], "vault_member")
        tasks = yaml.safe_load((ROLE / "tasks/bootstrap_follower.yml").read_text(encoding="utf-8"))
        unseal = next(task for task in tasks if task["name"] == "Unseal the joining Raft follower with the seed shares")
        self.assertEqual(unseal["ansible.builtin.include_tasks"], "unseal_member.yml")
        self.assertNotIn("vault_member", unseal.get("vars", {}))
        loader = DataLoader()
        for member_id, address, port in (("vault-ha-2", "192.168.56.101", 8302),
                                         ("vault-ha-3", "192.168.56.101", 8304),
                                         ("vault-hb-2", "192.168.56.102", 8502)):
            member = {"id": member_id, "address": address, "api_port": port}
            variables = {"vault_member": member, **unseal.get("vars", {})}
            templar = Templar(loader=loader, variables=variables)
            with self.subTest(member=member_id):
                self.assertEqual(templar.template("{{ vault_member }}"), member)
                self.assertEqual(templar.template("https://{{ vault_member.address }}:{{ vault_member.api_port }}/v1/sys/health"),
                                 f"https://{address}:{port}/v1/sys/health")

    def test_delegated_follower_tls_uses_the_members_host_plan(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar

        hostvars = {
            host: {"platform_pki_selected_consumer_plan": {
                "targetDirectory": f"/pki/{host}"}}
            for host in ("node1", "node2", "node3")
        }
        loader = DataLoader()
        for name in ("unseal_member.yml", "bootstrap_follower.yml"):
            tasks = yaml.safe_load((ROLE / "tasks" / name).read_text(encoding="utf-8"))
            for task in tasks:
                uri = task.get("ansible.builtin.uri")
                if uri is None:
                    continue
                self.assertEqual(task["delegate_to"], "{{ vault_member.host }}")
                for member_host in ("node1", "node2", "node3"):
                    variables = {
                        "vault_member": {"host": member_host},
                        "hostvars": hostvars,
                        # Bootstrap runs once on node1; this must not leak its
                        # selected directory into a delegated follower task.
                        "platform_pki_selected_consumer_plan": hostvars["node1"]["platform_pki_selected_consumer_plan"],
                    }
                    with self.subTest(task=task["name"], member_host=member_host):
                        self.assertEqual(
                            Templar(loader=loader, variables=variables).template(uri["ca_path"]),
                            f"/pki/{member_host}/ca-chain.pem",
                        )

    def test_final_health_verification_uses_each_delegated_hosts_pki_plan(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar

        tasks = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        health = next(task for task in tasks if task["name"] == "Query Vault health over validated API TLS")
        self.assertTrue(health["run_once"])
        self.assertEqual(health["delegate_to"], "{{ item.host }}")
        self.assertEqual(health["loop"], "{{ _platform_vault_instances }}")
        hostvars = {
            host: {"platform_pki_selected_consumer_plan": {"targetDirectory": f"/pki/{host}"}}
            for host in ("node1", "node2", "node3")
        }
        loader = DataLoader()
        for member_host in ("node1", "node2", "node3"):
            variables = {
                "item": {"host": member_host},
                "hostvars": hostvars,
                # run_once executes the task body from node1, while each URI
                # request is delegated to the member's own host.
                "platform_pki_selected_consumer_plan": hostvars["node1"]["platform_pki_selected_consumer_plan"],
            }
            with self.subTest(member_host=member_host):
                self.assertEqual(
                    Templar(loader=loader, variables=variables).template(health["ansible.builtin.uri"]["ca_path"]),
                    f"/pki/{member_host}/ca-chain.pem",
                )

    def test_raft_membership_verification_uses_seed_hosts_pki_plan_once(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar

        tasks = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        membership = next(task for task in tasks if task["name"] == "Read the authoritative Raft membership configuration")
        self.assertTrue(membership["run_once"])
        self.assertEqual(membership["delegate_to"], "{{ (_platform_vault_instances | first).host }}")
        hostvars = {
            host: {"platform_pki_selected_consumer_plan": {"targetDirectory": f"/pki/{host}"}}
            for host in ("node1", "node2", "node3")
        }
        loader = DataLoader()
        for inventory_host in ("node1", "node2", "node3"):
            variables = {
                "_platform_vault_instances": [{"host": "node1"}, {"host": "node2"}, {"host": "node3"}],
                "hostvars": hostvars,
                "platform_pki_selected_consumer_plan": hostvars[inventory_host]["platform_pki_selected_consumer_plan"],
            }
            with self.subTest(inventory_host=inventory_host):
                self.assertEqual(
                    Templar(loader=loader, variables=variables).template(membership["ansible.builtin.uri"]["ca_path"]),
                    "/pki/node1/ca-chain.pem",
                )

    def test_follower_waits_for_health_api_before_unsealing(self):
        tasks = yaml.safe_load((ROLE / "tasks/unseal_member.yml").read_text(encoding="utf-8"))
        read_health = tasks[0]
        self.assertEqual(read_health["register"], "_platform_vault_member_health_before")
        self.assertEqual(read_health["retries"], 30)
        self.assertEqual(read_health["delay"], 2)
        self.assertEqual(read_health["until"], "_platform_vault_member_health_before is succeeded")
        self.assertTrue(read_health["no_log"])

    def test_typed_runtime_inputs_are_closed_and_never_logged(self):
        main = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        include = next(task for task in main if task["name"] == "Resolve optional typed runtime lease inputs")
        self.assertEqual("Resolve optional typed runtime lease inputs", include["name"])
        tasks = yaml.safe_load((ROLE / "tasks/resolve_runtime_inputs.yml").read_text(encoding="utf-8"))
        self.assertTrue(all(task.get("no_log") for task in tasks))
        source = (ROLE / "tasks/resolve_runtime_inputs.yml").read_text(encoding="utf-8")
        self.assertIn("SERVICE_ADMIN_TOKEN", source)
        self.assertIn("SERVICE_UNSEAL_SHARES", source)
        self.assertNotIn("lookup('ansible.builtin.password'", source)

    def test_role_and_playbook_yaml_is_parseable(self):
        roots = [ROOT / "services/vault/ansible_collections/platform/vault/roles/vault_tls",
                 ROOT / "services/vault/playbooks"]
        for root in roots:
            for path in sorted(root.rglob("*.yml")):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertIsNotNone(yaml.safe_load(path.read_text(encoding="utf-8")))

    def test_verify_failure_message_belongs_to_assert_module(self):
        tasks = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        task = next(task for task in tasks if task["name"] == "Require the approved audit device, KV v2 and auth mounts")
        self.assertNotIn("fail_msg", task)
        self.assertEqual(task["ansible.builtin.assert"]["fail_msg"], "VAULT_CONFIGURATION_VERIFY_FAILED")

    def test_independent_verify_reconstructs_pki_through_shared_read_only_playbook(self):
        playbook = yaml.safe_load((ROOT / "services/vault/playbooks/verify.yml").read_text(encoding="utf-8"))
        self.assertEqual(playbook[0], {"import_playbook": "../../../ansible-core/playbooks/validate.yml"})
        self.assertEqual(playbook[1], {"import_playbook": "../../../ansible-core/playbooks/pki-verify.yml"})
        self.assertTrue(playbook[2]["roles"][0]["platform_vault_verify_only"])
        self.assertNotIn("pki-apply.yml", str(playbook))
        for service in ("kafka", "postgresql"):
            peer = yaml.safe_load((ROOT / "services" / service / "playbooks/verify.yml").read_text(encoding="utf-8"))
            self.assertIn(playbook[1], peer)
        shared = yaml.safe_load((ROOT / "ansible-core/playbooks/pki-verify.yml").read_text(encoding="utf-8"))
        resolver = shared[0]["tasks"][0]
        self.assertEqual(resolver["ansible.builtin.include_role"]["tasks_from"], "resolve.yml")
        self.assertTrue(resolver["vars"]["platform_pki_resolve_managed"])
        self.assertEqual(shared[1]["roles"], [{"role": "platform.core.pki_verify"}])

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

    def test_only_transient_lock_coordination_is_excluded_from_change_recap(self):
        acquire = yaml.safe_load((ROLE / "tasks/acquire_lock.yml").read_text(encoding="utf-8"))
        release = yaml.safe_load((ROLE / "tasks/release_lock.yml").read_text(encoding="utf-8"))
        hold = next(task for task in acquire if task["name"].startswith("Hold the shared Vault bootstrap lock"))
        self.assertIs(hold["changed_when"], False)
        self.assertNotIn("failed_when", hold)
        self.assertIn("--nonblock", hold["ansible.builtin.command"]["argv"])
        self.assertIs(release[0]["changed_when"], False)
        self.assertEqual(release[0]["ansible.builtin.systemd_service"]["state"], "stopped")
        lock_gate = next(task for task in acquire if task["name"].startswith("Require successful ownership"))
        self.assertEqual(lock_gate["ansible.builtin.assert"]["fail_msg"], "VAULT_DEPLOYMENT_BUSY")
        root = next(task for task in acquire if "ansible.builtin.file" in task)
        self.assertNotIn("changed_when", root)
        for filename in ("provision.yml", "configure.yml", "bootstrap.yml"):
            tasks = yaml.safe_load((ROLE / "tasks" / filename).read_text(encoding="utf-8"))
            for task in tasks:
                if any(module in task for module in ("ansible.builtin.copy", "ansible.builtin.template", "ansible.builtin.file", "ansible.builtin.package", "ansible.builtin.systemd_service")):
                    self.assertNotIn("changed_when", task, task.get("name"))

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
        self.assertEqual(names[names.index("Initialize a new seed exactly once") + 1],
                         "Durably stage the minimal init response before any unseal operation")
        self.assertLess(names.index("Synchronize recovery data and directory publication before validation"),
                        names.index("Validate the saved secret response before publishing or using it"))
        self.assertLess(names.index("Synchronize both matching custody files before recovery cleanup"),
                        names.index("Remove the protected recovery record only after both custody files exist"))
        self.assertLess(names.index("Remove the protected recovery record only after both custody files exist"),
                        names.index("Synchronize the custody directory after recovery record removal"))
        self.assertIn("not (_platform_vault_seed_init.json.initialized | bool)", init["when"])
        self.assertTrue(init["no_log"])
        material_tasks = [task for task in tasks if "_platform_vault_bootstrap_material" in str(task)
                          or "_platform_vault_effective_unseal_keys" in str(task)
                          or "/sys/unseal" in str(task)]
        self.assertTrue(material_tasks)
        self.assertTrue(all(task.get("no_log") for task in material_tasks))

    def test_shamir_follower_is_unsealed_before_waiting_for_join_completion(self):
        tasks = yaml.safe_load((ROLE / "tasks/bootstrap_follower.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in tasks]
        start = names.index("Start one Raft follower only after the seed is unsealed")
        unseal = names.index("Unseal the joining Raft follower with the seed shares")
        joined = names.index("Confirm the unsealed follower joined the initialized seed storage")
        self.assertLess(start, unseal)
        self.assertLess(unseal, joined)
        self.assertEqual(tasks[unseal]["ansible.builtin.include_tasks"], "unseal_member.yml")
        self.assertTrue(tasks[joined]["no_log"])
        self.assertIn("_platform_vault_follower_init.json.initialized | bool", tasks[joined]["until"])

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
        bootstrap_text = str(bootstrap)
        self.assertIn("/admin-token", bootstrap_text)
        self.assertIn("/unseal-shares", bootstrap_text)
        self.assertNotIn("/root-token", bootstrap_text)
        self.assertNotIn("/unseal-keys.json", bootstrap_text)
        verify = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        self.assertTrue(all("GET" == task.get("ansible.builtin.uri", {}).get("method", "GET") for task in verify
                            if "ansible.builtin.uri" in task))

    def test_verify_output_path_guard_accepts_linux_path_and_rejects_backslash(self):
        from jinja2 import Environment

        tasks = yaml.safe_load((ROLE / "tasks/read_output.yml").read_text(encoding="utf-8"))
        guard = next(task for task in tasks if task["name"] ==
                     "Require an explicit or project-root-derived standalone output path")
        expression = guard["ansible.builtin.assert"]["that"][-1]
        evaluate = Environment().compile_expression(expression)
        self.assertTrue(evaluate(_platform_vault_bootstrap_output_dir=
                                 "/var/lib/platform-installer/execution/secret-outputs/vault"))
        self.assertFalse(evaluate(_platform_vault_bootstrap_output_dir="/var/tmp/vault\\unsafe"))

    def test_audit_configuration_blocks_incompatible_owned_paths_before_writes(self):
        tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        names = [task["name"] for task in tasks]
        self.assertLess(names.index("Refuse incompatible existing audit, KV or auth configuration before mutation"),
                        names.index("Enable the cluster-wide file audit device only when absent"))
        for task in tasks:
            if "ansible.builtin.uri" in task and task["ansible.builtin.uri"].get("method") != "GET":
                self.assertTrue(task.get("no_log"))

    def test_audit_option_writer_uses_canonical_string_false(self):
        tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        enable = next(task for task in tasks if task["name"] == "Enable the cluster-wide file audit device only when absent")
        self.assertEqual(enable["ansible.builtin.uri"]["body"]["options"]["log_raw"], "false")
        self.assertIsInstance(enable["ansible.builtin.uri"]["body"]["options"]["log_raw"], str)
        self.assertIn("not in", enable["when"])

    def test_audit_false_readback_guards_use_real_ansible_conditionals(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.playbook.conditional import Conditional
        from ansible.template import Templar

        configure = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        verify = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        configure_guard = next(task for task in configure if task["name"].startswith("Refuse incompatible existing audit"))["ansible.builtin.assert"]["that"][0]
        verify_guard = next(task for task in verify if task["name"].startswith("Require the approved audit"))["ansible.builtin.assert"]["that"]
        verify_guard = next(condition for condition in verify_guard if "log_raw" in condition)
        absent = object()
        cases = [(absent, True), (False, True), ("false", True), ("False", True),
                 ("FALSE", True), ("0", True), (True, False), ("true", False),
                 ("TRUE", False), ("1", False), ("yes", False), ("off", False),
                 ("", False), (None, False), ([], False), ({}, False),
                 (" false", False), ("false ", False), ("00", False), ("0.0", False)]
        loader = DataLoader()
        for value, expected in cases:
            options = {"file_path": "/var/log/platform-vault-audit/audit.log"}
            if value is not absent:
                options["log_raw"] = value
            result = {"results": [{"json": {"data": {"file/": {
                "type": "file", "local": False, "options": options}}}}]}
            variables = {"platform_vault_name": "platform-vault",
                         "_platform_vault_owned_configuration": result,
                         "_platform_vault_configuration": result}
            for guard in (configure_guard, verify_guard):
                with self.subTest(value="absent" if value is absent else value, guard=guard):
                    conditional = Conditional(loader=loader)
                    conditional.when = [guard]
                    templar = Templar(loader=loader, variables=variables)
                    self.assertEqual(conditional.evaluate_conditional(templar, variables), expected)

        # Accepting a legacy false spelling must not weaken other audit guards.
        for field, value in (("type", "socket"), ("local", True),
                             ("options", {"file_path": "/tmp/foreign-audit.log", "log_raw": "0"})):
            audit = {"type": "file", "local": False, "options": {
                "file_path": "/var/log/platform-vault-audit/audit.log", "log_raw": "0"}}
            audit[field] = value
            variables = {"platform_vault_name": "platform-vault", "_platform_vault_owned_configuration": {
                "results": [{"json": {"data": {"file/": audit}}}]}}
            conditional = Conditional(loader=loader)
            conditional.when = [configure_guard]
            self.assertFalse(conditional.evaluate_conditional(Templar(loader=loader, variables=variables), variables))

    def test_vault_systemd_unit_uses_shared_audit_namespace_binding(self):
        unit = (ROLE / "templates/vault.service.j2").read_text(encoding="utf-8")
        self.assertIn("BindPaths={{ vault_member.log_directory }}:/var/log/{{ platform_vault_name }}-audit", unit)
        self.assertIn("ReadWritePaths={{ vault_member.data_directory }} /var/log/{{ platform_vault_name }}-audit", unit)

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
            self.assertEqual(first, "# {{ platform_vault_name }}-managed: {{ platform_vault_deployment_id }}/{{ vault_member.id }}")

    def test_artifact_source_gate_matches_existing_service_mode_policy(self):
        vault = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        vault_gate = next(task for task in vault if task["name"].startswith("Serialize Vault apply"))
        vault_gate = next(task for task in vault_gate["block"]
                          if task["name"].startswith("Require approved Vault artifact source"))
        expected = "platform_resolved_artifact_sources is defined or (platform_artifact_source_authority_active | default(false))"
        self.assertEqual(vault_gate["when"], [expected, "not (platform_vault_verify_only | bool)"])

        peers = [
            ROOT / "services/keepalived/ansible_collections/platform/keepalived/roles/keepalived/tasks/main.yml",
            ROOT / "services/redis/ansible_collections/platform/redis/roles/redis_tls/tasks/main.yml",
            ROOT / "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/main.yml",
            ROOT / "services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/main.yml",
        ]
        for path in peers:
            tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
            peer_gate = next(task for task in tasks if task.get("ansible.builtin.include_role", {}).get("name") == "platform.core.artifact_source_gate")
            service = path.relative_to(ROOT).parts[1]
            self.assertIn(expected, peer_gate["when"], path.as_posix())
            self.assertIn(f"not (platform_{service}_verify_only | bool)", peer_gate["when"], path.as_posix())
            if service == "keepalived":
                self.assertIn("platform_keepalived_lifecycle_phase == 'prepare'", peer_gate["when"])

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

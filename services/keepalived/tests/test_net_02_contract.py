from pathlib import Path
import json
import os
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ROLE = ROOT / "ansible_collections" / "platform" / "keepalived" / "roles" / "keepalived"


class Net02KeepalivedContractTests(unittest.TestCase):
    def test_advert_interval_uses_role_default_when_project_does_not_override(self):
        defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
        template = (ROLE / "templates" / "keepalived.conf.j2").read_text(encoding="utf-8")
        self.assertIn("platform_keepalived_advert_interval: 1", defaults)
        self.assertIn("configuration.advertInterval | default(platform_keepalived_advert_interval)", template)

    def test_tracking_is_opt_in_in_the_template(self):
        template = (ROLE / "templates" / "keepalived.conf.j2").read_text(encoding="utf-8")
        self.assertIn("haproxyHealthTracking", template)
        self.assertIn("vrrp_script platform_haproxy_ready_", template)
        self.assertIn("track_script", template)
        self.assertNotIn("weight ", template)
        self.assertIn("state BACKUP", template)
        self.assertIn("nopreempt", template)

    def test_future_haproxy_helper_is_materialized_deterministically(self):
        tasks = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("Установить примитив готовности HAProxy, принадлежащий пакету", tasks)
        self.assertIn("check-haproxy-ready.sh.j2", tasks)
        self.assertIn("platform_keepalived_haproxy_check_path", tasks)
        self.assertIn("mode: '0750'", tasks)

    def test_haproxy_helper_requires_service_and_responsive_socket(self):
        helper = (ROLE / "templates" / "check-haproxy-ready.sh.j2").read_text(encoding="utf-8")
        self.assertIn("systemctl is-active --quiet haproxy", helper)
        self.assertIn("socat -T 1", helper)
        self.assertIn("show info", helper)
        self.assertIn("timeout 2", helper)

    def test_cluster_barrier_orders_candidate_active_and_service_phases(self):
        playbook = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        phase_a = playbook.index("Этап A — подготовить")
        barrier_a = playbook.index("Барьер A")
        phase_b = playbook.index("Этап B — установить")
        barrier_b = playbook.index("Барьер B")
        phase_c = playbook.index("Этап C — привести")
        self.assertLess(phase_a, barrier_a)
        self.assertLess(barrier_a, phase_b)
        self.assertLess(phase_b, barrier_b)
        self.assertLess(barrier_b, phase_c)
        self.assertIn("platform_keepalived_candidate_validation_rc", playbook)
        self.assertIn("platform_keepalived_active_validation_rc", playbook)

    def test_barriers_validate_only_exact_keepalived_deployment_participants(self):
        playbook = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        self.assertIn("_platform_keepalived_selected_deployment in (hostvars[item].platform_deployments | default({}))", playbook)
        self.assertIn("platform_desired_state.serviceDeployments | default({})", playbook)
        self.assertIn("_platform_keepalived_deployment_ids", playbook)
        self.assertIn("intersect(hostvars[item].platform_deployments | default({}) | list)", playbook)
        self.assertIn("KEEPALIVED_DEPLOYMENT_PARTICIPANTS_EMPTY", playbook)
        self.assertIn("hostvars[item].platform_keepalived_candidate_validation_rc", playbook)
        self.assertIn("KEEPALIVED_CANDIDATE_BARRIER_FAILED", playbook)
        self.assertEqual(2, playbook.count("loop: \"{{ _platform_keepalived_participants }}\""))
        self.assertEqual(5, playbook.count("hostvars['localhost']._platform_keepalived_participants"))
        self.assertEqual(
            3,
            playbook.count(
                "when: inventory_hostname in (hostvars['localhost']._platform_keepalived_participants | default([]))"
            ),
        )
        self.assertNotIn("_platform_keepalived_participants: \"{{ groups['platform_targets']", playbook)
        self.assertIn("platform_keepalived_lifecycle_phase: activate", playbook)
        self.assertLess(
            playbook.index("KEEPALIVED_CANDIDATE_BARRIER_FAILED"),
            playbook.index("platform_keepalived_lifecycle_phase: activate"),
        )

    @unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required for participant-scope integration")
    def test_participant_preflight_excludes_unassigned_inventory_host(self):
        inventory = ROOT / "tests" / "fixtures" / "participant-scope-inventory.yml"
        playbook = ROOT / "playbooks" / "apply.yml"
        env = os.environ.copy()
        env["ANSIBLE_CONFIG"] = str(REPO / "ansible-core" / "ansible.cfg")
        env["ANSIBLE_COLLECTIONS_PATH"] = os.pathsep.join((
            str(REPO / "ansible-core" / "collections"),
            str(ROOT / "ansible_collections"),
        ))

        scenarios = (
            ("Installer-selected deployment", {"platform_execution_service_deployment": "keepalived-qa"}),
            ("standalone desired placement", None),
        )
        for label, extra_vars in scenarios:
            with self.subTest(scenario=label):
                command = [
                    "ansible-playbook", "-i", str(inventory), str(playbook),
                    "--tags", "keepalived-participant-scope",
                ]
                if extra_vars is not None:
                    command.extend(("-e", json.dumps(extra_vars)))
                result = subprocess.run(
                    command,
                    cwd=str(REPO),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertIn("ok: [localhost] => (item=node1)", result.stdout)
                self.assertIn("ok: [localhost] => (item=node2)", result.stdout)
                self.assertIn("skipping: [localhost] => (item=node3)", result.stdout)

    def test_active_barrier_requires_exact_validated_candidate_before_service_action(self):
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        reconcile = (ROLE / "tasks" / "reconcile.yml").read_text(encoding="utf-8")
        self.assertIn("KEEPALIVED_CANDIDATE_CHANGED_AFTER_PHASE_A", activate)
        self.assertIn("KEEPALIVED_ACTIVE_CONFIG_CHECKSUM_MISMATCH", activate)
        self.assertIn("--config-test", activate)
        self.assertIn("platform_keepalived_active_validation_rc", activate)
        self.assertEqual(2, reconcile.count("ansible.builtin.systemd:"))
        self.assertEqual(2, reconcile.count('name: "{{ platform_keepalived_service_name }}"'))

    def test_prepare_collects_native_failure_without_service_action(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("failed_when: false", prepare)
        self.assertIn("platform_keepalived_candidate_validation_rc", prepare)
        self.assertNotIn("ansible.builtin.systemd:", prepare)

    def test_activation_reuses_checksum_without_rerendering(self):
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        self.assertIn("remote_src: true", activate)
        self.assertNotIn("ansible.builtin.template", activate)
        self.assertIn("platform_keepalived_candidate_checksum", activate)

    def test_reconcile_is_after_both_failure_gates(self):
        playbook = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        self.assertEqual(playbook.count("platform_keepalived_lifecycle_phase: reconcile"), 1)
        self.assertLess(
            playbook.index("KEEPALIVED_ACTIVE_CONFIG_BARRIER_FAILED"),
            playbook.index("platform_keepalived_lifecycle_phase: reconcile"),
        )

    def test_role_has_no_single_host_apply_phase_bypass(self):
        defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
        validation = (ROLE / "tasks" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("platform_keepalived_lifecycle_phase: prepare", defaults)
        self.assertIn("['prepare', 'activate', 'reconcile']", validation)

    def test_opt_in_verify_checks_helper_haproxy_and_active_tracking(self):
        verify = (ROLE / "tasks" / "verify_tracking.yml").read_text(encoding="utf-8")
        self.assertIn("KEEPALIVED_HAPROXY_HELPER_ATTRIBUTES_INVALID", verify)
        self.assertIn("KEEPALIVED_HAPROXY_HELPER_CONTENT_INVALID", verify)
        self.assertIn("systemctl, is-active, haproxy", verify)
        self.assertIn("KEEPALIVED_HAPROXY_TRACKING_CONFIGURATION_INVALID", verify)
        self.assertIn("is not search('(^|\\\\s)weight", verify)


if __name__ == "__main__":
    unittest.main()

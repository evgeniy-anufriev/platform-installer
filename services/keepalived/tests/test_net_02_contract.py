from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "ansible_collections" / "platform" / "keepalived" / "roles" / "keepalived"


class Net02KeepalivedContractTests(unittest.TestCase):
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
        self.assertIn("Install package-owned HAProxy readiness primitive", tasks)
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
        phase_a = playbook.index("Phase A - prepare")
        barrier_a = playbook.index("Barrier A")
        phase_b = playbook.index("Phase B - install")
        barrier_b = playbook.index("Barrier B")
        phase_c = playbook.index("Phase C - reconcile")
        self.assertLess(phase_a, barrier_a)
        self.assertLess(barrier_a, phase_b)
        self.assertLess(phase_b, barrier_b)
        self.assertLess(barrier_b, phase_c)
        self.assertIn("platform_keepalived_candidate_validation_rc", playbook)
        self.assertIn("platform_keepalived_active_validation_rc", playbook)

    def test_any_participant_candidate_failure_blocks_activation_barrier(self):
        playbook = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        for participant in ("node1", "node2", "node3"):
            with self.subTest(participant=participant):
                self.assertIn("hostvars[item].platform_keepalived_candidate_validation_rc", playbook)
                self.assertIn("KEEPALIVED_CANDIDATE_BARRIER_FAILED", playbook)
        self.assertIn("platform_keepalived_lifecycle_phase: activate", playbook)
        self.assertLess(
            playbook.index("KEEPALIVED_CANDIDATE_BARRIER_FAILED"),
            playbook.index("platform_keepalived_lifecycle_phase: activate"),
        )

    def test_active_barrier_requires_exact_validated_candidate_before_service_action(self):
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        reconcile = (ROLE / "tasks" / "reconcile.yml").read_text(encoding="utf-8")
        self.assertIn("KEEPALIVED_CANDIDATE_CHANGED_AFTER_PHASE_A", activate)
        self.assertIn("KEEPALIVED_ACTIVE_CONFIG_CHECKSUM_MISMATCH", activate)
        self.assertIn("--config-test", activate)
        self.assertIn("platform_keepalived_active_validation_rc", activate)
        self.assertIn("systemd_service", reconcile)

    def test_prepare_collects_native_failure_without_service_action(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("failed_when: false", prepare)
        self.assertIn("platform_keepalived_candidate_validation_rc", prepare)
        self.assertNotIn("systemd_service", prepare)

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

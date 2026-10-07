from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from jinja2 import Template


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "ansible_collections" / "platform" / "bind" / "roles" / "bind"


class Net03BindContractTests(unittest.TestCase):
    def test_apply_projects_serial_state_once_from_controller_to_roles(self):
        apply = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        role = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Publish BIND runtime projection for this apply", apply)
        self.assertEqual(1, apply.count("Persist BIND generated serial state atomically"))
        self.assertIn("platform_generated_state_path", apply)
        self.assertIn("Bind persistent BIND generated state to this project identity", apply)
        self.assertIn("Validate loaded BIND generated state before reconciliation", apply)
        self.assertIn("Validate BIND generated state against the published project contract", apply)
        self.assertIn("hostvars['localhost'].platform_bind_runtime_projection", role)
        self.assertNotIn("platform_generated_state.serviceDeployments[item.key].dns.currentSerial", role)
        self.assertIn("include_service_endpoints: true", apply)
        self.assertIn("Resolve base-only DNS content for ordinary BIND Apply", apply)
        self.assertIn("include_service_endpoints: false", apply)
        self.assertIn("include_group_wildcards: true", apply)

    def test_candidate_failure_cannot_cross_the_cluster_activation_barrier(self):
        apply = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        self.assertIn("Prepare and validate authoritative BIND DNS candidates on all participants", apply)
        self.assertIn("Activate authoritative BIND DNS only after cluster-wide candidate validation", apply)
        self.assertEqual(3, apply.count("any_errors_fatal: true"))
        self.assertIn("platform_bind_phase: prepare", apply)
        self.assertIn("platform_bind_phase: activate", apply)
        self.assertIn("platform_bind_phase: start", apply)

    def test_base_apply_and_full_reconcile_have_separate_dns_ownership(self):
        apply = (ROOT / "playbooks" / "apply.yml").read_text(encoding="utf-8")
        full_reconcile = (ROOT / "playbooks" / "reconcile.yml").read_text(encoding="utf-8")
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        start = (ROLE / "tasks" / "start.yml").read_text(encoding="utf-8")
        reconcile_zone = (ROLE / "tasks" / "reconcile_primary_zone.yml").read_text(encoding="utf-8")
        self.assertIn("rndc, sync", apply)
        self.assertIn("_platform_bind_observed_live_serials[item.key]", apply)
        self.assertIn("platform_bind_full_reconcile | default(false) | bool", apply)
        self.assertIn("platform_bind_full_reconcile: true", full_reconcile)
        self.assertIn("Recover interrupted full zone replacement before any new BIND changes", prepare)
        self.assertIn("Replace existing primary zones only during explicit full reconcile", activate)
        self.assertIn("Install complete canonical full-reconcile zone candidate", reconcile_zone)
        self.assertIn("BIND_FULL_RECONCILE_SERIAL_RACE", reconcile_zone)
        self.assertIn("Always attempt to thaw a marked primary zone", reconcile_zone)
        self.assertIn("Verify replaced primary zone accepts local dynamic updates", reconcile_zone)
        self.assertIn("Clear primary-zone marker after authority and update verification", reconcile_zone)
        self.assertIn("Add or update only the base-owned authoritative A records", start)
        self.assertNotIn("platform_bind_runtime_serial_drift", start)

    def test_primary_only_uses_local_dynamic_update_policy(self):
        template = (ROLE / "templates" / "platform-installer.conf.j2").read_text(encoding="utf-8")
        primary, secondary = template.split("{% else %}", 1)
        self.assertIn("update-policy local;", primary)
        self.assertNotIn("allow-update", primary)
        self.assertNotIn("update-policy", secondary)

    def test_a_record_update_is_exact_idempotent_and_primary_scoped(self):
        playbook = (ROOT / "playbooks" / "integrate.yml").read_text(encoding="utf-8")
        tasks = (ROLE / "tasks" / "update_a_record.yml").read_text(encoding="utf-8")
        self.assertIn("platform_deployments[item.bindDeploymentId].roles | default([]) == ['primary']", playbook)
        self.assertIn("tasks_from: update_a_record.yml", playbook)
        self.assertIn("argv: [nsupdate, -l]", tasks)
        self.assertIn("_platform_bind_a_record_current_addresses != _platform_bind_a_record_desired_addresses", tasks)
        self.assertIn("update delete ", tasks)
        self.assertIn("update add ", tasks)
        self.assertIn("BIND_DNS_A_RECORD_UPDATE_INPUT_INVALID", tasks)
        self.assertIn("BIND_DNS_A_RECORD_UPDATE_ADDRESS_INVALID", tasks)
        self.assertIn("_platform_bind_a_record_after_addresses == _platform_bind_a_record_desired_addresses", tasks)
        self.assertIn("Build exact desired A record set including TTL", tasks)
        self.assertIn("stdin: |-", tasks)
        self.assertNotIn("rndc freeze", tasks)
        self.assertNotIn("zone.j2", tasks)

    def test_generic_source_hook_uses_core_selection_and_never_full_reconciles(self):
        integration = ROOT.parent / "integrations" / "playbooks" / "apply-endpoint.yml"
        content = integration.read_text(encoding="utf-8")
        self.assertIn("platform.core.resolve_service_integrations", content)
        self.assertIn("platform.core.resolve_service_endpoints", content)
        self.assertIn("platform.core.resolve_dns_zones", content)
        self.assertIn("include_group_wildcards: false", content)
        self.assertIn("platform_execution_service_deployment", content)
        self.assertIn("../../haproxy/playbooks/integrate.yml", content)
        self.assertIn("../../bind/playbooks/integrate.yml", content)
        self.assertNotIn("reconcile.yml", content)
        for service in ("vault", "redis", "clickhouse"):
            apply = (ROOT.parent / service / "playbooks" / "apply.yml").read_text(encoding="utf-8")
            self.assertIn("../../integrations/playbooks/apply-endpoint.yml", apply)
        for service in ("bind", "dns-client", "keepalived", "haproxy", "postgresql", "kafka", "docker"):
            apply = (ROOT.parent / service / "playbooks" / "apply.yml").read_text(encoding="utf-8")
            self.assertNotIn("apply-endpoint.yml", apply)

    def test_zone_record_fields_use_unambiguous_mapping_access(self):
        template = (ROLE / "templates" / "zone.j2").read_text(encoding="utf-8")
        self.assertNotIn("record.values", template)
        self.assertIn("record['values']", template)

    def test_rendered_multivalue_records_are_separate_physical_lines(self):
        template = Template((ROLE / "templates" / "zone.j2").read_text(encoding="utf-8"))
        projection = {
            "defaultTtl": 300,
            "mname": "node1.scada.local",
            "rname": "hostmaster.scada.local",
            "nameservers": ["node1.scada.local"],
            "records": [
                {"owner": "postgres-main.asutp.scada.local.", "type": "A", "values": ["192.0.2.112", "192.0.2.111"]},
                {"owner": "*.asutp.scada.local.", "type": "A", "values": ["192.0.2.112", "192.0.2.111"]},
            ],
        }
        rendered = template.render(platform_bind_zone_projection=projection, platform_bind_zone_serial=1)
        lines = [line for line in rendered.splitlines() if " IN A " in line]
        self.assertEqual([
            "postgres-main.asutp.scada.local. 300 IN A 192.0.2.112",
            "postgres-main.asutp.scada.local. 300 IN A 192.0.2.111",
            "*.asutp.scada.local. 300 IN A 192.0.2.112",
            "*.asutp.scada.local. 300 IN A 192.0.2.111",
        ], lines)
        self.assertEqual(2, sum("postgres-main.asutp.scada.local." in line for line in lines))
        self.assertEqual(2, sum("*.asutp.scada.local." in line for line in lines))
        self.assertNotIn("{%-", (ROLE / "templates" / "zone.j2").read_text(encoding="utf-8"))
        self.assertNotIn("-%}", (ROLE / "templates" / "zone.j2").read_text(encoding="utf-8"))

    def test_rendering_is_deterministic_and_native_zone_validation_is_clean(self):
        template = Template((ROLE / "templates" / "zone.j2").read_text(encoding="utf-8"))
        projection = {
            "defaultTtl": 300, "mname": "node1.scada.local", "rname": "hostmaster.scada.local",
            "nameservers": ["node1.scada.local", "node2.scada.local"],
            "records": [{"owner": "node1.scada.local.", "type": "A", "values": ["192.0.2.1"]},
                        {"owner": "node2.scada.local.", "type": "A", "values": ["192.0.2.2"]},
                        {"owner": "*.asutp.scada.local.", "type": "A", "values": ["192.0.2.111", "192.0.2.112"]}],
        }
        first = template.render(platform_bind_zone_projection=projection, platform_bind_zone_serial=1)
        second = template.render(platform_bind_zone_projection=projection, platform_bind_zone_serial=1)
        self.assertEqual(first, second)
        checker = shutil.which("named-checkzone")
        if checker:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "scada.local.zone"
                path.write_text("$TTL 300\n" + first, encoding="utf-8")
                result = subprocess.run([checker, "scada.local", str(path)], capture_output=True, text=True, check=False)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_options_fragment_is_kept_separate_from_zone_fragment(self):
        options = (ROLE / "templates" / "platform-installer-options.conf.j2").read_text(encoding="utf-8")
        zones = (ROLE / "templates" / "platform-installer.conf.j2").read_text(encoding="utf-8")
        self.assertIn("Included only from options", options)
        self.assertIn("recursion no;", options)
        self.assertNotIn("recursion no;", zones)

    def test_python_options_anchor_is_strict_and_accepts_indentation(self):
        anchor = re.compile(r"^\s*options\s*\{\s*$", re.MULTILINE)
        self.assertEqual(1, len(anchor.findall("options {\n};\n")))
        self.assertEqual(1, len(anchor.findall("  options   {   \n};\n")))
        self.assertEqual(0, len(anchor.findall("zone \"example\" {\n};\n")))
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("Require exactly one BIND options anchor", prepare)
        self.assertIn("BIND_OPTIONS_ANCHOR_INVALID", prepare)
        self.assertIn("BIND_OPTIONS_INCLUDE_CONTEXT_INVALID", prepare)
        self.assertNotIn("ansible.builtin.lineinfile", prepare)
        self.assertIn("Deterministically inject candidate Platform options inside BIND options context", prepare)
        self.assertIn("BIND_CANDIDATE_INCLUDE_STRUCTURE_INVALID", prepare)

    def test_activation_installs_the_validated_candidate_without_reassembly(self):
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        self.assertIn("Install exact validated candidate as active BIND main configuration", activate)
        self.assertNotIn("ansible.builtin.lineinfile", activate)
        self.assertNotIn("insertafter", activate)
        self.assertIn("Compare active BIND main configuration with validated candidate", activate)
        self.assertIn("Validate active primary BIND zone before service lifecycle", activate)

    def test_unchanged_candidate_does_not_reassemble_or_reinstall_active_config(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("Determine whether BIND candidate assembly is required", prepare)
        self.assertIn("platform_bind_candidate_rebuild_required", prepare)
        self.assertIn("checksum_algorithm: sha256", prepare)
        self.assertIn("Inspect existing primary zone state before candidate rendering", prepare)
        self.assertIn("not (_platform_bind_existing_primary_zone_by_deployment[item.key]", prepare)
        inspect = (ROLE / "tasks" / "inspect_primary_zone.yml").read_text(encoding="utf-8")
        self.assertIn("BIND_ZONE_JOURNAL_WITHOUT_MASTER_FILE", inspect)
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        self.assertIn("not (_platform_bind_existing_primary_zone_by_deployment[item.key]", activate)
        start = (ROLE / "tasks" / "start.yml").read_text(encoding="utf-8")
        self.assertIn("Add or update only the base-owned authoritative A records", start)
        self.assertNotIn("platform_bind_runtime_serial_drift", start)

    def test_changed_active_artifacts_reload_running_named(self):
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        start = (ROLE / "tasks" / "start.yml").read_text(encoding="utf-8")
        self.assertIn("Record whether active BIND artifacts changed", activate)
        self.assertIn("Reload active BIND after changed active artifacts", start)
        self.assertIn("Enable and start inactive BIND", start)
        self.assertIn("Add or update only the base-owned authoritative A records", start)
        self.assertNotIn("serial drift", start)


if __name__ == "__main__":
    unittest.main()

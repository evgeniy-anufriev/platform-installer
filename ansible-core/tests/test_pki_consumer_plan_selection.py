import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class PKIConsumerPlanSelectionTests(unittest.TestCase):
    def _run(self, requests, plans, deployment=None, expected_directory="/pki/expected", expect_success=True):
        with tempfile.TemporaryDirectory() as root:
            inventory = os.path.join(root, "hosts.yml")
            playbook = os.path.join(root, "selection.yml")
            marker = os.path.join(root, "mutation-marker")
            with open(inventory, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "all": {"hosts": {
                        "localhost": {
                            "ansible_connection": "local",
                            "platform_pki_requests": requests,
                            "platform_pki_materialization_plans": plans,
                        },
                        "node1": {"ansible_connection": "local"},
                    }},
                }))
            vars_block = {
                "platform_pki_consumer_tls_profile_id": "shared-tls",
            }
            if deployment is not None:
                vars_block["platform_execution_service_deployment"] = deployment
            with open(playbook, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent(f"""\
                    - hosts: node1
                      gather_facts: false
                      vars: {json.dumps(vars_block)}
                      tasks:
                        - ansible.builtin.include_role:
                            name: platform.core.pki_materialize
                            tasks_from: select_consumer_plan.yml
                          vars:
                            platform_pki_consumer_tls_profile_id: shared-tls
                        - ansible.builtin.file:
                            path: {marker}
                            state: touch
                        - ansible.builtin.assert:
                            that:
                              - platform_pki_selected_consumer_plan.targetDirectory == '{expected_directory}'
                """))
            environment = dict(os.environ)
            environment["ANSIBLE_CONFIG"] = os.path.join(ROOT, "ansible-core", "ansible.cfg")
            result = subprocess.run(
                ["ansible-playbook", "-i", inventory, playbook],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if expect_success:
                self.assertEqual(0, result.returncode, result.stdout)
                self.assertTrue(os.path.exists(marker))
            else:
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertIn("PKI_CONSUMER_PLAN_REQUIRED", result.stdout)
                self.assertFalse(os.path.exists(marker))

    @staticmethod
    def _consumer_request(deployment):
        return {
            "id": deployment + "-request",
            "consumers": [{
                "deploymentId": deployment,
                "memberId": deployment + "-member",
                "hostId": "node1",
                "tlsProfileRef": "shared-tls",
            }],
        }

    @staticmethod
    def _plan(deployment, directory):
        return {
            "id": deployment + "-plan",
            "requestId": deployment + "-request",
            "tlsProfileId": "shared-tls",
            "hostId": "node1",
            "targetDirectory": directory,
        }

    def test_shared_tls_profile_selects_plan_for_current_deployment(self):
        deployments = ["proxy", "kafka", "postgres"]
        requests = [self._consumer_request(item) for item in deployments]
        plans = [self._plan(item, "/pki/" + item) for item in deployments]
        plans.reverse()
        plans[0]["targetDirectory"] = "/pki/postgres"
        self._run(requests, plans, deployment="postgres", expected_directory="/pki/postgres")

    def test_ambiguous_shared_profile_without_deployment_fails_before_mutation(self):
        deployments = ["proxy", "kafka", "postgres"]
        requests = [self._consumer_request(item) for item in deployments]
        plans = [self._plan(item, "/pki/" + item) for item in deployments]
        self._run(requests, plans, expect_success=False)

    def test_unique_manual_consumer_needs_no_execution_deployment_context(self):
        self._run(
            [self._consumer_request("postgres")],
            [self._plan("postgres", "/pki/expected")],
        )


if __name__ == "__main__":
    unittest.main()

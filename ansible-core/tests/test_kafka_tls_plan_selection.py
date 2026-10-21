import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RESOLVE_TLS = os.path.join(
    ROOT,
    "services",
    "kafka",
    "ansible_collections",
    "platform",
    "kafka",
    "roles",
    "kafka_kraft",
    "tasks",
    "resolve_tls_runtime.yml",
)


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class KafkaTLSPlanSelectionTests(unittest.TestCase):
    def test_shared_tls_profile_selects_exact_kafka_deployment_request(self):
        with tempfile.TemporaryDirectory() as root:
            inventory = os.path.join(root, "hosts.yml")
            playbook = os.path.join(root, "selection.yml")
            with open(inventory, "w", encoding="utf-8") as handle:
                handle.write("all:\n  hosts:\n    node1: {ansible_connection: local}\n")
            with open(playbook, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""\
                    - hosts: node1
                      gather_facts: false
                      vars:
                        kafka_tls_member:
                          id: kafka-1
                          deployment_id: kafka-main
                          host: node1
                          tls_profile: shared-tls
                          config_directory: /etc/kafka/kafka-1
                        platform_kafka_store_type: PKCS12
                        platform_pki_secret_files:
                          runtime:pki-store-password: /run/secrets/pki-store-password
                        platform_pki_materialization_plans:
                          - {id: proxy-plan, requestId: proxy-request, tlsProfileId: shared-tls, hostId: node1, targetDirectory: /pki/proxy, formats: [PEM, PKCS12_KEYSTORE, PKCS12_TRUSTSTORE], storePasswordSecretRef: 'runtime:pki-store-password'}
                          - {id: kafka-plan, requestId: kafka-request, tlsProfileId: shared-tls, hostId: node1, targetDirectory: /pki/kafka, formats: [PEM, PKCS12_KEYSTORE, PKCS12_TRUSTSTORE], storePasswordSecretRef: 'runtime:pki-store-password'}
                        platform_pki_requests:
                          - id: proxy-request
                            usages: [serverAuth, clientAuth]
                            consumers:
                              - {deploymentId: proxy-main, memberId: 'host--node1', hostId: node1, tlsProfileRef: shared-tls}
                          - id: kafka-request
                            usages: [serverAuth, clientAuth]
                            consumers:
                              - {deploymentId: kafka-main, memberId: kafka-1, hostId: node1, tlsProfileRef: shared-tls}
                      tasks:
                        - ansible.builtin.include_tasks: %s
                        - ansible.builtin.assert:
                            that:
                              - _platform_kafka_tls_runtime_plans | length == 1
                              - _platform_kafka_tls_runtime_plans[0].id == 'kafka-plan'
                              - _platform_kafka_tls_runtime_requests | length == 1
                              - _platform_kafka_tls_runtime_requests[0].id == 'kafka-request'
                              - _platform_kafka_tls_runtime.targetDirectory == '/pki/kafka'
                """) % RESOLVE_TLS.replace("\\", "/"))
            result = subprocess.run(
                ["ansible-playbook", "-i", inventory, playbook],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()

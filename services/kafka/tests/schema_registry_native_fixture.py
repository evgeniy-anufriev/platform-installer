"""Create an isolated ordinary-role acceptance fixture on the RED OS QA node.

Run only with an explicitly supplied workspace; generated private material is
restricted to workspace/.runtime/secrets. This does not run or reset a service.
"""
import base64
import os
from pathlib import Path
import subprocess
import sys
import uuid
import yaml


def create(root):
    root = Path(root).resolve()
    secrets = root / ".runtime" / "secrets"
    secrets.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(secrets, 0o700)
    password_file = secrets / "store-password"
    if password_file.exists():
        raise ValueError("fixture already exists")
    password_file.write_text(base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("="))
    os.chmod(password_file, 0o600)

    def openssl(*args):
        subprocess.run(["openssl", *args], cwd=secrets, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-keyout", "ca-key.pem", "-out", "ca-chain.pem", "-subj", "/CN=Registry QA isolated CA")
    openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", "private-key.pem",
            "-out", "certificate.csr", "-subj", "/CN=192.168.56.102")
    (secrets / "certificate.ext").write_text("subjectAltName=IP:192.168.56.102,IP:127.0.0.1,DNS:node2\nextendedKeyUsage=serverAuth,clientAuth\n")
    openssl("x509", "-req", "-in", "certificate.csr", "-CA", "ca-chain.pem", "-CAkey", "ca-key.pem",
            "-CAcreateserial", "-days", "2", "-extfile", "certificate.ext", "-out", "certificate.pem")
    openssl("pkcs12", "-export", "-in", "certificate.pem", "-inkey", "private-key.pem",
            "-certfile", "ca-chain.pem", "-out", "keystore.p12", "-passout", "file:store-password")
    subprocess.run(["keytool", "-importcert", "-noprompt", "-alias", "qa-root", "-file", str(secrets / "ca-chain.pem"),
                    "-keystore", str(secrets / "truststore.p12"), "-storetype", "PKCS12",
                    "-storepass:file", str(password_file)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (secrets / "materialization-fingerprint").write_text("isolated-schema-registry-qa\n")
    for path in secrets.iterdir():
        if path.is_file():
            os.chmod(path, 0o600)
    deployment, identity = "qa-schema-registry-20261012", "srqa-1"
    config, logs = "/etc/kafka/" + deployment, "/var/log/kafka/" + deployment
    member = {"id": identity, "deployment_id": deployment, "host": "node2", "node_id": 1701,
              "roles": ["broker", "controller"], "advertised_host": "192.168.56.102",
              "tls_profile": "infrastructure-tls", "config_directory": config, "log_directory": logs,
              "data_directory": "/var/lib/" + deployment,
              "listeners": {"SSL": {"purpose": "interBroker", "securityProtocol": "SSL", "port": 45994},
                            "PLAINTEXT": {"purpose": "client", "securityProtocol": "PLAINTEXT", "port": 45992},
                            "CONTROLLER": {"purpose": "controller", "securityProtocol": "SSL", "port": 45993}}}
    request = {"id": "srqa-request", "usages": ["serverAuth", "clientAuth"],
               "consumers": [{"deploymentId": deployment, "memberId": identity, "hostId": "node2", "tlsProfileRef": "infrastructure-tls"}]}
    plan = {"hostId": "node2", "requestId": request["id"], "tlsProfileId": "infrastructure-tls",
            "targetDirectory": str(secrets), "storePasswordSecretRef": "runtime:srqa-store-password"}
    values = {"platform_name_prefix": "srqa", "platform_kafka_service_name": "srqa",
              "platform_kafka_deployment_id": deployment,
              "platform_kafka_cluster_id": base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("="),
              "platform_kafka_instances": [member], "platform_kafka_schema_registry_http_port": 48081,
              "platform_kafka_schema_registry_https_port": 48082,
              "platform_kafka_artifact_path": str(root / "kafka_2.13-4.3.1.tgz"),
              "platform_kafka_artifact_checksum": "sha256:f118328b2d053497350d5befd82c08db7ffd710327ff52943dd5caaa1b25db21",
              "platform_kafka_schema_registry_artifact_path": str(root / "confluent-community-8.3.2.tar.gz"),
              "platform_pki_requests": [request], "platform_pki_materialization_plans": [plan],
              "platform_pki_secret_files": {"runtime:srqa-store-password": str(password_file)}}
    (root / "srqa-vars.yml").write_text(yaml.safe_dump(values))
    (root / "srqa-inventory.ini").write_text("[platform_targets]\nnode2 ansible_connection=local ansible_host=192.168.56.102 ansible_user=platform-automation\n")
    (root / "srqa-role.yml").write_text("- hosts: platform_targets\n  become: true\n  gather_facts: true\n  roles:\n    - platform.kafka.kafka_kraft\n")
    print("isolated fixture created; private material not emitted")


if __name__ == "__main__":
    create(sys.argv[1])

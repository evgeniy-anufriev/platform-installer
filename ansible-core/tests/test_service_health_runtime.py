"""Run production health tasks through Ansible against isolated TLS endpoints."""
import http.server
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ServiceHealthRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ansible-playbook") or not shutil.which("openssl"):
            raise unittest.SkipTest("Ansible and OpenSSL required")
        cls.workspace = tempfile.TemporaryDirectory(prefix="platform-health-")
        cls.directory = Path(cls.workspace.name)
        cls.private = cls.directory / ".runtime/secrets"
        cls.private.mkdir(parents=True, mode=0o700)
        cls.token = secrets.token_urlsafe(24)
        cls.password = cls.private / "password"
        cls.password.write_text(cls.token)
        os.chmod(cls.password, 0o600)
        cls.bin = cls.directory / "bin"
        cls.bin.mkdir()
        psql = cls.bin / "psql"
        psql.write_text("#!/usr/bin/python3\nimport os,pathlib,sys\n"
                        f"expected=pathlib.Path({str(cls.password)!r}).read_text()\n"
                        "valid=(os.environ.get('PGPASSWORD')==expected and "
                        "os.environ.get('PGSSLMODE')=='verify-full' and "
                        "os.environ.get('PGSSLROOTCERT','').endswith('/pki/ca-chain.pem'))\n"
                        "print('1' if valid else 'authentication failed')\n"
                        "sys.exit(0 if valid else 2)\n")
        psql.chmod(0o700)
        cls.key, cls.ca = cls.private / "key.pem", cls.private / "ca-chain.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-keyout", str(cls.key), "-out", str(cls.ca),
                        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(cls.key, 0o600)
        cls.health = {"initialized": True, "sealed": False}
        cls.requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                cls.requests.append(self.path)
                code, body = 200, []
                if self.path.startswith("/v1/"):
                    if self.path == "/v1/sys/health":
                        body = cls.health
                    elif self.headers.get("X-Vault-Token") != cls.token:
                        code, body = 403, {}
                    elif self.path == "/v1/auth/token/lookup-self":
                        body = {"data": {}}
                    elif self.path == "/v1/sys/storage/raft/configuration":
                        body = {"data": {"config": {"servers": [{"node_id": "vault-1", "voter": True}]}}}
                    else:
                        code, body = 404, {}
                elif self.path != "/subjects":
                    code = 404
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cls.ca), str(cls.key))
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.workspace.cleanup()

    def invoke(self, service, role, filename, variables, success):
        task = ROOT / f"services/{service}/ansible_collections/platform/{service}/roles/{role}/tasks/{filename}"
        variables = dict(variables)
        # Secret values are runtime-only test inputs, never command arguments/output.
        variables["platform_vault_admin_token"] = self.token if success != "bad-token" else "invalid"
        variables["platform_pki_selected_consumer_plan"] = {"targetDirectory": str(self.private)}
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "environment": {"PATH": str(self.bin) + ":" + os.environ["PATH"]},
                 "vars": variables, "tasks": [
                     {"ansible.builtin.set_fact": {"platform_pki_selected_consumer_plan": variables["platform_pki_selected_consumer_plan"]}},
                     {"ansible.builtin.include_tasks": str(task)}]}]
        file = self.private / "play.yml"
        file.write_text(yaml.safe_dump(play), encoding="utf-8")
        os.chmod(file, 0o600)
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(file)],
                                capture_output=True, text=True, timeout=90)
        output = result.stdout + result.stderr
        self.assertNotIn(self.token, output)
        if success is True:
            self.assertEqual(0, result.returncode, output)
            self.assertRegex(output, r"changed=0\s")
        else:
            self.assertNotEqual(0, result.returncode, output)
        file.unlink()
        return output

    def registry(self, trusted=True):
        return {"_platform_kafka_registry_local": [{"id": "registry-1",
                    "https_url": f"https://127.0.0.1:{self.server.server_port}",
                    "config_directory": str(self.directory)}],
                "platform_kafka_schema_registry_readiness_retries": 1,
                "platform_kafka_schema_registry_readiness_delay": 0}

    def test_registry_healthy_and_repeat_changed_zero(self):
        pki = self.directory / "pki"
        pki.mkdir(exist_ok=True)
        shutil.copyfile(self.ca, pki / "ca-chain.pem")
        for _ in range(2):
            self.invoke("kafka", "kafka_kraft", "schema_registry_verify.yml", self.registry(), True)

    def test_registry_missing_trust_is_rejected(self):
        variables = self.registry()
        variables["_platform_kafka_registry_local"][0]["config_directory"] = str(self.directory / "missing")
        self.invoke("kafka", "kafka_kraft", "schema_registry_verify.yml", variables, False)

    def test_registry_untrusted_server_certificate_rejected(self):
        root = self.directory / "untrusted"
        (root / "pki").mkdir(parents=True, exist_ok=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-keyout", str(self.private / "untrusted-key"),
                        "-out", str(root / "pki/ca-chain.pem"), "-subj", "/CN=Other CA"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        variables = self.registry()
        variables["_platform_kafka_registry_local"][0]["config_directory"] = str(root)
        self.invoke("kafka", "kafka_kraft", "schema_registry_verify.yml", variables, False)

    def vault(self):
        return {"_platform_vault_instances": [{"id": "vault-1", "instance_name": "vault-1",
                    "host": "localhost", "address": "127.0.0.1", "api_port": self.server.server_port}],
                "platform_vault_mode": "raft-ha", "platform_vault_verify_only": True}

    def test_vault_health_authentication_and_raft_without_configuration_reads(self):
        self.requests.clear()
        self.invoke("vault", "vault_tls", "verify.yml", self.vault(), True)
        self.assertEqual(["/v1/sys/health", "/v1/auth/token/lookup-self",
                          "/v1/sys/storage/raft/configuration"], self.requests)

    def test_vault_invalid_token_rejected(self):
        self.requests.clear()
        self.invoke("vault", "vault_tls", "verify.yml", self.vault(), "bad-token")
        self.assertIn("/v1/auth/token/lookup-self", self.requests)

    def test_vault_sealed_rejected(self):
        self.health["sealed"] = True
        try:
            self.requests.clear()
            self.invoke("vault", "vault_tls", "verify.yml", self.vault(), False)
            self.assertEqual(["/v1/sys/health"], self.requests)
        finally:
            self.health["sealed"] = False

    def postgres(self, password):
        return {"_platform_postgresql_local_members": [{"address": "127.0.0.1"}],
                "_platform_postgresql_effective_port": 5432,
                "platform_postgresql_admin_superuser": {"username": "admin", "passwordSecretRef": "runtime:password"},
                "platform_postgresql_secret_files": {"runtime:password": str(password)},
                "platform_postgresql_tls_profile": "tls",
                "platform_postgresql_config_directory": str(self.directory)}

    def test_postgres_sql_authentication_tls_environment_and_repeat(self):
        for _ in range(2):
            self.invoke("postgresql", "postgresql", "verify.yml", self.postgres(self.password), True)

    def test_postgres_invalid_password_rejected(self):
        bad = self.private / "invalid-password"
        bad.write_text("invalid")
        bad.chmod(0o600)
        # Avoid the production retry delay in this isolated negative fixture.
        source = ROOT / "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/verify.yml"
        original = yaml.safe_load(source.read_text())
        original[0]["retries"] = 0
        original[0]["delay"] = 0
        variables = self.postgres(bad)
        variables["platform_vault_admin_token"] = self.token
        file = self.private / "negative.yml"
        file.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                        "environment": {"PATH": str(self.bin) + ":" + os.environ["PATH"]},
                                        "vars": variables, "tasks": original}]))
        file.chmod(0o600)
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(file)],
                                capture_output=True, text=True, timeout=45)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn(self.token, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

"""Exercise the production Docker TLS task against bounded temporary certificates."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
TESTS = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("openssl"), "RED OS Ansible/OpenSSL required")
class DockerTLSResolutionTests(unittest.TestCase):
    def test_explicit_dual_eku_is_required(self):
        collections = os.pathsep.join(
            [str(ROOT / "services/docker/ansible_collections"), str(ROOT / "ansible-core/collections")]
        )
        for eku, accepted in (
            (None, False),
            ("serverAuth", False),
            ("clientAuth", False),
            ("serverAuth,clientAuth", True),
        ):
            with self.subTest(eku=eku), tempfile.TemporaryDirectory(prefix="docker-tls-qa-") as directory:
                source = Path(directory)
                command = [
                    "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-days", "1", "-subj", "/CN=docker-qa", "-keyout",
                    str(source / "private-key.pem"), "-out", str(source / "certificate.pem"),
                    "-addext", "subjectAltName=IP:192.168.56.101",
                ]
                if eku:
                    command += ["-addext", f"extendedKeyUsage={eku}"]
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                shutil.copyfile(source / "certificate.pem", source / "ca-chain.pem")
                result = subprocess.run(
                    [
                        "ansible-playbook", "-i", str(TESTS / "hosts.yml"),
                        str(TESTS / "tls_resolution.yml"),
                        "-e", f"platform_docker_tls_directory={source}",
                    ],
                    cwd=ROOT,
                    env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": collections},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode == 0, accepted, result.stdout[-1800:])
                if not accepted:
                    self.assertIn("DOCKER_PKI_USAGES_INVALID", result.stdout)


if __name__ == "__main__":
    unittest.main()

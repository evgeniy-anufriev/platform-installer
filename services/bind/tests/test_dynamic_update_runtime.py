import base64
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class BindDynamicUpdateRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required = ("named", "named-checkconf", "named-checkzone", "rndc", "dig", "nsupdate")
        missing = [binary for binary in required if shutil.which(binary) is None]
        if missing:
            raise unittest.SkipTest("BIND runtime tools unavailable: " + ", ".join(missing))

    def run_checked(self, argv, *, input_text=None, timeout=8):
        result = subprocess.run(argv, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def query(self, port, owner, record_type, *options):
        return subprocess.run(
            ["dig", "@127.0.0.1", "-p", str(port), owner, record_type, *options],
            capture_output=True, text=True, timeout=4, check=False,
        )

    def test_local_updates_freeze_thaw_and_live_serial(self):
        with tempfile.TemporaryDirectory(prefix="platform-bind-runtime-") as tmp:
            root = Path(tmp)
            zone_path = root / "example.test.zone"
            config_path = root / "named.conf"
            session_key_path = root / "session.key"
            rndc_config_path = root / "rndc.conf"
            control_port = free_port()
            dns_port = free_port()
            while dns_port == control_port:
                dns_port = free_port()
            secret = base64.b64encode(b"isolated-bind-test-rndc-secret").decode("ascii")

            def zone(serial, include_source):
                records = "service 60 IN A 192.0.2.100\\n" if include_source else ""
                return (
                    "$ORIGIN example.test.\\n$TTL 60\\n"
                    f"@ IN SOA ns.example.test. hostmaster.example.test. ( {serial} 300 60 3600 60 )\\n"
                    "@ IN NS ns.example.test.\\n"
                    "ns 60 IN A 127.0.0.1\\n"
                    + records
                ).replace("\\n", "\n")

            zone_path.write_text(zone(100, False), encoding="ascii")
            config_path.write_text(
                "options {\\n"
                f"  directory \\\"{root}\\\";\\n"
                f"  pid-file \\\"{root / 'named.pid'}\\\";\\n"
                f"  session-keyfile \\\"{session_key_path}\\\";\\n"
                f"  listen-on port {dns_port} {{ 127.0.0.1; }};\\n"
                "  listen-on-v6 { none; };\\n"
                "  recursion no;\\n"
                "  allow-query { 127.0.0.1; };\\n"
                "};\\n"
                f"key \\\"platform-bind-test-rndc\\\" {{ algorithm hmac-sha256; secret \\\"{secret}\\\"; }};\\n"
                f"controls {{ inet 127.0.0.1 port {control_port} allow {{ 127.0.0.1; }} keys {{ \\\"platform-bind-test-rndc\\\"; }}; }};\\n"
                'zone "example.test" { type primary; file "example.test.zone"; update-policy local; };\\n'
                .replace("\\n", "\n").replace('\\"', '"'),
                encoding="ascii",
            )
            rndc_config_path.write_text(
                f"key \\\"platform-bind-test-rndc\\\" {{ algorithm hmac-sha256; secret \\\"{secret}\\\"; }};\\n"
                f"options {{ default-server 127.0.0.1; default-port {control_port}; default-key \\\"platform-bind-test-rndc\\\"; }};\\n"
                .replace("\\n", "\n").replace('\\"', '"'),
                encoding="ascii",
            )

            self.run_checked(["named-checkconf", str(config_path)])
            self.run_checked(["named-checkzone", "example.test", str(zone_path)])

            with (root / "named.log").open("wb") as log:
                process = subprocess.Popen(["named", "-g", "-c", str(config_path)], stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 12
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            self.fail("isolated named exited during startup")
                        soa = self.query(dns_port, "example.test", "SOA", "+short")
                        if soa.returncode == 0 and len(soa.stdout.split()) >= 3 and session_key_path.exists():
                            break
                        time.sleep(0.15)
                    else:
                        self.fail("isolated named did not become authoritative")

                    key = session_key_path
                    update = "zone example.test.\\nupdate add service.example.test. 60 A 192.0.2.100\\nsend\\n".replace("\\n", "\n")
                    update_result = subprocess.run(
                        ["nsupdate", "-4", "-l", "-k", str(key), "-p", str(dns_port)],
                        input=update, capture_output=True, text=True, timeout=8, check=False,
                    )
                    self.assertEqual(0, update_result.returncode, update_result.stdout + update_result.stderr + (root / "named.log").read_text(encoding="utf-8", errors="replace"))
                    self.run_checked(["rndc", "-c", str(rndc_config_path), "sync", "example.test"])
                    live = int(self.query(dns_port, "example.test", "SOA", "+short").stdout.split()[2])

                    self.run_checked(["rndc", "-c", str(rndc_config_path), "freeze", "example.test"])
                    frozen_live = int(self.query(dns_port, "example.test", "SOA", "+short").stdout.split()[2])
                    candidate_serial = live + 1
                    self.assertGreater(candidate_serial, frozen_live)
                    zone_path.write_text(zone(candidate_serial, False), encoding="ascii")
                    self.run_checked(["rndc", "-c", str(rndc_config_path), "thaw", "example.test"])

                    removed = self.query(dns_port, "service.example.test", "A", "+norecurse", "+noall", "+comments")
                    self.assertIn("status: NXDOMAIN", removed.stdout)
                    self.assertIn("flags: qr aa", removed.stdout)

                    # A second thaw can report an error when no zone is frozen;
                    # recovery is accepted only after authority and update checks.
                    subprocess.run(["rndc", "-c", str(rndc_config_path), "thaw", "example.test"], capture_output=True, text=True, timeout=5, check=False)
                    probe = "zone example.test.\\nupdate add probe.example.test. 60 A 192.0.2.101\\nsend\\n".replace("\\n", "\n")
                    self.run_checked(["nsupdate", "-4", "-l", "-k", str(key), "-p", str(dns_port)], input_text=probe)
                    self.assertIn("192.0.2.101", self.query(dns_port, "probe.example.test", "A", "+short").stdout)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()

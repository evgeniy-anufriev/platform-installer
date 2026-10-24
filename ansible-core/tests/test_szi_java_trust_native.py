"""Exercise the package launcher with a real JVM and a private TLS fixture."""
import functools
import http.server
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / 'examples/szi/application-packages/grant-access/1.0.0/assets/start-java.sh'


@unittest.skipUnless(all(shutil.which(x) for x in ('java', 'keytool', 'openssl')), 'native Java and OpenSSL required')
class JavaTrustTests(unittest.TestCase):
    def test_agent_environment_password_enables_https_without_diagnostic_disclosure(self):
        with tempfile.TemporaryDirectory(prefix='szi-java-trust-') as directory:
            root = Path(directory)
            password = 'fixture space & apostrophe\' double" $test'
            def run(argv):
                result = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, 'TLS fixture preparation failed')
            run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'key.pem',
                 '-out', 'cert.pem', '-days', '1', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'])
            run(['keytool', '-importcert', '-noprompt', '-alias', 'qa', '-file', 'cert.pem',
                 '-keystore', 'truststore.p12', '-storetype', 'PKCS12', '-storepass', password])
            (root / 'Probe.java').write_text('import java.net.*; public class Probe { public static void main(String[] a) throws Exception { try(var s=new URL(a[0]).openStream()){s.read();} System.out.println("HTTPS_TRUST_OK"); }}')
            class Quiet(http.server.SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=directory))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(root / 'cert.pem', root / 'key.pem')
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            # Translate only the container mount path; execute the exact package script and JVM flags.
            binary = root / 'bin'; binary.mkdir()
            shim = binary / 'java'
            shim.write_text('#!/usr/bin/env python3\nimport os,sys\na=sys.argv[1:]\nassert a[0]=="-Djavax.net.ssl.trustStore=/opt/application/pki/truststore.p12"\na[0]="-Djavax.net.ssl.trustStore="+os.environ["QA_TRUSTSTORE"]\nos.execv(os.environ["QA_JAVA"],[os.environ["QA_JAVA"]]+a)\n')
            shim.chmod(0o700)
            env = dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
                       QA_JAVA=shutil.which('java'), QA_TRUSTSTORE=str(root / 'truststore.p12'))
            argv = ['/bin/sh', str(LAUNCHER), str(root / 'Probe.java'), 'https://localhost:%s/' % server.server_port]
            try:
                for mode in ('missing', 'incorrect', 'valid'):
                    current = dict(env)
                    if mode != 'missing':
                        current['JAVA_KEYSTORE_PASSWORD'] = password if mode == 'valid' else 'fixture-wrong'
                    result = subprocess.run(argv, env=current, capture_output=True, text=True, timeout=30)
                    self.assertNotIn(password, result.stdout + result.stderr)
                    self.assertEqual(mode == 'valid', result.returncode == 0, 'JVM trust outcome mismatch: '+mode)
                    if mode == 'valid':
                        self.assertIn('HTTPS_TRUST_OK', result.stdout)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()

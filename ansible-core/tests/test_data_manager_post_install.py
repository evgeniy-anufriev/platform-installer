"""The package's actual curl script, with a real HTTP server and retained projects."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'examples/sdku/application-packages/data-manager/1.0.0/assets/ensure-project.sh'


@unittest.skipUnless(shutil.which('curl') and shutil.which('jq'), 'curl and jq required')
class DataManagerPostInstallTests(unittest.TestCase):
    def test_create_demo_then_repeat_preserves_existing_project(self):
        projects, created = [{'id': 7, 'name': 'retained', 'pk': 1}], []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(projects).encode())
            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                created.append(value)
                projects.append(value)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = 'http://127.0.0.1:'+str(server.server_port)
            for expected in (True, False):
                result = subprocess.run(['sh', str(SCRIPT), url, 'demo'], capture_output=True, text=True, timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(dict(status='ok', changed=expected), json.loads(result.stdout))
            self.assertEqual([{'id': 8, 'name': 'demo'}], created)
            self.assertEqual('retained', projects[0]['name'])
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

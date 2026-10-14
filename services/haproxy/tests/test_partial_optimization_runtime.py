from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import shutil
import subprocess
import tempfile
import threading
import unittest

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/haproxy/roles/haproxy"


class PartialOptimizationTests(unittest.TestCase):
    def test_unready_backend_preserves_prior_candidate_and_can_retry(self):
        class Handler(BaseHTTPRequestHandler):
            status = 503

            def do_GET(self):
                self.send_response(self.status)
                self.end_headers()

            def log_message(self, *args):
                pass

        source = yaml.safe_load((ROLE / 'tasks/prepare.yml').read_text())
        selected = [task for task in source if task.get('name') in {
            'Check the projected targets before candidate publication',
            'Reset only the temporary HAProxy candidate graph',
            'Create temporary HAProxy candidate workspace'}]
        for task in selected:
            if 'ansible.builtin.include_tasks' in task:
                task['ansible.builtin.include_tasks'] = str(ROLE / 'tasks/check_targets.yml')
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='platform-haproxy-readiness-') as directory:
                root = Path(directory)
                candidate = root / 'candidate'
                candidate.mkdir()
                marker = candidate / 'retained-proof'
                marker.write_text('last successful graph')
                variables = {'platform_haproxy_candidate_directory': str(candidate),
                             'platform_haproxy_application_backends': [{
                                 'targetDeploymentId': 'qa-app', 'settings': {'ssl': False},
                                 'endpoint': {'fqdn': 'qa-app.example'},
                                 'probe': {'path': '/status', 'expected_status': 200, 'timeout': 2},
                                 'targets': [{'address': '127.0.0.1', 'port': server.server_port}]}]}
                path = root / 'test.yml'
                path.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local',
                                                'gather_facts': False, 'vars': variables,
                                                'tasks': selected}]))
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(marker.read_text(), 'last successful graph')
                Handler.status = 200
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(marker.exists())
                self.assertTrue((candidate / 'conf.d').is_dir())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_partial_reuses_provider_files_and_only_publishes_source(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        def tasks(file, names):
            source = yaml.safe_load((ROLE / "tasks" / file).read_text())
            return [task for task in source if task.get("name") in names]
        prepare = tasks("prepare.yml", {
            "Require HAProxy PKI materialization", "Deploy HAProxy TLS PEM inputs",
            "Build HAProxy PEM bundle atomically without logging key data",
            "Record whether HAProxy TLS material changed", "Render full Platform HAProxy candidate",
            "Stage unchanged provider configuration for partial backend validation"})
        publish = tasks("activate_publish.yml", {
            "Install exact validated Platform main configuration atomically",
            "Install exact validated Platform HAProxy fragments atomically",
            "Install exact validated managed HAProxy application backend fragments",
            "Record whether the active HAProxy graph changed"})
        start = yaml.safe_load((ROLE / "tasks/start.yml").read_text())
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-partial-") as directory:
            root = Path(directory)
            active = root / "active"
            candidate = root / "candidate"
            (active / "conf.d").mkdir(parents=True)
            (candidate / "conf.d").mkdir(parents=True)
            common = {"haproxy.cfg": "# existing custom main\n",
                      "conf.d/10-public.cfg": "# existing frontend\n",
                      "conf.d/20-local-stats.cfg": "# existing stats\n",
                      "conf.d/90-stats-backends.cfg": "# existing stats backends\n"}
            for name, content in common.items():
                (active / name).write_text(content)
            source = "30-backend-vault-public.cfg"
            other = "30-backend-other-public.cfg"
            (active / "conf.d" / other).write_text("# retain other source\n")
            (candidate / "conf.d" / other).write_text("# must not publish this\n")
            (candidate / "conf.d" / source).write_text("# selected backend\n")
            variables = {"platform_haproxy_partial_deployment_id": "vault",
                         "platform_haproxy_candidate_directory": str(candidate),
                         "platform_haproxy_main_config": str(active / "haproxy.cfg"),
                         "platform_haproxy_conf_directory": str(active / "conf.d"),
                         "platform_haproxy_application_backends": [{"configFileName": source}],
                         "platform_haproxy_managed_application_backend_files": [source, other],
                         "platform_haproxy_service_name": "haproxy",
                         "_platform_haproxy_backend_archive": {"changed": False}}
            reload_check = dict(start[-1], check_mode=True, register="_qa_reload")
            checks = [{"ansible.builtin.assert": {"that": [
                "not platform_haproxy_tls_material_changed",
                "not platform_haproxy_active_artifacts_changed"]}}]
            play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": variables, "tasks": prepare + publish},
                    {"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": variables, "tasks": [reload_check,
                       {"ansible.builtin.assert": {"that": ["_qa_reload.changed"]}}]},
                    {"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": variables, "tasks": publish + checks + start}]
            path = root / "test.yml"
            path.write_text(yaml.safe_dump(play))
            # Fixtures use root-owned production copy tasks, in a disposable directory only.
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for name, content in common.items():
                self.assertEqual(content, (active / name).read_text())
                self.assertEqual(content, (candidate / name).read_text())
            self.assertEqual("# retain other source\n", (active / "conf.d" / other).read_text())
            self.assertEqual("# selected backend\n", (active / "conf.d" / source).read_text())


if __name__ == "__main__":
    unittest.main()

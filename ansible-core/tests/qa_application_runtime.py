"""Owner-authorized RED OS rootless QA using pinned public Nginx.

Creates only uniquely named QA projects; public pull is explicitly authorized.
Run explicitly, never through unittest discover. Safe metadata is the only output.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[2]
IMAGE = "docker.io/library/nginx:1.28.0-alpine"
IMAGE_ID = "sha256:c318e336065b17ff460aeac6d14bce5d0b13e35f25d5cb1843b635359fc00c9a"
SECOND_IMAGE = "docker.io/library/nginx:1.28.0-alpine-slim"
SECOND_IMAGE_ID = "sha256:72c83a2a01fe2ae843fc2bdd4c9bb73064f58215f93a226445a1e443806c4f3c"
SECOND_MANIFEST = "sha256:eb8c00e3f75d52947cbfe3cc352671e70bcb78f850be8b64e6bf9652ee8853de"
ACCOUNT = "platform-docker"


def digest(path):
    sha = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return "sha256:" + sha.hexdigest()


class ApplicationRuntimeQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="a2-runtime-")
        cls.root = Path(cls.temporary.name) / ("a2qa-" + os.path.basename(cls.temporary.name).split("-")[-1])
        shutil.copytree(REPO / "examples/valid/application-runtime", cls.root)
        cls.account = pwd.getpwnam(ACCOUNT)
        cls.failed = False
        cls.owned_extra_references = set()
        cls.local_image = "platform-application:sha256-" + IMAGE_ID.split(":", 1)[1]
        cls.docker = ["sudo", "-n", "-u", ACCOUNT, "env", "HOME=" + cls.account.pw_dir,
                      "XDG_RUNTIME_DIR=/run/user/" + str(cls.account.pw_uid),
                      "DOCKER_HOST=unix:///run/user/" + str(cls.account.pw_uid) + "/docker.sock", "docker"]
        cls.dockers = {"node1": cls.docker}
        cls.target_roots = {"node1": Path(cls.account.pw_dir) / ".local/share/platform-installer/applications" / cls.root.name}
        cls.ssh = None
        completed = subprocess.run(cls.docker + ["image", "inspect", IMAGE_ID], capture_output=True)
        if completed.returncode != 0 or json.loads(completed.stdout)[0]["Id"] != IMAGE_ID:
            raise RuntimeError("A2_EXISTING_IMAGE_PREREQUISITE")
        # All ports and names are reserved to this unique local-only QA project.
        inventory = {"all": {"hosts": {"localhost": {"ansible_connection": "local"}},
                             "children": {"platform_targets": {"hosts": {"node1": {"ansible_connection": "local", "ansible_host": "192.168.56.101"}}}}}}
        key = os.environ.get("PLATFORM_A2_SSH_KEY")
        if key:
            cls.ssh = ["ssh", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-i", key,
                       "platform-automation@192.168.56.102"]
            row = subprocess.run(cls.ssh + ["getent passwd platform-docker"], capture_output=True, check=True, timeout=30).stdout.decode().strip().split(":")
            uid, home = row[2], row[5]
            cls.dockers["node2"] = ["sudo", "-n", "-u", ACCOUNT, "env", "HOME=" + home,
                                    "XDG_RUNTIME_DIR=/run/user/" + uid, "DOCKER_HOST=unix:///run/user/" + uid + "/docker.sock", "docker"]
            cls.target_roots["node2"] = Path(home) / ".local/share/platform-installer/applications" / cls.root.name
            inventory["all"]["children"]["platform_targets"]["hosts"]["node2"] = {
                "ansible_host": "192.168.56.102", "ansible_user": "platform-automation", "ansible_ssh_private_key_file": key,
                "ansible_ssh_common_args": "-o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes"}
        (cls.root / "inventory/hosts.yml").write_text(json.dumps(inventory))
        cls.owned_alias_hosts = {host for host in cls.dockers if cls.docker_run(host, ["image", "inspect", cls.local_image], capture_output=True).returncode != 0}
        cls.vars_path = cls.root / "inventory/group_vars/all/platform-installer.yml"
        cls.target_root = Path(cls.account.pw_dir) / ".local/share/platform-installer/applications" / cls.root.name
        cls.bundle = Path(cls.temporary.name) / "image-fixture-bundle"
        archive = cls.bundle / "runtime/artifacts/applications/nginx.tar"
        archive.parent.mkdir(parents=True)
        with open(archive, "wb") as stream:
            result = subprocess.run(cls.docker + ["save", IMAGE_ID], stdout=stream, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError("A2_IMAGE_ARCHIVE_EXPORT_FAILED")
        manifest = {"apiVersion": "platform.installer/execution-bundle/v1alpha1", "kind": "ExecutionRuntimeBundle",
                    "bundleVersion": "a2-image-fixture", "bootstrapProtocol": "v1alpha1", "coreVersion": "qa",
                    "catalogDigest": "sha256:" + "0" * 64, "schemaDigest": "sha256:" + "0" * 64,
                    "platforms": [{"os": "redos", "version": "8", "architecture": "x86_64"}],
                    "components": [{"path": "runtime/artifacts/applications/nginx.tar", "sha256": digest(archive), "size": archive.stat().st_size}]}
        manifest_path = cls.bundle / "manifest.yaml"
        manifest_path.write_text(json.dumps(manifest))
        variables = json.loads(cls.vars_path.read_text())
        variables["platform_artifact_lock"]["digest"] = digest(manifest_path)
        variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE]["archive"] = {
            "ref": "runtime/artifacts/applications/nginx.tar", "sha256": digest(archive), "size": archive.stat().st_size}
        cls.registry = variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE].pop("registry")
        cls.vars_path.write_text(json.dumps(variables))
        cls.env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / "ansible-core/ansible.cfg"),
                       ANSIBLE_COLLECTIONS_PATH=str(REPO / "ansible-core/collections"), ANSIBLE_NOCOLOR="1")
        cls.logs = Path(cls.temporary.name) / "logs"
        cls.logs.mkdir(mode=0o700)

    @classmethod
    def docker_run(cls, host, arguments, **kwargs):
        command = cls.dockers[host] + arguments
        if host == "node2":
            command = cls.ssh + [shlex.join(command)]
        return subprocess.run(command, timeout=60, **kwargs)

    @classmethod
    def tearDownClass(cls):
        # Delete only containers with the exact project ownership label.
        for host in cls.dockers:
            listed = cls.docker_run(host, ["ps", "-aq", "--filter", "label=platform.installer.project=" + cls.root.name], capture_output=True)
            for identifier in listed.stdout.decode().split():
                cls.docker_run(host, ["rm", "-f", identifier], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            remaining = cls.docker_run(host, ["ps", "-aq", "--filter", "ancestor=" + IMAGE_ID], capture_output=True)
            if host in cls.owned_alias_hosts and not remaining.stdout.strip():
                cls.docker_run(host, ["image", "rm", cls.local_image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for owned_host, reference, image_id in cls.owned_extra_references:
                if host == owned_host:
                    remaining = cls.docker_run(host, ["ps", "-aq", "--filter", "ancestor=" + image_id], capture_output=True)
                    if not remaining.stdout.strip():
                        cls.docker_run(host, ["image", "rm", reference], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for library in (("sdku", "cspa") if host == "node1" else ("sdku",)):
                name = cls.root.name + "-" + library + "-apigateway-" + library + "-" + host
                listed = cls.docker_run(host, ["network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + name], capture_output=True)
                for identifier in listed.stdout.decode().split():
                    cls.docker_run(host, ["network", "rm", identifier], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Exact owned QA project subtree, bounded to the selected account HOME.
        if cls.target_root.parent == Path(cls.account.pw_dir) / ".local/share/platform-installer/applications" and cls.target_root.name == cls.root.name and cls.root.name.startswith("a2qa-"):
            subprocess.run(["sudo", "-n", "rm", "-rf", "--", str(cls.target_root)], check=True)
        if cls.ssh:
            path = cls.target_roots["node2"]
            if path.name == cls.root.name and path.name.startswith("a2qa-") and path.parent.name == "applications":
                subprocess.run(cls.ssh + [shlex.join(["sudo", "-n", "rm", "-rf", "--", str(path)])], check=True, timeout=30)
        if cls.failed:
            cls.temporary._finalizer.detach()
            print("A2_QA_FAILED_EVIDENCE=" + cls.temporary.name)
        else:
            cls.temporary.cleanup()
        print("A2_QA_PROJECT=" + cls.root.name)

    def tearDown(self):
        if self._outcome and not self._outcome.success:
            type(self).failed = True

    def play(self, operation, success=True):
        command = ["ansible-playbook", "-i", str(self.root / "inventory/hosts.yml"),
                   str(REPO / "ansible-core/playbooks/applications" / (operation + ".yml")),
                   "-e", "platform_project_root=" + str(self.root),
                   "-e", "platform_service_catalog_path=" + str(REPO / "examples/catalog/service-catalog.yml"),
                   "-e", "platform_execution_bundle_root=" + str(self.bundle)]
        log = self.logs / (self._testMethodName + "-" + operation + ".log")
        started = time.monotonic()
        try:
            completed = subprocess.run(command, env=self.env, capture_output=True, timeout=600)
        except subprocess.TimeoutExpired as error:
            type(self).failed = True
            log.write_bytes((error.stdout or b"") + (error.stderr or b""))
            log.chmod(0o600)
            raise
        log.write_bytes(completed.stdout + completed.stderr)
        log.chmod(0o600)
        print("A2_TIMING case=%s operation=%s seconds=%.3f" %
              (self._testMethodName, operation, time.monotonic() - started), flush=True)
        if success and completed.returncode:
            type(self).failed = True
        if success:
            self.assertEqual(0, completed.returncode, "A2_PLAY_FAILED protected log: " + str(log))
        else:
            self.assertNotEqual(0, completed.returncode)
        return completed.stdout.decode()

    def containers(self, host="node1"):
        rows = {}
        for library in (("sdku", "cspa") if host == "node1" else ("sdku",)):
            name = self.root.name + "-apigateway-" + library + "-" + host
            result = self.docker_run(host, ["inspect", name], capture_output=True, check=True)
            obj = json.loads(result.stdout)[0]
            rows[library] = {"id": obj["Id"], "digest": obj["Config"]["Labels"]["platform.installer.config-digest"], "running": obj["State"]["Running"]}
        return rows

    def test_01_apply_verify_and_clean_repeat(self):
        initial = self.play("apply")
        verified = self.play("verify")
        before = self.containers()
        output = self.play("apply")
        if not self.ssh:
            # Two libraries share an account; every invocation still rediscovers it.
            for observed in (initial, output):
                self.assertEqual(1, observed.count("TASK [platform.core.application_runtime : Обнаружение выбранной учетной записи Docker]"))
                self.assertEqual(1, observed.count("TASK [platform.core.application_runtime : Проверка Docker без прав root и плагина Compose без внесения изменений]"))
            self.assertNotIn('Проверка манифеста выбранной платформы в разрешённом реестре', verified)
            self.assertNotIn('Проверка Docker без прав root и плагина Compose без внесения изменений', verified)
            self.assertNotIn('Inspect expected runtime file bytes', verified)
            self.assertRegex(verified, r"node1\s+:\s+ok=\d+\s+changed=0")
        self.assertRegex(output, r"node1\s+:\s+ok=\d+\s+changed=0")
        self.assertEqual(before, self.containers())
        if self.ssh:
            self.assertRegex(output, r"node2\s+:\s+ok=\d+\s+changed=0")
            self.assertTrue(self.containers("node2")["sdku"]["running"])
            response = subprocess.run(self.ssh + ["curl --fail --silent --max-time 15 http://127.0.0.1:28180/status"], capture_output=True, check=True, timeout=30)
            self.assertEqual("apigateway-sdku:INFO\n", response.stdout.decode())
        for library, port in (("sdku", 28180), ("cspa", 28181)):
            with urllib.request.urlopen("http://127.0.0.1:%d/status" % port, timeout=30) as response:
                self.assertEqual("apigateway-%s:INFO\n" % library, response.read().decode())

    def test_02_interrupted_config_activation_recovers_and_isolates(self):
        if type(self).failed:
            self.skipTest("Initial Apply failed; recovery prerequisite not established")
        before = self.containers()
        variables = json.loads(self.vars_path.read_text())
        variables["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"]["parameters"]["log_level"] = "TRACE"
        self.vars_path.write_text(json.dumps(variables))
        # Reproduce the exact post-write/pre-up interrupted state; no production bypass.
        config_path = self.target_root / "sdku/apigateway-sdku/node1/config/default.conf"
        content = 'server {\n    listen 8080;\n    location /status {\n        default_type text/plain;\n        return 200 "apigateway-sdku:TRACE\\n";\n    }\n}\n'
        subprocess.run(["sudo", "-n", "-u", ACCOUNT, "tee", str(config_path)], input=content.encode(), stdout=subprocess.DEVNULL, check=True)
        with urllib.request.urlopen("http://127.0.0.1:28180/status", timeout=30) as response:
            self.assertEqual("apigateway-sdku:INFO\n", response.read().decode())
        # Lightweight Verify checks identity/readiness, not configuration drift.
        self.play("verify")
        self.play("apply")
        after = self.containers()
        self.assertNotEqual(before["sdku"]["id"], after["sdku"]["id"])
        self.assertNotEqual(before["sdku"]["digest"], after["sdku"]["digest"])
        self.assertEqual(before["cspa"], after["cspa"])
        with urllib.request.urlopen("http://127.0.0.1:28180/status", timeout=30) as response:
            self.assertEqual("apigateway-sdku:TRACE\n", response.read().decode())
        self.play("verify")
        self.assertRegex(self.play("apply"), r"node1\s+:\s+ok=\d+\s+changed=0")

    def test_03_public_registry_delivery(self):
        if type(self).failed:
            self.skipTest("Initial Apply failed; registry prerequisite not established")
        variables = json.loads(self.vars_path.read_text())
        record = variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE]
        record["registry"] = self.registry
        self.vars_path.write_text(json.dumps(variables))
        for host in self.dockers:
            if host not in self.owned_alias_hosts:
                self.skipTest("Digest-bound tag preexists; preserve its external ownership")
            owned = self.docker_run(host, ["ps", "-aq", "--filter", "label=platform.installer.project=" + self.root.name], capture_output=True, check=True)
            for identifier in owned.stdout.decode().split():
                self.docker_run(host, ["rm", "-f", identifier], stdout=subprocess.DEVNULL, check=True)
            self.docker_run(host, ["image", "rm", self.local_image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        hidden = self.bundle.with_name(self.bundle.name + "-hidden")
        self.bundle.rename(hidden)
        try:
            output = self.play("apply")
            self.assertIn("Получение точного манифеста авторизованной платформы", output)
        finally:
            hidden.rename(self.bundle)
        archive = self.bundle / "runtime/artifacts/applications/nginx.tar"
        with archive.open("r+b") as stream:
            stream.write(b"X")
        self.play("verify")
        self.assertRegex(self.play("apply"), r"node1\s+:\s+ok=\d+\s+changed=0")

    def test_04_invalid_selected_fallback_blocks_before_mutations(self):
        if type(self).failed:
            self.skipTest("Initial Apply failed; negative prerequisite not established")
        before = {host: self.containers(host) for host in self.dockers}
        variables = json.loads(self.vars_path.read_text())
        variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE].pop("registry", None)
        self.vars_path.write_text(json.dumps(variables))
        self.play("apply", success=False)
        self.assertEqual(before, {host: self.containers(host) for host in self.dockers})

    def test_05_parallel_libraries_bind_distinct_image_identities(self):
        if type(self).failed:
            self.skipTest("Initial Apply failed; parallel prerequisite not established")
        variables = json.loads(self.vars_path.read_text())
        variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE]["registry"] = self.registry
        variables["platform_artifact_lock"]["x-container-images"]["images"][SECOND_IMAGE] = {
            "imageId": SECOND_IMAGE_ID, "platform": {"os": "linux", "architecture": "amd64"},
            "registry": {"reference": SECOND_IMAGE, "manifestDigest": SECOND_MANIFEST}}
        variables["platform_desired_state"]["applicationLibraryDeployments"]["cspa"]["applications"]["gateway"]["overrides"]["image"] = SECOND_IMAGE
        self.vars_path.write_text(json.dumps(variables))
        reference = "platform-application:sha256-" + SECOND_IMAGE_ID.split(":", 1)[1]
        if self.docker_run("node1", ["image", "inspect", reference], capture_output=True).returncode != 0:
            self.owned_extra_references.add(("node1", reference, SECOND_IMAGE_ID))
        projects = []
        for library in ("sdku", "cspa"):
            view = Path(self.temporary.name) / "parallel-views" / library / self.root.name
            shutil.copytree(self.root, view)
            scoped = copy.deepcopy(variables)
            scoped["platform_desired_state"]["applicationLibraryDeployments"] = {
                library: scoped["platform_desired_state"]["applicationLibraryDeployments"][library]}
            (view / "inventory/group_vars/all/platform-installer.yml").write_text(json.dumps(scoped))
            for path in (view / "inventory/host_vars").glob("*/platform-installer.yml"):
                values = json.loads(path.read_text())
                values["platform_application_libraries"] = {
                    key: value for key, value in values["platform_application_libraries"].items() if key == library}
                path.write_text(json.dumps(values))
            projects.append((library, view))
        runs = []
        for library, view in projects:
            log = self.logs / (self._testMethodName + "-" + library + ".log")
            stream = log.open("wb")
            log.chmod(0o600)
            command = ["ansible-playbook", "-i", str(view / "inventory/hosts.yml"),
                       str(REPO / "ansible-core/playbooks/applications/apply.yml"),
                       "-e", "platform_project_root=" + str(view),
                       "-e", "platform_service_catalog_path=" + str(REPO / "examples/catalog/service-catalog.yml"),
                       "-e", "platform_execution_bundle_root=" + str(self.bundle)]
            runs.append((subprocess.Popen(command, env=self.env, stdout=stream, stderr=stream), stream, log))
        failures = []
        for process, stream, log in runs:
            try:
                if process.wait(timeout=600):
                    failures.append(str(log))
            finally:
                stream.close()
        if failures:
            type(self).failed = True
        self.assertEqual([], failures, "Parallel Apply failed; protected logs")
        for library, expected in (("sdku", IMAGE_ID), ("cspa", SECOND_IMAGE_ID)):
            name = self.root.name + "-apigateway-" + library + "-node1"
            obj = json.loads(self.docker_run("node1", ["inspect", name], capture_output=True, check=True).stdout)[0]
            self.assertEqual(expected, obj["Image"])
            self.assertEqual("platform-application:sha256-" + expected.split(":", 1)[1], obj["Config"]["Image"])
        self.play("verify")
        before = {host: self.containers(host) for host in self.dockers}
        self.assertRegex(self.play("apply"), r"node1\s+:\s+ok=\d+\s+changed=0")
        self.assertEqual(before, {host: self.containers(host) for host in self.dockers})

    def test_06_healthcheck_readiness_and_unhealthy_verify(self):
        if type(self).failed:
            self.skipTest("Initial Apply failed; readiness prerequisite not established")
        app_root = self.root / "application-packages/apigateway/1.0.0/roles/application_apigateway"
        defaults_path = app_root / "defaults/main.yml"
        defaults = json.loads(defaults_path.read_text())
        defaults["platform_application_definition"]["defaults"]["readiness"] = {
            "mode": "healthcheck", "retries": 6, "delay": 2}
        defaults_path.write_text(json.dumps(defaults))
        template = app_root / "templates/apigateway.compose.yml.j2"
        original = template.read_text()
        healthcheck = '\n    healthcheck:\n      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1:8080/status"]\n      interval: 1s\n      timeout: 2s\n      retries: 2\n'
        template.write_text(original + healthcheck)
        variables = json.loads(self.vars_path.read_text())
        # Separate native fixture ports allow this bounded case alongside delivery QA.
        for library, port in (("sdku", 28280), ("cspa", 28281)):
            variables["platform_desired_state"]["applicationLibraryDeployments"][library]["applications"]["gateway"]["overrides"]["ports"]["http"]["published"] = port
        for record in variables["platform_artifact_lock"]["x-container-images"]["images"].values():
            record.pop("archive", None)
        variables["platform_artifact_lock"]["x-container-images"]["images"][IMAGE]["registry"] = self.registry
        self.vars_path.write_text(json.dumps(variables))
        self.play("apply")
        self.play("verify")
        for host in self.dockers:
            for library in self.containers(host):
                name = self.root.name + "-apigateway-" + library + "-" + host
                obj = json.loads(self.docker_run(host, ["inspect", name], capture_output=True, check=True).stdout)[0]
                self.assertEqual("healthy", obj["State"]["Health"]["Status"])
        self.assertRegex(self.play("apply"), r"node1\s+:\s+ok=\d+\s+changed=0")
        template.write_text(original + healthcheck.replace('["CMD", "wget", "-q", "--spider", "http://127.0.0.1:8080/status"]', '["CMD", "false"]'))
        self.play("apply", success=False)
        before = {host: self.containers(host) for host in self.dockers}
        self.play("verify", success=False)
        self.assertEqual(before, {host: self.containers(host) for host in self.dockers})


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""A non-seed standalone participant must verify _schemas before activation."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/kafka/roles/kafka_kraft/tasks"


class RegistryPartialTopicRuntimeTests(unittest.TestCase):
    def test_seed_create_confirms_policy_and_repeat_reads_once(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-registry-seed-') as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            cli = root / 'bin/kafka-topics.sh'
            cli.write_text('#!/usr/bin/python3\nimport json,pathlib,sys\n'
                'root=pathlib.Path(__file__).resolve().parents[1]\n'
                'with (root/"calls.jsonl").open("a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                'if "--create" in sys.argv:(root/"topic").write_text("Topic: _schemas PartitionCount: 1 ReplicationFactor: 2 Configs: cleanup.policy=compact,min.insync.replicas=2")\n'
                'elif (root/"topic").exists():print((root/"topic").read_text())\n')
            cli.chmod(0o700)
            variables = dict(registry_instance=dict(id='member-1', deployment_id='qa',
                bootstrap_servers='SSL://127.0.0.1:9093', config_directory=str(root),
                replication_factor=2, min_insync_replicas=2),
                _platform_kafka_registry_projection={'instances': [dict(id='member-1', deployment_id='qa')]},
                platform_kafka_install_directory=str(root), platform_kafka_verify_only=False)
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=variables, tasks=[{'ansible.builtin.include_tasks': str(TASKS / 'schema_registry_topic.yml')}])]))
            for repeat in [False, True]:
                (root / 'calls.jsonl').write_text('')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout[-2000:] + result.stderr[-800:])
                calls = [json.loads(s) for s in (root / 'calls.jsonl').read_text().splitlines()]
                self.assertEqual(1 if repeat else 3, len(calls))
                self.assertIn('--describe', calls[0])
                if repeat:
                    self.assertIn('changed=0', result.stdout)
                else:
                    self.assertIn('--create', calls[1])
                    self.assertIn('cleanup.policy=compact', calls[1])
                    self.assertIn('min.insync.replicas=2', calls[1])

    def test_non_seed_member_checks_existing_incompatible_and_missing_topic(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        include = {'ansible.builtin.include_tasks': str(TASKS / 'schema_registry_topic.yml')}
        with tempfile.TemporaryDirectory(prefix="platform-registry-partial-") as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            cli = root / "bin/kafka-topics.sh"
            cli.write_text("#!/usr/bin/python3\nimport json,pathlib,sys\n"
                           "root=pathlib.Path(__file__).resolve().parents[1]\n"
                           "with (root/'calls.jsonl').open('a') as stream:stream.write(json.dumps(sys.argv[1:])+'\\n')\n"
                           "print((root/'topic').read_text())\n")
            cli.chmod(0o700)
            projection = {"instances": [{"id": "member-1", "deployment_id": "qa"},
                                         {"id": "member-2", "deployment_id": "qa"}]}
            variables = {"registry_instance": {"id": "member-2", "deployment_id": "qa",
                            "bootstrap_servers": "SSL://127.0.0.1:9093", "config_directory": str(root),
                            "replication_factor": 2, "min_insync_replicas": 2},
                         "_platform_kafka_registry_projection": projection,
                         "platform_kafka_install_directory": str(root), "platform_kafka_verify_only": False,
                         "platform_kafka_schema_registry_readiness_retries": 1,
                         "platform_kafka_schema_registry_readiness_delay": 0}
            good = "Topic: _schemas PartitionCount: 1 ReplicationFactor: 2 Configs: cleanup.policy=compact,min.insync.replicas=2"
            for label, description, success in (("ready", good, True),
                                                 ("incompatible", good.replace("PartitionCount: 1", "PartitionCount: 2"), False),
                                                 ("missing", "", False)):
                with self.subTest(topic=label):
                    (root / "topic").write_text(description)
                    (root / "calls.jsonl").write_text("")
                    marker = root / "activation"
                    marker.unlink(missing_ok=True)
                    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                             "vars": variables, "tasks": [include, {"ansible.builtin.copy": {
                                 "content": "activation reached", "dest": str(marker)}}]}]
                    file = root / "play.yml"
                    file.write_text(yaml.safe_dump(play))
                    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(file)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)
                    self.assertEqual(success, marker.exists())
                    calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
                    self.assertEqual(1, len(calls))
                    self.assertTrue(all("--describe" in args for args in calls))
                    self.assertFalse(any("--create" in args for args in calls))


if __name__ == "__main__":
    unittest.main()

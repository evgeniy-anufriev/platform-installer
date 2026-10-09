import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/kafka/roles/kafka_kraft/tasks/main.yml"


class KafkaUnitOwnershipRuntimeTests(unittest.TestCase):
    def test_missing_owned_and_foreign_units(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        names = ["Inspect exact Kafka member unit paths before rendering",
                 "Reject unsafe existing Kafka member unit paths",
                 "Read ownership headers from existing Kafka member units",
                 "Refuse replacement of foreign Kafka member units"]
        checks = [next(task for task in source if task.get("name") == name) for name in names]
        with tempfile.TemporaryDirectory(prefix="platform-kafka-ownership-") as directory:
            root = Path(directory)
            marker = "# platform-kafka-managed: platform-kafka@qa.service"
            for scenario, header, expected_code in [("missing", None, 0), ("owned", marker, 0),
                                                     ("foreign", "# foreign", 2)]:
                with self.subTest(scenario=scenario):
                    unit = root / (scenario + ".service")
                    if header is not None:
                        unit.write_text(header + "\n[Unit]\n", encoding="utf-8")
                    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                             "vars": {"platform_kafka_verify_only": False,
                                      "_platform_kafka_local_instances": [{"id": scenario,
                                          "systemd_unit_destination": str(unit),
                                          "systemd_unit_ownership_marker": marker}]},
                             "tasks": checks}]
                    path = root / "test.yml"
                    path.write_text(yaml.safe_dump(play), encoding="utf-8")
                    result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(expected_code, result.returncode, result.stdout + result.stderr)
                    if header is not None:
                        self.assertEqual(header + "\n[Unit]\n", unit.read_text(encoding="utf-8"))
                    else:
                        self.assertFalse(unit.exists())
                    if expected_code:
                        self.assertIn("KAFKA_UNIT_OWNERSHIP_UNKNOWN", result.stdout)


if __name__ == "__main__":
    unittest.main()

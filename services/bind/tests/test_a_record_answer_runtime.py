import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/bind/roles/bind"
OWNER = "vault.example.test."


class ARecordAnswerRuntimeTests(unittest.TestCase):
    def run_answer(self, answer, expected, success=True):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = (yaml.safe_load((ROLE / "tasks/prepare_a_record.yml").read_text()) +
                  yaml.safe_load((ROLE / "tasks/verify_a_record.yml").read_text()))
        names = {
            "Собрать существующие авторитетные записи ответов для конкретного владельца",
            "Отклонить ответ CNAME или неуправляемого владельца перед изменением записи A",
            "Нормализация набора записей после динамического обновления",
        }
        tasks = [task for task in source if task["name"] in names]
        tasks.append({"ansible.builtin.assert": {"that": [
            "_platform_bind_a_record_current_answer_lines == expected",
            "_platform_bind_a_record_after_answer_lines == expected",
        ]}})
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "vars": {"platform_bind_a_record": {"owner": OWNER},
                          "_platform_bind_a_record_current": {"stdout_lines": answer},
                          "_platform_bind_a_record_after": {"stdout_lines": answer},
                          "_platform_bind_a_record_update": {"skipped": False},
                          "expected": expected}, "tasks": tasks}]
        with tempfile.TemporaryDirectory(prefix="platform-bind-answer-") as directory:
            path = Path(directory) / "test.yml"
            path.write_text(yaml.safe_dump(play), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    capture_output=True, text=True, timeout=40)
        if success:
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        else:
            self.assertNotEqual(0, result.returncode)
            self.assertIn("BIND_DNS_A_RECORD_EXISTING_RECORD_CONFLICT", result.stdout)

    def test_nxdomain_comments_are_not_records(self):
        self.run_answer([";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 1",
                         ";; flags: qr aa; QUERY: 1, ANSWER: 0",
                         " ; WARNING: test comment", ""], [])

    def test_exact_a_record_is_retained(self):
        record = f"{OWNER} 60 IN A 192.0.2.1"
        self.run_answer([";; status: NOERROR", record], [record])

    def test_cname_is_rejected(self):
        record = f"{OWNER} 60 IN CNAME other.example.test."
        self.run_answer([record], [record], success=False)

    def test_foreign_owner_is_rejected(self):
        record = "other.example.test. 60 IN A 192.0.2.1"
        self.run_answer([record], [record], success=False)


if __name__ == "__main__":
    unittest.main()

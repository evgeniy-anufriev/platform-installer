from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "ansible_collections" / "platform" / "keepalived" / "roles" / "keepalived"


class Net02KeepalivedContractTests(unittest.TestCase):
    def test_net_02_rendered_template_has_no_haproxy_runtime_hooks(self):
        template = (ROLE / "templates" / "keepalived.conf.j2").read_text(encoding="utf-8")
        self.assertNotIn("vrrp_script", template)
        self.assertNotIn("track_script", template)

    def test_future_haproxy_helper_is_materialized_deterministically(self):
        tasks = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Install dormant package-owned HAProxy readiness primitive", tasks)
        self.assertIn("check-haproxy-ready.sh.j2", tasks)
        self.assertIn("platform_keepalived_haproxy_check_path", tasks)
        self.assertIn("mode: '0750'", tasks)


if __name__ == "__main__":
    unittest.main()

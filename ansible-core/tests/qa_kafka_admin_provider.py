"""Exercise the real provider action's dedicated admin PKI binding, target-free."""
import os
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(ROOT, 'ansible-core/collections'))
from test_application_providers import KafkaAdminSelectionTest
from ansible_collections.platform.core.plugins.action.prepare_application_providers import ActionModule


class KafkaAdminProviderActionTest(unittest.TestCase):
    def test_admin_candidate_uses_exact_member_certificate_in_both_library_orders(self):
        for sasl_first in (False, True):
            for mode in ('managed', 'existing'):
                for matching_request in (True, False):
                    with self.subTest(sasl_first=sasl_first, mode=mode, matching_request=matching_request):
                        rows, snapshot, configuration, desired, catalog = KafkaAdminSelectionTest().fixture(sasl_first, mode)
                        selected = dict(hostId='h1', tlsProfileId='infra', requestId='member-cert')
                        prepared = dict(snapshot=snapshot, execution_configuration=configuration,
                            pki_materialization=dict(materializationPlans=[selected,
                                dict(hostId='h1', tlsProfileId='infra', requestId='other-cert')],
                                requests=[dict(id='member-cert', consumers=[dict(
                                    deploymentId='kafka-main' if matching_request else 'another-deployment', memberId='member')])]))
                        action = ActionModule.__new__(ActionModule)
                        action._task = SimpleNamespace(args=dict(snapshot_result=prepared, service_catalog_path='unused', project_root=ROOT))
                        action._loader = SimpleNamespace(load_from_file=lambda path: catalog)
                        result = action.run(task_vars=dict(platform_application_rows=rows, platform_desired_state=desired))
                        self.assertFalse(result['changed'])
                        if matching_request:
                            self.assertEqual('PASS', result['status'], result.get('findings'))
                            admin = result['instanceJobs'][0]['adminCandidates'][0]
                            self.assertEqual('SASL_SSL', admin['securityProtocol'])
                            self.assertEqual([selected], admin['pkiPlans'])
                        else:
                            self.assertEqual('BLOCKED', result['status'])


if __name__ == '__main__':
    unittest.main()

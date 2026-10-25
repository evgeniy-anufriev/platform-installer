"""Library script validation and execution select the same representative."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_connections import library_script_hosts
from application_libraries import project
from application_scripts import prepare_script_jobs


class LibraryScriptSelectionTest(unittest.TestCase):
    def fixture(self):
        script = dict(id='prepare', source='prepare.sh', phase='before_start', execution='once',
                      argv=[dict(valueFrom='parameter', name='OPTIONS')])
        rows = [dict(libraryId='sample', slotId=name, instanceId=name+'-sample',
                     applicationName=name, applicationVersion='1.0.0', hostId='node1',
                     runtimeRef='docker', libraryRef='sample@1.0.0',
                     settings=dict(image='example/'+name+':1', parameters=({'OPTIONS': []} if name=='backend' else {})),
                     resources={}, connections={}, bindings={}, sharedSecrets={}, identityNames=[],
                     libraryScripts=[script], packageIdentity=dict(application=name, library='lib'))
                for name in ['backend', 'frontend']]
        desired = dict(serviceDeployments={'docker': dict(serviceType='docker', members={'node1': {'host': 'node1'}})})
        hosts = {'node1': {'platformDeployments': {'docker': {}}}}
        return script, rows, desired, hosts

    def test_parameter_required_only_on_actual_library_script_representative(self):
        script, rows, desired, hosts = self.fixture()
        result = project(rows, desired, {}, {}, hosts)
        self.assertEqual([], result['findings'])
        library = result['libraries']['sample']
        self.assertEqual(['node1'], library_script_hosts(library, 'backend-sample', script))
        self.assertEqual([], library_script_hosts(library, 'frontend-sample', script))
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'library').mkdir()
            Path(directory, 'library', 'prepare.sh').write_text('#!/bin/sh\nexit 0\n')
            jobs = [dict(libraryId='sample', instanceId=row['instanceId'], hostId='node1', projectId='qa',
                         applicationPackagePath='unused', libraryPackagePath='library', packageApplicationScripts=[],
                         packageLibraryScripts=[script], settings=row['settings']) for row in rows]
            snapshot = dict(applicationLibraries=dict(libraries=result['libraries']), hosts={'node1': {'ansibleHost': '192.0.2.1'}})
            jobs = prepare_script_jobs(directory, snapshot, desired, rows, jobs)
            self.assertEqual(['[]'], jobs[0]['scripts'][0]['argv'])
            self.assertEqual([], jobs[1]['scripts'])

    def test_missing_parameter_on_selected_representative_still_blocks(self):
        _, rows, desired, hosts = self.fixture()
        rows[0]['settings']['parameters'] = {}
        result = project(rows, desired, {}, {}, hosts)
        self.assertIn('APPLICATION_SCRIPT_REFERENCE_INVALID', [f['code'] for f in result['findings']])

    def test_selection_is_per_host_and_honors_required_connections(self):
        script = dict(requires_connections=['api'])
        library = dict(instances={'a': dict(placements={'node1': {}}, connections={}),
                                  'b': dict(placements={'node1': {}, 'node2': {}}, connections={'api': {}}),
                                  'c': dict(placements={'node2': {}}, connections={'api': {}})})
        self.assertEqual(['node1', 'node2'], library_script_hosts(library, 'b', script))
        self.assertEqual([], library_script_hosts(library, 'a', script))
        self.assertEqual([], library_script_hosts(library, 'c', script))


if __name__ == '__main__':
    unittest.main()

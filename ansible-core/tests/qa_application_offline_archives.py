"""Native Ansible common archive barrier with real locked synthetic bytes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'ansible-core/playbooks/applications/tasks/offline-archives.yml'


class ApplicationOfflineArchivesTests(unittest.TestCase):
    def probe(self, *, distinct=False, corrupt=False, registry=False, repeat=False, symlink=False):
        with tempfile.TemporaryDirectory(prefix='qa-common-archive-') as directory:
            root = Path(directory)
            components, records = [], []
            for name in (['one', 'two'] if distinct else ['one']):
                archive = root / ('runtime/artifacts/%s/image.tar' % name)
                archive.parent.mkdir(parents=True)
                archive.write_bytes(b'locked archive')
                record = dict(ref=str(archive.relative_to(root)),
                              sha256='sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest(),
                              size=archive.stat().st_size)
                records.append(record)
                components.append(dict(path=record['ref'], sha256=record['sha256'], size=record['size']))
            manifest = root / 'manifest.yaml'
            manifest.write_text(json.dumps(dict(apiVersion='platform.installer/execution-bundle/v1alpha1',
                                               kind='ExecutionRuntimeBundle', components=components)))
            digest = 'sha256:' + hashlib.sha256(manifest.read_bytes()).hexdigest()
            records = [dict(r, bundleDigest=digest) for r in records]
            target = root / records[-1]['ref']
            if corrupt:
                target.write_bytes(b'tampered')
            if symlink:
                target.unlink()
                target.symlink_to(manifest)
            hosts = {}
            for index in range(3):
                hosts['node' + str(index)] = dict(platform_application_preflight_jobs=[dict(
                    source=dict(source='REPOSITORY' if registry else 'OFFLINE_BUNDLE'),
                    authority=dict(offlineBundle=records[n % len(records)])) for n in range(2)])
            inventory = root / 'inventory.yml'
            inventory.write_text(yaml.safe_dump(dict(all=dict(children=dict(platform_targets=dict(hosts=hosts))))))
            steps = [{'ansible.builtin.import_tasks': str(TASKS)},
                     {'ansible.builtin.assert': dict(that='application_selected_offline_archives | length == %d' %
                                                    (0 if registry else len(records)))}]
            if repeat:
                steps.extend([{'ansible.builtin.copy': dict(content='tampered', dest=str(target))},
                              {'ansible.builtin.import_tasks': str(TASKS)}])
            play = root / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(platform_execution_bundle_root=str(root)), tasks=steps)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=45)
            self.assertEqual(not ((corrupt or symlink) and not registry or repeat), result.returncode == 0,
                             (result.stdout + result.stderr)[-2200:])

    def test_six_placements_select_one_archive(self):
        self.probe()

    def test_different_locked_paths_are_not_merged_even_with_identical_bytes(self):
        self.probe(distinct=True)

    def test_corrupted_selected_archive_blocks_the_barrier(self):
        self.probe(distinct=True, corrupt=True)

    def test_selected_symlink_is_rejected(self):
        self.probe(symlink=True)

    def test_repository_selection_does_not_read_offline_bytes(self):
        self.probe(registry=True, corrupt=True)

    def test_next_invocation_rechecks_instead_of_reusing_a_previous_pass(self):
        self.probe(repeat=True)


if __name__ == '__main__':
    unittest.main()

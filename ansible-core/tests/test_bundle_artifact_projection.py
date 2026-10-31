import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
SPEC = importlib.util.spec_from_file_location('projected_bundle_builder', TOOLS / 'build_execution_runtime_bundle.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
PLATFORM = ['redos:8.0:x86_64']


def archive(path, root, kafka=False, registry=False):
    names = []
    if kafka:
        names += ['bin/kafka-server-start' + ('.sh' if root.startswith('kafka_') else '')]
        if root.startswith('kafka_'):
            names += ['libs/' + root + '.jar']
    if registry:
        names += ['bin/schema-registry-start', 'share/java/schema-registry/kafka-schema-registry-' + root.removeprefix('confluent-') + '.jar']
    with tarfile.open(path, 'w:gz') as stream:
        for name in names:
            info = tarfile.TarInfo(root + '/' + name)
            info.mode = 0o755
            stream.addfile(info, io.BytesIO())


class BundleArtifactProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ('services', 'contracts'):
            BUILDER.copy_tree(BUILDER.REPOSITORY / name, self.root / name)

    def inputs(self, service):
        path = self.root / 'runtime/artifacts' / service
        path.mkdir(parents=True)
        return path

    def read(self, relative):
        return yaml.safe_load((self.root / relative).read_text())

    def defaults(self, service, role):
        return self.read('services/%s/ansible_collections/platform/%s/roles/%s/defaults/main.yml' % (service, service, role))

    def test_shared_confluent_updates_only_staged_copies_and_one_ref(self):
        source = BUILDER.REPOSITORY / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/defaults/main.yml'
        original = source.read_bytes()
        path = self.inputs('kafka') / 'combined.tar.gz'
        archive(path, 'confluent-7.8.0', kafka=True, registry=True)
        payload = path.read_bytes()
        BUILDER.project_service_artifacts(self.root, PLATFORM)
        defaults = self.defaults('kafka', 'kafka_kraft')
        self.assertEqual('7.8.0', defaults['platform_kafka_version'])
        self.assertTrue(defaults['platform_kafka_schema_registry_use_kafka_distribution'])
        self.assertEqual('', defaults['platform_kafka_script_extension'])
        self.assertEqual('/opt/confluent-7.8.0', defaults['platform_kafka_install_directory'])
        self.assertEqual(defaults['platform_kafka_install_directory'], defaults['platform_kafka_schema_registry_install_directory'])
        metadata = self.read('services/kafka/artifacts.yml')['artifacts']
        self.assertEqual({'combined.tar.gz'}, {item['filename'] for item in metadata})
        self.assertEqual({hashlib.sha256(payload).hexdigest()}, {item['sha256'] for item in metadata})
        self.assertTrue(all(item['architecture'] == 'x86_64' and item['os'] == 'redos' for item in metadata))
        BUILDER.write_service_catalog(self.root)
        sources = BUILDER.artifact_sources(self.root)
        self.assertEqual(2, len(sources))
        self.assertEqual(1, len({item['ref'] for item in sources}))
        self.assertEqual(original, source.read_bytes())
        self.assertEqual(payload, path.read_bytes())
        before = (self.root / 'catalog/service-catalog.yml').read_bytes()
        BUILDER.project_service_artifacts(self.root, PLATFORM)
        BUILDER.write_service_catalog(self.root)
        self.assertEqual(before, (self.root / 'catalog/service-catalog.yml').read_bytes())

    def test_apache_and_separate_registry_versions(self):
        directory = self.inputs('kafka')
        archive(directory / 'apache.tgz', 'kafka_2.13-4.0.0', kafka=True)
        archive(directory / 'registry.tar.gz', 'confluent-7.8.0', kafka=True, registry=True)
        BUILDER.project_service_artifacts(self.root, PLATFORM)
        defaults = self.defaults('kafka', 'kafka_kraft')
        self.assertEqual('4.0.0', defaults['platform_kafka_version'])
        self.assertEqual('7.8.0', defaults['platform_kafka_schema_registry_version'])
        self.assertFalse(defaults['platform_kafka_schema_registry_use_kafka_distribution'])
        self.assertEqual('.sh', defaults['platform_kafka_script_extension'])

    def test_duplicate_distributions_and_ambiguous_platform_block(self):
        directory = self.inputs('kafka')
        archive(directory / 'one.tgz', 'confluent-7.8.0', kafka=True, registry=True)
        for platforms in ([], ['redos:8:x86_64', 'altlinux:10:x86_64']):
            with self.assertRaisesRegex(ValueError, 'one explicit --platform'):
                BUILDER.project_service_artifacts(self.root, platforms)
        archive(directory / 'two.tgz', 'confluent-7.9.0', kafka=True, registry=True)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            BUILDER.project_service_artifacts(self.root, PLATFORM)

    def test_clickhouse_release_two_is_projected_without_restriction(self):
        directory = self.inputs('clickhouse')
        names = ['clickhouse-common-static', 'clickhouse-client', 'clickhouse-server']
        identities = {}
        for name in names:
            path = directory / (name + '.rpm')
            path.write_bytes(name.encode())
            identities[path.name] = dict(path=path, name=name, version='26.9.1', release='2')
        with patch.object(BUILDER, 'rpm_identity', side_effect=lambda path: identities[path.name]):
            BUILDER.project_service_artifacts(self.root, PLATFORM)
        defaults = self.defaults('clickhouse', 'clickhouse_tls')
        self.assertEqual('26.9.1', defaults['platform_clickhouse_package_version'])
        self.assertEqual(dict.fromkeys(names, '2'), defaults['platform_clickhouse_package_releases'])
        self.assertEqual('x86_64', defaults['platform_clickhouse_package_architecture'])
        BUILDER.write_service_catalog(self.root)
        self.assertEqual(3, len(BUILDER.artifact_sources(self.root)))

    def test_runtime_rpm_projection_retains_policy_without_duplicate(self):
        path = self.inputs('redis') / 'redis.rpm'
        path.write_bytes(b'rpm')
        with patch.object(BUILDER, 'rpm_identity', return_value=dict(path=path, name='redis', version='8.7.0', release='2.red80')):
            BUILDER.project_service_artifacts(self.root, PLATFORM)
        service = self.read('services/redis/service.yml')
        self.assertEqual([], service['runtimeRequirements'])
        self.assertEqual([dict(artifactRef='redis-runtime', requiredOffline=False)], service['artifacts'])
        self.assertEqual('8.7.0-2.red80', self.defaults('redis', 'redis_tls')['platform_redis_version'])
        BUILDER.write_service_catalog(self.root)
        self.assertEqual(1, len(BUILDER.artifact_sources(self.root)))

    def test_unsafe_archive_and_oversized_pax_block(self):
        path = self.inputs('kafka') / 'unsafe.tgz'
        for name in ('../escape', '/absolute', 'confluent-7.8.0/../../escape'):
            with tarfile.open(path, 'w:gz') as stream:
                stream.addfile(tarfile.TarInfo(name))
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                BUILDER.kafka_archive(path)
        with tarfile.open(path, 'w:gz', format=tarfile.PAX_FORMAT) as stream:
            info = tarfile.TarInfo('confluent-7.8.0/bin/schema-registry-start')
            info.pax_headers = {'comment': 'x' * (1024 * 1024 + 1)}
            stream.addfile(info)
        with self.assertRaisesRegex(ValueError, 'metadata exceeds limit'):
            BUILDER.kafka_archive(path)

    def test_reference_metadata_is_single_owner_and_bad_refs_block(self):
        from service_catalog import expand_artifact_references
        source = self.root / 'services/kafka/service.yml'
        manifest = self.read('services/kafka/service.yml')
        expanded = expand_artifact_references(manifest, source, self.root)
        self.assertEqual('platform.installer/service-manifest/v1alpha1', expanded['apiVersion'])
        self.assertEqual('8.3.2', expanded['artifacts'][0]['version'])
        self.assertTrue(expanded['artifacts'][0]['requiredOffline'])
        for reference in ('../escape', 'https://example.invalid/archive', 'missing'):
            invalid = copy.deepcopy(manifest)
            invalid['artifacts'][0]['artifactRef'] = reference
            with self.assertRaises(ValueError):
                expand_artifact_references(invalid, source, self.root)
        manifest['artifacts'].append(copy.deepcopy(manifest['artifacts'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            expand_artifact_references(manifest, source, self.root)

    def test_complete_build_is_deterministic_and_inputs_are_unchanged(self):
        runtime = self.root / 'input'
        directory = runtime / 'artifacts/kafka'
        directory.mkdir(parents=True)
        path = directory / 'confluent.tgz'
        archive(path, 'confluent-7.8.0', kafka=True, registry=True)
        original = path.read_bytes()
        source_path = BUILDER.REPOSITORY / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/defaults/main.yml'
        original_defaults = source_path.read_bytes()
        manifests = []
        for name in ('bundle-a', 'bundle-b'):
            output = self.root / name
            BUILDER.build(output, runtime, 'artifact-projection-test', '0.1.0', PLATFORM)
            manifests.append((output / 'manifest.yaml').read_bytes())
            manifest = yaml.safe_load(manifests[-1])
            self.assertEqual(2, len(manifest['artifactSources']))
            for source in manifest['artifactSources']:
                component = next(c for c in manifest['components'] if c['path'] == source['ref'])
                self.assertEqual(component['sha256'], source['sha256'])
                self.assertEqual(component['size'], source['size'])
        self.assertEqual(manifests[0], manifests[1])
        self.assertEqual(original, path.read_bytes())
        self.assertEqual(original_defaults, source_path.read_bytes())

    def test_legacy_and_escaping_fqcn_never_write_outside_staging(self):
        external = self.root / 'external-role/defaults/main.yml'
        external.parent.mkdir(parents=True)
        external.write_bytes(b'sentinel: unchanged\n')
        source = self.root / 'services/redis/service.yml'
        original = yaml.safe_load(source.read_text())
        runtime = self.root / 'input'
        directory = runtime / 'artifacts/redis'
        directory.mkdir(parents=True)
        (directory / 'redis.rpm').write_bytes(b'not inspected before manifest validation')
        roots = [('services', self.root / 'services'), ('contracts', self.root / 'contracts'),
                 ('ansible-core', BUILDER.REPOSITORY / 'ansible-core')]
        for version in ('v1alpha1', 'v1alpha2'):
            for role in (str(external.parent.parent), '../external-role'):
                manifest = copy.deepcopy(original)
                manifest['apiVersion'] = 'platform.installer/service-manifest/' + version
                manifest['roleEntrypoints']['apply']['fqcn'] = 'platform.redis.' + role
                source.write_text(yaml.safe_dump(manifest))
                with patch.object(BUILDER, 'SOURCE_ROOTS', roots), patch.object(BUILDER, 'rpm_identity',
                        side_effect=lambda path: dict(path=path, name='redis', version='8.7.0', release='2')), self.assertRaises(ValueError):
                    BUILDER.build(self.root / 'published', runtime, 'invalid-service', '0.1.0', PLATFORM)
                self.assertEqual(b'sentinel: unchanged\n', external.read_bytes())
                self.assertFalse((self.root / 'published').exists())
                self.assertFalse((self.root / 'published.tmp').exists())
        from service_catalog import expand_artifact_references
        legacy = copy.deepcopy(original)
        legacy['apiVersion'] = 'platform.installer/service-manifest/v1alpha1'
        with self.assertRaisesRegex(ValueError, 'unsupported service manifest version'):
            expand_artifact_references(legacy, source, self.root)

    def test_resolved_defaults_path_cannot_leave_staging(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'main.yml'
            external.write_bytes(b'sentinel: unchanged\n')
            defaults = self.root / 'services/redis/ansible_collections/platform/redis/roles/redis_tls/defaults/main.yml'
            defaults.unlink()
            defaults.symlink_to(external)
            path = self.inputs('redis') / 'redis.rpm'
            path.write_bytes(b'rpm')
            with patch.object(BUILDER, 'rpm_identity', return_value=dict(path=path, name='redis', version='8.7.0', release='2')):
                with self.assertRaisesRegex(ValueError, 'defaults path escapes bundle staging'):
                    BUILDER.project_service_artifacts(self.root, PLATFORM)
            self.assertEqual(b'sentinel: unchanged\n', external.read_bytes())


if __name__ == '__main__':
    unittest.main()

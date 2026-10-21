"""Docker-save identity and immutable bundle image index."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_images import docker_save_image, normalize_image, registry_request
SPEC = importlib.util.spec_from_file_location('image_bundle_builder', ROOT / 'ansible-core/tools/build_execution_runtime_bundle.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ApplicationImagesTests(unittest.TestCase):
    def archive(self, path, corrupt=False, duplicate=False, compressed=False):
        layer = b'a layer of a synthetic image'
        config = json.dumps(dict(os='linux', architecture='amd64',
                                 rootfs=dict(type='layers', diff_ids=['sha256:' + hashlib.sha256(layer).hexdigest()]))).encode()
        files = [('manifest.json', json.dumps([dict(Config='config.json', RepoTags=['example.test/app:1'], Layers=['layer.tar'])]).encode()),
                 ('config.json', config), ('layer.tar', b'corrupt' if corrupt else layer)]
        if duplicate:
            files.append(files[0])
        with tarfile.open(path, 'w:gz' if compressed else 'w') as stream:
            for name, content in files:
                member = tarfile.TarInfo(name)
                member.size = len(content)
                stream.addfile(member, io.BytesIO(content))
        return 'sha256:' + hashlib.sha256(config).hexdigest()

    def test_reference_normalization_preserves_registry_port_and_tag_case(self):
        self.assertEqual(normalize_image('nginx'), 'docker.io/library/nginx:latest')
        self.assertEqual(normalize_image('team/app:SNAPSHOT'), 'docker.io/team/app:SNAPSHOT')
        self.assertEqual(normalize_image('localhost:5000/app:1'), 'localhost:5000/app:1')
        pinned = dict(registry=dict(reference='mirror.example:5000/team/app:old', manifestDigest='sha256:' + 'a' * 64))
        request = registry_request('app:latest', pinned)
        self.assertEqual((request['registry'], request['repository'], request['version']),
                         ('mirror.example:5000', 'team/app', pinned['registry']['manifestDigest']))
        self.assertEqual(registry_request('example.test/app:tag@sha256:' + 'b' * 64)['repository'], 'app')

    def test_bundle_index_uses_config_identity_and_component_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'runtime/artifacts/app.tar'
            path.parent.mkdir(parents=True)
            image_id = self.archive(path)
            index = BUILDER.container_images(root, [('example.test/app:1', 'artifacts/app.tar')])
            self.assertEqual(index, [dict(reference='example.test/app:1', imageId=image_id,
                                         platform=dict(os='linux', architecture='amd64'),
                                         archiveRef='runtime/artifacts/app.tar')])
            self.assertNotEqual(image_id, BUILDER.digest_file(path))

    def test_bundle_index_accepts_compressed_docker_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'runtime/artifacts/app.tar.gz'
            path.parent.mkdir(parents=True)
            image_id = self.archive(path, compressed=True)
            index = BUILDER.container_images(root, [('example.test/app:1', 'artifacts/app.tar.gz')])
            self.assertEqual(index[0]['imageId'], image_id)
            self.assertEqual(index[0]['archiveRef'], 'runtime/artifacts/app.tar.gz')

    def test_rejects_corrupt_layers_duplicate_members_and_unproven_digest_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'app.tar'
            for kwargs in [dict(corrupt=True), dict(duplicate=True)]:
                self.archive(path, **kwargs)
                with self.assertRaises(ValueError):
                    docker_save_image(path, 'example.test/app:1')
            self.archive(path)
            with self.assertRaisesRegex(ValueError, 'DIGEST_UNPROVEN'):
                docker_save_image(path, 'example.test/app@sha256:' + 'a' * 64)

    def test_index_rejects_conflicting_release_archives_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'runtime/artifacts').mkdir(parents=True)
            for name in ['a.tar', 'b.tar']:
                self.archive(root / 'runtime/artifacts' / name)
            with self.assertRaisesRegex(ValueError, 'AMBIGUOUS'):
                BUILDER.container_images(root, [('example.test/app:1', 'artifacts/a.tar'),
                                                ('example.test/app:1', 'artifacts/b.tar')])
            with self.assertRaisesRegex(ValueError, 'PATH_INVALID'):
                BUILDER.container_images(root, [('example.test/app:1', '../a.tar')])

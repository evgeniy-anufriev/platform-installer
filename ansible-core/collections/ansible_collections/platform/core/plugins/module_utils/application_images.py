"""Image format parsing; source policy and orchestration remain in Ansible."""
import hashlib
import json
import re
import tarfile


DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')
REFERENCE = re.compile(r'^[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]*)?(?:@sha256:[0-9a-f]{64})?$')


def normalize_image(reference):
    if not isinstance(reference, str) or not REFERENCE.fullmatch(reference):
        raise ValueError('APPLICATION_IMAGE_REFERENCE_INVALID')
    name, marker, digest = reference.partition('@')
    first, slash, rest = name.partition('/')
    if not slash or not ('.' in first or ':' in first or first == 'localhost'):
        name = 'docker.io/' + ('library/' if not slash else '') + name
    if not marker and ':' not in name.rsplit('/', 1)[-1]:
        name += ':latest'
    return name + (marker + digest if marker else '')


def image_platform(config):
    platform = {key: config[key] for key in ('os', 'architecture', 'variant') if config.get(key)}
    if platform.get('os') != 'linux' or platform.get('architecture') not in ('amd64', 'arm64'):
        raise ValueError('APPLICATION_IMAGE_PLATFORM_INVALID')
    return platform


def placement_key(row):
    return ':'.join(row[key] for key in ('libraryId', 'instanceId', 'hostId'))


def selected_image(lock, reference, library_id, instance_id, host_id):
    if lock.get('apiVersion') == 'platform.installer/container-images/v1alpha2':
        entry = lock.get('placements', {}).get(':'.join((library_id, instance_id, host_id)), {})
        if normalize_image(entry.get('reference')) != normalize_image(reference):
            raise ValueError('APPLICATION_IMAGE_NOT_LOCKED')
        return entry.get('image')
    images = [value for key, value in lock.get('images', {}).items()
              if normalize_image(key) == normalize_image(reference)]
    if len(images) > 1 and any(value != images[0] for value in images[1:]):
        raise ValueError('APPLICATION_ARTIFACT_LOCK_CONFLICT')
    return images[0] if images else None


def offline_image(manifest, reference, platform, expected=None):
    records = [record for record in manifest.get('containerImages', [])
               if normalize_image(record['reference']) == normalize_image(reference) and
               all(record['platform'].get(key) == value for key, value in platform.items())]
    if len(records) > 1:
        raise ValueError('APPLICATION_IMAGE_ARCHIVE_AMBIGUOUS')
    if not records:
        return {}
    record = records[0]
    if expected and record['imageId'] != expected['imageId']:
        raise ValueError('APPLICATION_ARTIFACT_LOCK_CONFLICT')
    components = [component for component in manifest['components'] if component['path'] == record['archiveRef']]
    if len(components) != 1 or not record['archiveRef'].startswith('runtime/artifacts/'):
        raise ValueError('APPLICATION_IMAGE_ARCHIVE_NOT_LOCKED')
    component = components[0]
    return dict(imageId=record['imageId'], platform=record['platform'],
                archive=dict(ref=component['path'], sha256=component['sha256'], size=component['size']))


def registry_request(reference, legacy=None):
    pinned = (legacy or {}).get('registry', {})
    normalized = normalize_image(pinned.get('reference', reference))
    registry, repository = normalized.split('/', 1)
    name, marker, version = repository.partition('@')
    if not marker:
        name, version = name.rsplit(':', 1)
    elif ':' in name.rsplit('/', 1)[-1]:
        name = name.rsplit(':', 1)[0]
    if pinned:
        version = pinned['manifestDigest']
    return dict(registry=registry, endpoint='registry-1.docker.io' if registry == 'docker.io' else registry, repository=name, version=version,
                reference=reference, digest=version if version.startswith('sha256:') else '')


def registry_manifest(raw, platform, expected=''):
    if not isinstance(raw, str) or len(raw.encode()) > 8 * 1024 * 1024:
        raise ValueError('APPLICATION_REGISTRY_MANIFEST_INVALID')
    actual = 'sha256:' + hashlib.sha256(raw.encode()).hexdigest()
    if expected and actual != expected:
        raise ValueError('APPLICATION_REGISTRY_MANIFEST_DIGEST_INVALID')
    value = json.loads(raw)
    media = value.get('mediaType')
    if media in ('application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.list.v2+json'):
        entries = [entry for entry in value['manifests'] if all(entry.get('platform', {}).get(key) == item for key, item in platform.items())]
        if not entries:
            return dict(manifestDigest=actual, configDigest='', index=False)
        if len(entries) != 1 or not DIGEST.fullmatch(entries[0]['digest']):
            raise ValueError('APPLICATION_IMAGE_PLATFORM_INVALID')
        return dict(manifestDigest=entries[0]['digest'], configDigest='', index=True)
    if media not in ('application/vnd.oci.image.manifest.v1+json', 'application/vnd.docker.distribution.manifest.v2+json'):
        raise ValueError('APPLICATION_REGISTRY_MANIFEST_UNSUPPORTED')
    config = value['config']['digest']
    if not DIGEST.fullmatch(config):
        raise ValueError('APPLICATION_REGISTRY_MANIFEST_INVALID')
    return dict(manifestDigest=actual, configDigest=config, index=False)


def registry_config(raw, descriptor, reference, platform, legacy=None):
    if (not isinstance(raw, str) or len(raw.encode()) > 8 * 1024 * 1024 or
            'sha256:' + hashlib.sha256(raw.encode()).hexdigest() != descriptor['configDigest']):
        raise ValueError('APPLICATION_REGISTRY_CONFIG_DIGEST_INVALID')
    config = json.loads(raw)
    if any(config.get(key) is not None and config[key] != value for key, value in platform.items()):
        return {}
    config_platform = image_platform(config)
    if any(config_platform.get(key) != value for key, value in platform.items()):
        return {}
    if legacy and descriptor['configDigest'] != legacy['imageId']:
        raise ValueError('APPLICATION_IMAGE_IDENTITY_INVALID')
    return dict(imageId=descriptor['configDigest'], platform=config_platform,
                registry=dict(reference=normalize_image(reference).split('@')[0], manifestDigest=descriptor['manifestDigest']))


def prepared_image(registry, offline, legacy=None):
    image = dict(registry or legacy or offline)
    if not image:
        raise ValueError('APPLICATION_IMAGE_NOT_LOCKED')
    if offline and offline['imageId'] == image['imageId'] and offline['platform'] == image['platform']:
        image['archive'] = offline['archive']
    return image


def prepared_lock(hostvars):
    placements, identities = {}, {}
    for host in hostvars.values():
        for key, value in host.get('platform_application_image_preparations', {}).items():
            image = value['image']
            identity = (normalize_image(value['reference']), json.dumps(image['platform'], sort_keys=True))
            if identity in identities and identities[identity] != image['imageId']:
                raise ValueError('APPLICATION_IMAGE_IDENTITY_CONFLICT')
            identities[identity] = image['imageId']
            placements[key] = value
    return dict(apiVersion='platform.installer/container-images/v1alpha2', placements=placements)


def docker_save_image(path, reference):
    """Inspect one Docker-save image without extracting or loading its layers."""
    reference = normalize_image(reference)
    # A Docker-save config digest does not prove a registry manifest digest.
    if '@' in reference:
        raise ValueError('APPLICATION_IMAGE_ARCHIVE_DIGEST_UNPROVEN')
    with tarfile.open(path, 'r:*') as archive:
        members = {}
        for member in archive:
            name = member.name.rstrip('/')
            if (not name or name.startswith('/') or '\\' in name or
                    any(part in ('', '.', '..') for part in name.split('/')) or
                    name in members or not (member.isfile() or member.isdir())):
                raise ValueError('APPLICATION_IMAGE_ARCHIVE_INVALID')
            members[name] = member

        def read_json(name):
            member = members.get(name)
            if not member or not member.isfile() or member.size > 8 * 1024 * 1024:
                raise ValueError('APPLICATION_IMAGE_ARCHIVE_INVALID')
            raw = archive.extractfile(member).read()
            return raw, json.loads(raw)

        _, manifest = read_json('manifest.json')
        if not isinstance(manifest, list):
            raise ValueError('APPLICATION_IMAGE_ARCHIVE_INVALID')
        matches = [item for item in manifest if isinstance(item, dict) and
                   reference in [normalize_image(tag) for tag in item.get('RepoTags') or []]]
        # A single-image input also permits the explicitly supplied release alias.
        if not matches and len(manifest) == 1:
            matches = manifest
        if len(matches) != 1:
            raise ValueError('APPLICATION_IMAGE_ARCHIVE_AMBIGUOUS')
        entry = matches[0]
        raw, config = read_json(entry['Config'])
        layers = entry.get('Layers', [])
        diff_ids = config.get('rootfs', {}).get('diff_ids', [])
        if not isinstance(layers, list) or len(layers) != len(diff_ids):
            raise ValueError('APPLICATION_IMAGE_ARCHIVE_INVALID')
        for name, expected in zip(layers, diff_ids):
            member = members.get(name)
            if not member or not member.isfile() or not DIGEST.fullmatch(expected):
                raise ValueError('APPLICATION_IMAGE_ARCHIVE_INVALID')
            sha = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    sha.update(chunk)
            if 'sha256:' + sha.hexdigest() != expected:
                raise ValueError('APPLICATION_IMAGE_ARCHIVE_LAYER_INVALID')
        return dict(reference=reference, platform=image_platform(config),
                    imageId='sha256:' + hashlib.sha256(raw).hexdigest())

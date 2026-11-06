"""Read-only validation of the approved PKI projection before a managed Apply."""

import grp
import hashlib
import os
from pathlib import Path
import pwd
import stat
import subprocess

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.pki_resolution import materialization_fingerprint


FILES = (
    ('ca-chain.pem', 'ca.crt', 0o644),
    ('certificate.pem', 'leaf.crt', 0o644),
    ('private-key.pem', 'leaf.key', 0o600),
    ('keystore.p12', 'keystore.p12', 0o600),
    ('truststore.p12', 'truststore.p12', 0o600),
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def regular(path, owner, group, mode):
    info = path.lstat()
    if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or
            info.st_uid != owner or info.st_gid != group or
            stat.S_IMODE(info.st_mode) != mode or not 0 < info.st_size <= 1048576):
        raise ValueError('Invalid PKI file')
    return path.read_bytes()


def run(*args, data=None):
    return subprocess.run(list(map(str, args)), input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, check=True, timeout=15).stdout


def source(args, uid, gid):
    root = Path(args['source_root'])
    expected = {}
    for plan in args['plans']:
        request = root / 'requests' / plan['requestId']
        authority = root / 'authorities' / plan['authorityId']
        if os.path.lexists(root / 'reissues' / (plan['requestId'] + '.fingerprint')):
            raise ValueError('Pending PKI reissue')
        request_fingerprint = regular(request / 'request-fingerprint', uid, gid, 0o600).decode('ascii').strip()
        if materialization_fingerprint(request_fingerprint, plan) != plan['materializationFingerprint']:
            raise ValueError('PKI request fingerprint mismatch')
        if plan['requestId'] not in expected:
            paths = [authority / FILES[0][1], *(request / entry[1] for entry in FILES[1:])]
            expected[plan['requestId']] = [digest(regular(path, uid, gid, 0o600)) for path in paths]
            ca, leaf, key, keystore, truststore = paths
            run('openssl', 'verify', '-CAfile', ca, leaf)
            public_key = run('openssl', 'pkey', '-in', key, '-passin', 'pass:', '-pubout')
            if public_key != run('openssl', 'x509', '-in', leaf, '-pubkey', '-noout'):
                raise ValueError('PKI key mismatch')
            password_file = args['secret_files'][plan['storePasswordSecretRef']]
            for store, certificate, alias in ((keystore, leaf, plan['keyAlias']),
                                               (truststore, ca, plan['trustAlias'])):
                stored = run('keytool', '-exportcert', '-storetype', 'PKCS12', '-keystore', store,
                             '-alias', alias, '-storepass:file', password_file)
                if stored != run('openssl', 'x509', '-in', certificate, '-outform', 'DER'):
                    raise ValueError('PKI store mismatch')
            stored_key = run('openssl', 'pkcs12', '-in', keystore, '-passin', 'file:' + password_file,
                             '-nocerts', '-nodes')
            if public_key != run('openssl', 'pkey', '-pubout', data=stored_key):
                raise ValueError('PKI store key mismatch')
    return expected


def target(args, uid, gid):
    token = digest(args['project_id'].encode())
    for plan in args['plans']:
        directory = Path(plan['targetDirectory'])
        info = directory.lstat()
        if (directory.resolve() != directory or not stat.S_ISDIR(info.st_mode) or
                (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (uid, gid, 0o700)):
            return False
        actual = [digest(regular(directory / name, uid, gid, mode)) for name, _, mode in FILES]
        if actual != args['expected'].get(plan['requestId']):
            return False
        marker = regular(directory / 'materialization-fingerprint', uid, gid, 0o644)
        if marker != (plan['materializationFingerprint'] + '\n').encode():
            return False
        anchor = 'platform-installer-%s-%s.crt' % (token, digest(plan['authorityId'].encode()))
        if digest(regular(Path('/etc/pki/ca-trust/source/anchors') / anchor, 0, 0, 0o644)) != actual[0]:
            return False
        run('openssl', 'verify', directory / 'certificate.pem')
    return True


def main():
    module = AnsibleModule(argument_spec=dict(
        plans=dict(type='list', elements='dict', required=True),
        project_id=dict(type='str', required=True),
        owner=dict(type='str', required=True),
        group=dict(type='str', required=True),
        source_root=dict(type='path'),
        secret_files=dict(type='dict', default={}, no_log=True),
        expected=dict(type='dict', default={}, no_log=True),
    ), supports_check_mode=True)
    args = module.params
    try:
        uid = pwd.getpwnam(args['owner']).pw_uid
        gid = grp.getgrnam(args['group']).gr_gid
        if args['source_root']:
            module.exit_json(changed=False, ready=True, expected=source(args, uid, gid))
        module.exit_json(changed=False, ready=target(args, uid, gid))
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError):
        module.exit_json(changed=False, ready=False)


if __name__ == '__main__':
    main()

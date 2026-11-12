#!/usr/bin/python
"""Private bind files for the actual rootless container UID, without secret output."""
import os
import pwd
import re
import stat
import tempfile
from ansible.module_utils.basic import AnsibleModule


def read_map(path):
    with open(path, encoding='ascii') as stream:
        return [list(map(int, line.split())) for line in stream]


def mapped(path, identity):
    return map_identity(read_map(path), identity)


def map_identity(rows, identity):
    for inside, outside, length in rows:
        if inside <= identity < inside+length:
            return outside+identity-inside
    raise ValueError()


def custody(path, owners, directory=False):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
        raise ValueError()
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError()
    return info


def write(path, content, uid, gid):
    if os.path.lexists(path):
        info = custody(path, {uid})
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError()
        with open(path, 'rb') as stream:
            if stream.read() == content:
                return False
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def inspect_identity(args, accounts):
    name = args['account']
    if name not in accounts:
        account = pwd.getpwnam(name)
        with open('/run/user/%s/docker.pid' % account.pw_uid, encoding='ascii') as stream:
            pid = int(stream.read().strip())
        uid_map = read_map('/proc/%s/uid_map' % pid)
        gid_map = read_map('/proc/%s/gid_map' % pid)
        if map_identity(uid_map, 0) != account.pw_uid:
            raise ValueError()
        accounts[name] = account, uid_map, gid_map
    account, uid_map, gid_map = accounts[name]
    if not re.fullmatch(r'[0-9]+:[0-9]+', args['user']):
        raise ValueError()
    inside_uid, inside_gid = map(int, args['user'].split(':'))
    uid = map_identity(uid_map, inside_uid)
    gid = map_identity(gid_map, inside_gid)
    root = args['instance_path']
    if not root.startswith(account.pw_dir+'/') or os.path.realpath(root) != root:
        raise ValueError()
    current = root
    while current != account.pw_dir:
        if os.path.lexists(current):
            custody(current, {account.pw_uid}, directory=True)
        current = os.path.dirname(current)
    payloads = {}
    if args['agent_required'] or args['agent'] or args['role_id'] or args['ca']:
        payloads['vault'] = {'role-id': args['role_id'].encode(), 'agent.hcl': args['agent'].encode(), 'ca.pem': args['ca'].encode()}
    if args['pki_plans']:
        if len(args['pki_plans']) != 1:
            raise ValueError()
        plan = args['pki_plans'][0]
        source = plan['targetDirectory']
        if not source.startswith('/etc/platform-installer/pki/') or os.path.realpath(source) != source:
            raise ValueError()
        payloads['pki'] = {}
        for name in ('keystore.p12', 'truststore.p12', 'ca-chain.pem', 'certificate.pem', 'private-key.pem'):
            path = source+'/'+name
            info = custody(path, {0})
            if not stat.S_ISREG(info.st_mode) or info.st_size > 1048576:
                raise ValueError()
            with open(path, 'rb') as stream:
                payloads['pki'][name] = stream.read(1048577)
    for name, contents in payloads.items():
        directory = root+'/'+name
        if os.path.lexists(directory):
            info = custody(directory, {uid}, directory=True)
            if info.st_mode & 0o077:
                raise ValueError()
            for filename in contents:
                path = directory+'/'+filename
                if os.path.lexists(path):
                    info = custody(path, {uid})
                    if info.st_mode & 0o077 or not stat.S_ISREG(info.st_mode):
                        raise ValueError()
    return uid, gid, payloads


def main():
    module = AnsibleModule(argument_spec=dict(account=dict(), user=dict(default='0:0'),
        instance_path=dict(), role_id=dict(default='', no_log=True), ca=dict(default=''),
        agent=dict(default=''), agent_required=dict(type='bool', default=False),
        pki_plans=dict(type='list', elements='dict', default=[]), preflight=dict(type='bool', default=False),
        placements=dict(type='list', elements='dict')), supports_check_mode=True)
    try:
        args = module.params
        if args['placements'] is not None:
            if not args['preflight']:
                raise ValueError()
            accounts = {}
            for index, placement in enumerate(args['placements']):
                try:
                    inspect_identity(dict(args, **placement), accounts)
                except (ValueError, KeyError, OSError, TypeError):
                    module.fail_json(msg='APPLICATION_PRIVATE_IDENTITY_MATERIALIZATION_INVALID',
                                     placement_index=index)
            module.exit_json(changed=False)
        if not args['account'] or not args['instance_path']:
            raise ValueError()
        uid, gid, payloads = inspect_identity(args, {})
        root = args['instance_path']
        if args['preflight'] or module.check_mode:
            module.exit_json(changed=False, host_uid=uid, host_gid=gid)
        changed_volumes = []
        for name, contents in payloads.items():
            volume_changed = False
            directory = root+'/'+name
            if not os.path.exists(directory):
                os.mkdir(directory, 0o700)
                os.chown(directory, uid, gid)
                volume_changed = True
            for filename, content in contents.items():
                if not content:
                    raise ValueError()
                volume_changed = write(directory+'/'+filename, content, uid, gid) or volume_changed
            if volume_changed:
                changed_volumes.append(directory)
        module.exit_json(changed=bool(changed_volumes), changed_volumes=changed_volumes, host_uid=uid, host_gid=gid)
    except (ValueError, KeyError, OSError):
        module.fail_json(msg='APPLICATION_PRIVATE_IDENTITY_MATERIALIZATION_INVALID')


if __name__ == '__main__':
    main()

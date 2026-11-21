#!/usr/bin/python
"""Private bind files for the actual rootless container UID, without secret output."""
import os
import base64
import hashlib
import pwd
import re
import secrets
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


def write_configs(account_name, root, files, check_mode=False):
    """Install the preflight bytes in one module call, with guarded atomic writes."""
    account = pwd.getpwnam(account_name)
    if not os.path.isabs(root) or root == '/' or os.path.realpath(root) != root:
        raise ValueError()
    current = root
    boundary = account.pw_dir if root.startswith(account.pw_dir + '/') else '/'
    while current != boundary:
        if os.path.lexists(current):
            if current == root or boundary == account.pw_dir:
                custody(current, {account.pw_uid}, directory=True)
            else:
                info = os.lstat(current)
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                    raise ValueError()
        elif not check_mode:
            raise ValueError()
        current = os.path.dirname(current)
    prepared, destinations = [], set()
    for item in files:
        relative = item['destination']
        if (not isinstance(relative, str) or '\x00' in relative or
                any(part in ('', '.', '..') for part in relative.split('/'))):
            raise ValueError()
        if relative in destinations:
            raise ValueError()
        destinations.add(relative)
        raw = (base64.b64decode(item['content'], validate=True) if item.get('encoding') == 'base64'
               else item['content'].encode('utf-8'))
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError()
        mode = int(item.get('mode', '0644'), 8)
        if mode & ~0o777 or mode & 0o022:
            raise ValueError()
        prepared.append((relative, raw, mode))
    changed = []
    for relative, raw, mode in prepared:
        path = root + '/config/' + relative
        if check_mode and not os.path.exists(os.path.dirname(path)):
            if os.path.realpath(os.path.dirname(path)) != os.path.dirname(path):
                raise ValueError()
            changed.append(path)
            continue
        parts = (root + '/config/' + relative).split('/')[1:]
        parent = os.open('/', os.O_DIRECTORY | os.O_NOFOLLOW)
        gid = account.pw_gid
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            if os.fstat(parent).st_uid != account.pw_uid:
                raise ValueError()
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            except FileNotFoundError:
                same = False
            else:
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != account.pw_uid:
                        raise ValueError()
                    gid = info.st_gid
                    same = (stat.S_IMODE(info.st_mode) == mode and stream.read() == raw)
            if same:
                continue
            changed.append(root + '/config/' + relative)
            if check_mode:
                continue
            temporary = '.platform-config-' + secrets.token_hex(16)
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
                with os.fdopen(fd, 'wb') as stream:
                    os.fchown(stream.fileno(), account.pw_uid, gid)
                    stream.write(raw)
                    stream.flush()
                    os.fchmod(stream.fileno(), mode)
                    os.fsync(stream.fileno())
                os.replace(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
        finally:
            os.close(parent)
    return changed


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
        placements=dict(type='list', elements='dict'), config_files=dict(type='list', elements='dict')),
        supports_check_mode=True)
    try:
        args = module.params
        if args['config_files'] is not None:
            changed = write_configs(args['account'], args['instance_path'], args['config_files'], module.check_mode)
            module.exit_json(changed=bool(changed), changed_paths=changed)
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

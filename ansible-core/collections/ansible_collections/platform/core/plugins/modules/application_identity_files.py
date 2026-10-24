#!/usr/bin/python
"""Private bind files for the actual rootless container UID, without secret output."""
import os
import pwd
import re
import stat
import tempfile
from ansible.module_utils.basic import AnsibleModule


def mapped(path, identity):
    with open(path, encoding='ascii') as stream:
        rows = [list(map(int, line.split())) for line in stream]
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


def main():
    module = AnsibleModule(argument_spec=dict(account=dict(required=True), user=dict(default='0:0'),
        instance_path=dict(required=True), role_id=dict(default='', no_log=True), ca=dict(default=''),
        agent=dict(default=''), agent_required=dict(type='bool', default=False),
        pki_plans=dict(type='list', elements='dict', default=[]), preflight=dict(type='bool', default=False)), supports_check_mode=True)
    try:
        args = module.params
        account = pwd.getpwnam(args['account'])
        if not re.fullmatch(r'[0-9]+:[0-9]+', args['user']):
            raise ValueError()
        inside_uid, inside_gid = map(int, args['user'].split(':'))
        with open('/run/user/%s/docker.pid' % account.pw_uid, encoding='ascii') as stream:
            pid = int(stream.read().strip())
        uid = mapped('/proc/%s/uid_map' % pid, inside_uid)
        gid = mapped('/proc/%s/gid_map' % pid, inside_gid)
        if mapped('/proc/%s/uid_map' % pid, 0) != account.pw_uid:
            raise ValueError()
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
        if args['preflight'] or module.check_mode:
            module.exit_json(changed=False, host_uid=uid, host_gid=gid)
        changed = False
        for name, contents in payloads.items():
            directory = root+'/'+name
            if not os.path.exists(directory):
                os.mkdir(directory, 0o700)
                os.chown(directory, uid, gid)
                changed = True
            for filename, content in contents.items():
                if not content:
                    raise ValueError()
                changed = write(directory+'/'+filename, content, uid, gid) or changed
        module.exit_json(changed=changed, host_uid=uid, host_gid=gid)
    except (ValueError, KeyError, OSError):
        module.fail_json(msg='APPLICATION_PRIVATE_IDENTITY_MATERIALIZATION_INVALID')


if __name__ == '__main__':
    main()

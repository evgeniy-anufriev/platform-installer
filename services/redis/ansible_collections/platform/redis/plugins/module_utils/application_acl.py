"""Bounded RESP commands and member ownership custody for application ACLs."""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import socket
import ssl
import stat
import tempfile
import time


class ACLFailure(ValueError):
    pass


class Client:
    def __init__(self, address, port, ca, cert, key, timeout=15):
        context = ssl.create_default_context(cafile=ca)
        if cert:
            context.load_cert_chain(cert, key)
        raw = socket.create_connection((address, port), timeout)
        try:
            self.socket = context.wrap_socket(raw, server_hostname=address)
        except Exception:
            raw.close()
            raise
        self.stream = self.socket.makefile('rb')

    def close(self):
        self.stream.close()
        self.socket.close()

    def read(self):
        line = self.stream.readline(65537)
        if not line.endswith(b'\r\n') or len(line) > 65536:
            raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')
        kind, value = line[:1], line[1:-2]
        if kind == b'-':
            # Never return the server's error text: commands may contain hashes.
            raise ACLFailure('REDIS_APPLICATION_COMMAND_FAILED')
        if kind == b'+':
            return value.decode('utf-8')
        if kind == b':':
            return int(value)
        if kind in (b'$', b'*'):
            count = int(value)
            if count == -1:
                return None
            if count < 0 or count > 1048576:
                raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')
            if kind == b'*':
                if count > 4096:
                    raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')
                return [self.read() for _ in range(count)]
            body = self.stream.read(count + 2)
            if len(body) != count + 2 or not body.endswith(b'\r\n'):
                raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')
            return body[:-2].decode('utf-8')
        raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')

    def command(self, *arguments):
        encoded = [str(item).encode('utf-8') for item in arguments]
        payload = b'*%d\r\n' % len(encoded) + b''.join(b'$%d\r\n' % len(item) + item + b'\r\n' for item in encoded)
        self.socket.sendall(payload)
        return self.read()


def private_info(path, directory=False):
    info = os.lstat(path)
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ACLFailure('REDIS_APPLICATION_PATH_UNSAFE')
    return info


@contextlib.contextmanager
def member_lock(directory, timeout=15):
    if os.path.realpath(directory) != os.path.abspath(directory):
        raise ACLFailure('REDIS_APPLICATION_PATH_UNSAFE')
    private_info(directory, True)
    path = os.path.join(directory, '.application-accounts.lock')
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ACLFailure('REDIS_APPLICATION_PATH_UNSAFE')
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ACLFailure('REDIS_APPLICATION_LOCK_TIMEOUT')
                time.sleep(0.05)
        yield
    finally:
        os.close(descriptor)


def read_witness(directory):
    path = os.path.join(directory, 'application-accounts.json')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {}
    with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 1048576:
            raise ACLFailure('REDIS_APPLICATION_PATH_UNSAFE')
        value = json.load(stream)
    if not isinstance(value, dict) or any(not isinstance(key, str) or not isinstance(marker, str) for key, marker in value.items()):
        raise ACLFailure('REDIS_APPLICATION_WITNESS_INVALID')
    return value


def publish_witness(directory, value):
    destination = os.path.join(directory, 'application-accounts.json')
    if os.path.lexists(destination):
        private_info(destination)
    descriptor, temporary = tempfile.mkstemp(prefix='.application-accounts-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def account_state(client, username):
    value = client.command('ACL', 'GETUSER', username)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) % 2:
        raise ACLFailure('REDIS_APPLICATION_RESPONSE_INVALID')
    return dict(zip(value[::2], value[1::2]))


def command_permissions(rules, commands, categories):
    """Compare ordered ACL rules against the selected server's command metadata."""
    result = set()
    for rule in rules:
        if not re.fullmatch(r'[+-]?(?:@[a-z][a-z0-9_-]*|[a-z][a-z0-9]*(?:\|[a-z][a-z0-9-]*)?)', rule):
            raise ACLFailure('REDIS_APPLICATION_GRANTS_INVALID')
        name = rule[1:] if rule[0] in '+-' else rule
        if name == '@all':
            selected = set(commands) | {'@all'}
        elif name.startswith('@'):
            if name[1:] not in categories:
                raise ACLFailure('REDIS_APPLICATION_GRANTS_INVALID')
            selected = {command for command, groups in commands.items() if name in groups}
        else:
            selected = {command for command in commands if command == name or command.startswith(name + '|')}
            if not selected:
                raise ACLFailure('REDIS_APPLICATION_GRANTS_INVALID')
        if rule.startswith('-'):
            result.difference_update(selected)
        else:
            result.update(selected)
    return result


def ensure_account(client, user_client, directory, username, password, marker, listener, grants, mode, verify=False, timeout=15, preflight=False):
    """One locked check/reconcile/save/witness for an owned application account."""
    changed = False
    with member_lock(directory, timeout):
        acl_path = os.path.join(directory, ('sentinel' if listener == 'sentinel' else 'redis') + '.users.acl')
        private_info(acl_path)
        if listener == 'client' and client.command('CONFIG', 'GET', 'aclfile') != ['aclfile', acl_path]:
            raise ACLFailure('REDIS_APPLICATION_ACL_FILE_INVALID')
        if listener == 'sentinel':
            config_path = os.path.join(directory, 'sentinel.conf')
            private_info(config_path)
            descriptor = os.open(config_path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
                configuration = stream.read(1048577)
            paths = re.findall(r'(?m)^aclfile\s+(.+)$', configuration)
            if len(configuration) > 1048576 or paths not in [[acl_path], ['"' + acl_path + '"']]:
                raise ACLFailure('REDIS_APPLICATION_ACL_FILE_INVALID')
        witness = read_witness(directory)
        witness_key = listener + '/' + username
        actual = account_state(client, username)
        if mode == 'managed' and actual is not None and witness.get(witness_key) != marker:
            raise ACLFailure('REDIS_APPLICATION_OWNERSHIP_UNKNOWN')
        if actual is None and (verify or mode == 'existing'):
            raise ACLFailure('REDIS_APPLICATION_ACCOUNT_MISSING')
        if actual is None and witness_key in witness:
            raise ACLFailure('REDIS_APPLICATION_OWNERSHIP_DRIFT')
        expected_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        password_mismatch = actual is not None and actual.get('passwords') != [expected_hash]
        command_tokens = [item if item[0] in '+-' else '+' + item for item in grants['commands']]
        commands, pending = {}, list(client.command('COMMAND'))
        while pending:
            row = pending.pop()
            if not isinstance(row, list) or len(row) < 7:
                raise ACLFailure('REDIS_APPLICATION_METADATA_INVALID')
            children = row[9] if len(row) > 9 else []
            if children:
                pending.extend(children)
            else:
                commands[row[0]] = row[6]
        categories = client.command('ACL', 'CAT')
        expected_commands = command_permissions(command_tokens, commands, categories)
        if actual is None and preflight:
            return False
        tokens = list(command_tokens)
        tokens += ['~' + item for item in grants.get('keys', [])]
        tokens += ['&' + item for item in grants.get('channels', [])]
        if actual is None:
            if client.command('ACL', 'SETUSER', username, 'reset', 'on', '#' + expected_hash, *tokens) != 'OK':
                raise ACLFailure('REDIS_APPLICATION_COMMAND_FAILED')
            changed = True
        else:
            if (not {'on'} <= set(actual.get('flags', [])) or set(actual.get('flags', [])) - {'on', 'sanitize-payload'}
                    or actual.get('selectors') or (password_mismatch and (verify or mode == 'existing'))):
                raise ACLFailure('REDIS_APPLICATION_ACCOUNT_DRIFT')
            actual_commands = actual.get('commands', '').split()
            observed_commands = command_permissions(actual_commands, commands, categories)
            updates = []
            if observed_commands != expected_commands:
                if verify or mode == 'existing':
                    raise ACLFailure('REDIS_APPLICATION_GRANTS_DRIFT' if observed_commands - expected_commands else
                                     'REDIS_APPLICATION_GRANTS_MISSING')
                updates = ['nocommands', *command_tokens]
            if password_mismatch:
                updates.extend(['resetpass', '#' + expected_hash])
            for field, prefix, requested in [('keys', '~', grants.get('keys', [])),
                                              ('channels', '&', grants.get('channels', []))]:
                observed = set(actual.get(field, '').split())
                expected = {prefix + item for item in requested}
                if not observed <= expected:
                    raise ACLFailure('REDIS_APPLICATION_GRANTS_DRIFT')
                missing = sorted(expected - observed)
                if missing:
                    if verify or mode == 'existing':
                        raise ACLFailure('REDIS_APPLICATION_GRANTS_MISSING')
                    updates.extend(missing)
            if updates and not preflight:
                if client.command('ACL', 'SETUSER', username, *updates) != 'OK':
                    raise ACLFailure('REDIS_APPLICATION_COMMAND_FAILED')
                changed = True
        if not (preflight and password_mismatch) and (user_client.command('AUTH', username, password) != 'OK' or (not preflight and 'ping' in grants['commands'] and user_client.command('PING') != 'PONG')):
            raise ACLFailure('REDIS_APPLICATION_LOGIN_FAILED')
        if changed:
            if client.command('ACL', 'SAVE') != 'OK':
                raise ACLFailure('REDIS_APPLICATION_PERSIST_FAILED')
            witness[witness_key] = marker
            publish_witness(directory, witness)
    return changed

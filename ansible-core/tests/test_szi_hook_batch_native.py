"""Provider-owned curl/jq batch runs directly and through the generic Ansible role."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/integration.sh'
STUB = r'''#!/usr/bin/python3
import json, os, pathlib, sys, urllib.parse
p = pathlib.Path(os.environ['STUB_STATE']); state = json.loads(p.read_text())
a = sys.argv[1:]; url = urllib.parse.urlsplit(a[-1]); q = urllib.parse.parse_qs(url.query)
method = a[a.index('--request')+1] if '--request' in a else 'POST'
raw = pathlib.Path(a[a.index('--data-binary')+1][1:]).read_text() if '--data-binary' in a else ''
status = 200; result = {}
if 'openid-connect/token' in url.path:
    state['tokens'] += 1; result = {'access_token': 'stub-token'}
else:
    path = url.path.split('/admin/realms/master/')[-1]; parts = path.split('/')
    state.setdefault('requests', []).append([method, path])
    kind = parts[0]
    if kind not in ['clients', 'groups']:
        raise RuntimeError('UNEXPECTED_RESOURCE')
    if len(parts) == 1 and method == 'GET':
        field = 'clientId' if kind == 'clients' else 'name'
        name = q.get('clientId' if kind == 'clients' else 'search', [''])[0]
        result = [v for v in state[kind].values() if v[field] == name]
    elif len(parts) == 1:
        body = json.loads(raw); name = body.get('clientId', body.get('name'))
        if name == 'second' and state.get('fail_once'):
            state['fail_once'] = False; status = 500
        else:
            state[kind][name] = dict(body, id=name); state['writes'] += 1; status = 201
    elif len(parts) == 2:
        if method == 'GET': result = state[kind][parts[1]]
        else:
            state[kind][parts[1]].update(json.loads(raw)); state['writes'] += 1; status = 204
    elif kind == 'clients' and len(parts) >= 3 and parts[2] == 'roles':
        roles = state.setdefault('roles', {}).setdefault(parts[1], {})
        if method == 'GET': result = list(roles.values())
        else:
            body = json.loads(raw); name = body['name']
            roles[name] = dict(body, id=parts[1]+'-'+name)
            state['writes'] += 1; status = 204 if method == 'PUT' else 201
    else:
        raise RuntimeError('UNEXPECTED_PATH')
p.write_text(json.dumps(state)); pathlib.Path(a[a.index('--output')+1]).write_text(json.dumps(result))
print(status, end='')
'''


@unittest.skipUnless(shutil.which('jq'), 'native jq required')
class SziHookBatchNativeTests(unittest.TestCase):
    def exercise(self, *, ansible=False, fail=False, mismatch=False, roles=False):
        with tempfile.TemporaryDirectory(prefix='qa-szi-hook-batch-') as directory:
            root = Path(directory)
            curl = root / 'curl'
            curl.write_text(STUB)
            curl.chmod(0o700)
            (root / 'state').write_text(json.dumps(dict(tokens=0, writes=0, clients={}, groups={}, fail_once=fail)))
            (root / 'admin').write_text('private-probe-value')
            def invocation(operation, instance, payload, realm='master'):
                return [operation, 'https://stub.invalid', realm, 'admin', instance,
                        'https://' + instance + '.internal', 'https://nginx.internal', json.dumps(payload)]
            model = dict(clientRoles=[dict(name='role-'+str(i)) for i in range(9)]) if roles else {}
            invocations = [invocation('groups', 'library', ['operators']),
                           invocation('client', 'first', model), invocation('client', 'second', model),
                           invocation('groups', 'library', ['after-clients'])]
            if mismatch:
                invocations[1][2] = 'other-realm'
            (root / 'batch.json').write_text(json.dumps(invocations))
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'], STUB_STATE=str(root / 'state'),
                       PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(root / 'admin'),
                       PLATFORM_SCRIPT_BATCH_FILE=str(root / 'batch.json'))
            if ansible:
                play = root / 'probe.yml'
                play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                    environment={'PATH': env['PATH'], 'STUB_STATE': env['STUB_STATE']}, tasks=[{
                        'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                        'vars': {'platform_script_job': dict(id='batch', path=str(SCRIPT), argv=[], invocations=invocations,
                            sourceDigest=hashlib.sha256(SCRIPT.read_bytes()).hexdigest(), workingDirectory=str(root),
                            account=pwd.getpwuid(os.getuid()).pw_name, secretInputs={'admin_password': 'admin'}),
                            'platform_script_secret_files': {'admin': str(root / 'admin')}}}])], sort_keys=False))
                command = ['ansible-playbook', '-i', 'localhost,', str(play)]
                # Role environment supplies its own private batch path.
                env.pop('PLATFORM_SCRIPT_BATCH_FILE')
                env.pop('PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE')
                env['ANSIBLE_COLLECTIONS_PATH'] = str(ROOT / 'ansible-core/collections')
            else:
                command = ['/bin/sh', str(SCRIPT)]
            for iteration in range(1 if mismatch else (3 if fail else 2)):
                result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=90)
                state = json.loads((root / 'state').read_text())
                expected_success = not mismatch and (not fail or iteration > 0)
                self.assertEqual(expected_success, result.returncode == 0, (result.stdout + result.stderr)[-2000:])
                self.assertNotIn('private-probe-value', result.stdout + result.stderr)
                if mismatch:
                    self.assertEqual(0, state['tokens'])
                    self.assertEqual(0, state['writes'])
                    continue
                self.assertEqual(iteration + 1, state['tokens'])
                if fail and iteration == 0:
                    self.assertNotIn('after-clients', state['groups'])
                    self.assertEqual({'first'}, set(state['clients']))
                    continue
                self.assertEqual({'first', 'second'}, set(state['clients']))
                if roles:
                    reads = [request for request in state['requests'] if request[0] == 'GET' and request[1].endswith('/roles')]
                    self.assertEqual(2 * (iteration + 1), len(reads))
                    self.assertEqual(9, len(state['roles']['first']))
                self.assertEqual('https://second.internal', state['clients']['second']['description'])
                self.assertEqual(['https://nginx.internal/second/*'], state['clients']['second']['redirectUris'])
                if ansible:
                    self.assertFalse((root / '.scripts/.secrets/batch').exists())
                    if iteration == 1:
                        self.assertIn('changed=0', result.stdout)
                else:
                    self.assertEqual(iteration == 0 or (fail and iteration == 1), json.loads(result.stdout)['changed'])

    def test_direct_fresh_repeat_uses_one_admin_authentication(self):
        self.exercise()

    def test_role_inventory_is_read_once_per_client_on_create_and_repeat(self):
        self.exercise(roles=True)

    def test_ansible_fresh_repeat_uses_same_generic_path(self):
        self.exercise(ansible=True)

    def test_partial_failure_stops_later_operations_and_repeat_recovers(self):
        self.exercise(fail=True)

    def test_different_auth_context_is_rejected_before_writes(self):
        self.exercise(mismatch=True)

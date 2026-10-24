"""Exercise real shell role reconciliation and authentication recovery with native jq."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/integration.sh'

STUB = r'''#!/usr/bin/env python3
import json,os,pathlib,sys,urllib.parse
p=pathlib.Path(os.environ['STUB_STATE']); s=json.loads(p.read_text())
a=sys.argv[1:]; u=urllib.parse.urlsplit(a[-1]); query=urllib.parse.parse_qs(u.query)
path=u.path.split('/admin/realms/master/')[-1]
method=a[a.index('--request')+1] if '--request' in a else 'POST'
raw=pathlib.Path(a[a.index('--data-binary')+1][1:]).read_text() if '--data-binary' in a else ''
code=200; result={}
if 'openid-connect/token' in u.path:
 body=urllib.parse.parse_qs(raw); user=body['username'][0]
 if user=='admin':
  s['tokens']+=1; result={'access_token':'admin-token-'+str(s['tokens'])}
 else:
  result={'access_token':'user-token'} if body['password'][0]==s['passwords'].get(user) else {'error':'invalid_grant'}
  if 'error' in result:code=400
else:
 config=pathlib.Path(a[a.index('--config')+1]).read_text()
 if 'Bearer admin-token-'+str(s['tokens'])+'"' not in config:code=401
 if path=='clients' and query.get('clientId')==['master-realm']:
  s['protectedReads']+=1
  if s['scenario']=='permanent' or (s['scenario']=='once' and not s['rejected']):
   s['rejected']=True; code=401
 if code==401:result={'error':'unauthorized'}
 elif path=='users':
  name=query['username'][0]; result=[{'id':name,'username':name}]
 elif path.startswith('users/') and path.endswith('/groups'):result=[{'id':'tuz','name':'ТУЗ'}]
 elif path.startswith('users/') and '/role-mappings/' in path:
  if method=='GET':result=s['mappings'].get(path,[])
  else:
   s['mappings'][path]=s['mappings'].get(path,[])+json.loads(raw);s['writes']+=1;code=204
 elif path.startswith('users/'):result={'id':path.split('/')[1],'username':path.split('/')[1]}
 elif path=='groups':result=[{'id':'tuz','name':'ТУЗ'}]
 elif path=='clients':
  name=query['clientId'][0];result=[{'id':name,'clientId':name}]
 elif path.startswith('clients/') and path.endswith('/roles'):
  name=path.split('/')[1];result=[{'id':name+'-role','name':'manage'}]
 elif path.startswith('clients/'):result={'id':path.split('/')[1]}
 elif path=='roles':result=[{'id':'realm-role','name':'realm-access'}]
 else:raise RuntimeError('UNEXPECTED_STUB_CALL: '+path)
p.write_text(json.dumps(s));pathlib.Path(a[a.index('--output')+1]).write_text(json.dumps(result) if code!=204 else '')
print(code,end='')
'''


@unittest.skipUnless(shutil.which('jq'), 'native jq required')
class SziRoleRecoveryTests(unittest.TestCase):
    def exercise(self, scenario, initially_mapped=True):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / 'curl').write_text(STUB)
            (work / 'curl').chmod(0o755)
            state = dict(tokens=0, writes=0, protectedReads=0, rejected=False,
                         scenario=scenario, passwords={'access': 'fixture-user-password'}, mappings={})
            mappings = {'realm': [{'id': 'realm-role', 'name': 'realm-access'}],
                        'clients/account': [{'id': 'account-role', 'name': 'manage'}],
                        'clients/master-realm': [{'id': 'master-realm-role', 'name': 'manage'}]}
            if initially_mapped:
                state['mappings'] = {'users/access/role-mappings/' + k: v for k, v in mappings.items()}
            (work / 'state').write_text(json.dumps(state))
            (work / 'admin').write_text('fixture-admin-password')
            account = dict(id='access', username='access', mode='managed', parameters={
                'groups': ['ТУЗ'], 'roles_file': {'realm_roles': ['realm-access'],
                    'client_roles': {'account': ['manage'], 'master-realm': ['manage']}}})
            (work / 'batch').write_text(json.dumps({'accounts': [account], 'passwords': state['passwords']}))
            env = dict(os.environ, PATH=str(work) + ':' + os.environ['PATH'],
                       STUB_STATE=str(work / 'state'), PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(work / 'admin'),
                       PLATFORM_SCRIPT_SECRET_ACCOUNT_BATCH_FILE=str(work / 'batch'))
            for index in range(2 if scenario != 'permanent' else 1):
                result = subprocess.run(['/bin/sh', str(SCRIPT), 'accounts', 'https://stub.invalid', 'master',
                    'admin', 'keycloak', '', '', '{}'], cwd=work, env=env, capture_output=True, text=True, timeout=30)
                output = json.loads(result.stdout)
                saved = json.loads((work / 'state').read_text())
                if scenario == 'permanent':
                    self.assertEqual(1, result.returncode)
                    self.assertEqual(dict(status='error', step=14, http_status=401, curl_exit=0), output)
                    self.assertEqual(2, saved['protectedReads'])
                    self.assertEqual(2, saved['tokens'])
                else:
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertEqual(dict(status='ok', changed=not initially_mapped and index == 0), output)
                    self.assertEqual(state['passwords'], saved['passwords'])
                    self.assertEqual(0 if initially_mapped else 3, saved['writes'])
                diagnostic = result.stdout + result.stderr + ''.join(p.read_text() for p in (work / '.scripts/diagnostics').glob('*.log'))
                self.assertNotIn('fixture-admin-password', diagnostic)
                self.assertNotIn('fixture-user-password', diagnostic)

    def test_existing_roles_repeat_without_changes(self):
        self.exercise('none')

    def test_missing_role_assignments_are_added_once(self):
        self.exercise('none', initially_mapped=False)

    def test_one_unauthorized_subshell_request_reauthenticates_and_repeats(self):
        self.exercise('once')

    def test_persistent_unauthorized_stops_after_one_retry_and_reports_401(self):
        self.exercise('permanent')

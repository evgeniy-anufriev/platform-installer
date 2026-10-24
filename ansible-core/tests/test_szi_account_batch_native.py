"""Run the provider shell with curl replaced by a local deterministic REST stub."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/integration.sh'


@unittest.skipUnless(shutil.which('jq'), 'native jq required')
class SziAccountBatchTests(unittest.TestCase):
    def test_client_name_create_repair_and_repeat_preserve_identity_and_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            curl = work / 'curl'
            curl.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys,urllib.parse
p=pathlib.Path(os.environ['STUB_STATE']); s=json.loads(p.read_text()) if p.exists() else {'writes':0}
a=sys.argv[1:]; path=urllib.parse.urlsplit(a[-1]); method=a[a.index('--request')+1] if '--request' in a else 'POST'
body=json.loads(pathlib.Path(a[a.index('--data-binary')+1][1:]).read_text()) if '--data-binary' in a and 'openid-connect/token' not in path.path else None
result={}; status=200
if 'openid-connect/token' in path.path:result={'access_token':'stub-token'}
elif path.path.endswith('/client-secret'):result={'value':s['client']['secret']}
elif path.path.endswith('/clients'):
 if method=='POST':s['client']=dict(body,id='stable-client-uuid',attributes={});s['writes']+=1;status=201
 else:result=[s['client']] if 'client' in s else []
elif path.path.endswith('/clients/stable-client-uuid'):
 if method=='PUT':s['client'].update(body);s['writes']+=1;status=204
 else:result=s['client']
else:raise RuntimeError('UNEXPECTED_STUB_CALL')
p.write_text(json.dumps(s));pathlib.Path(a[a.index('--output')+1]).write_text('' if status in (201,204) else json.dumps(result));print(status,end='')
''')
            curl.chmod(0o755)
            (work / 'admin').write_text('fixture-admin')
            (work / 'secret').write_text('fixture-client-secret')
            env = dict(os.environ, PATH=str(work)+':'+os.environ['PATH'], STUB_STATE=str(work/'state'),
                       PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(work/'admin'),
                       PLATFORM_SCRIPT_SECRET_CLIENT_SECRET_FILE=str(work/'secret'))
            for phase, changed in [('create', True), ('repair', True), ('repeat', False)]:
                if phase == 'repair':
                    state = json.loads((work/'state').read_text())
                    state['client']['name'] = None
                    state['client']['serviceAccountsEnabled'] = False
                    (work/'state').write_text(json.dumps(state))
                result = subprocess.run(['/bin/sh', str(SCRIPT), 'client', 'https://stub.invalid', 'master', 'admin',
                    'grant-access', 'http://grant.internal', 'https://nginx.internal',
                    '{"publicClient":false,"directAccessGrantsEnabled":true,"serviceAccountsEnabled":true}'], env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, phase)
                self.assertEqual({'status':'ok','changed':changed}, json.loads(result.stdout))
                self.assertNotIn('fixture-client-secret', result.stdout+result.stderr)
                state = json.loads((work/'state').read_text())
                self.assertEqual('grant-access', state['client']['name'])
                self.assertTrue(state['client']['serviceAccountsEnabled'])
                self.assertEqual('stable-client-uuid', state['client']['id'])
                self.assertEqual('fixture-client-secret', state['client']['secret'])
            self.assertEqual(2, state['writes'])

    def test_two_new_accounts_receive_passwords(self):
        self.exercise(False)

    def test_redirected_rest_failure_keeps_safe_diagnostics(self):
        self.exercise(True)

    def exercise(self, reject_reset):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            curl = work/'curl'
            curl.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys,urllib.parse
p=pathlib.Path(os.environ['STUB_STATE']); state=json.loads(p.read_text()) if p.exists() else {}
a=sys.argv[1:]; url=a[-1]; path=urllib.parse.urlsplit(url); body=None; status=200; result={}
method=a[a.index('--request')+1] if '--request' in a else 'POST'
if '--data-binary' in a:
 raw=pathlib.Path(a[a.index('--data-binary')+1][1:]).read_text()
 body=urllib.parse.parse_qs(raw) if 'openid-connect/token' in path.path else json.loads(raw)
if 'openid-connect/token' in path.path:
 user=body['username'][0]
 if user=='admin' or state.get(user,{}).get('password')==body['password'][0]:result={'access_token':'stub'}
 else:
  pathlib.Path(os.environ['STUB_INVALID_LOGIN_LOG']).write_text(user);status=400;result={'error':'invalid_grant'}
elif path.path.endswith('/users'):
 if method=='POST':state[body['username']]={'id':body['username']};status=201
 else:
  user=urllib.parse.parse_qs(path.query)['username'][0]
  result=[dict(username=user,id=user)] if user in state else []
elif path.path.endswith('/reset-password'):
 if os.environ['STUB_REJECT_RESET']=='1':status=400;result={'error':'stub rejection'}
 else:
  user=path.path.split('/')[-2];state[user]['password']=body['value'];status=204
elif path.path.endswith('/groups'):result=[]
elif '/users/' in path.path:
 user=path.path.split('/')[-1];result={'id':user,'username':user}
else:raise RuntimeError('UNEXPECTED_STUB_CALL')
p.write_text(json.dumps(state))
pathlib.Path(a[a.index('--output')+1]).write_text('' if status in (201,204) else json.dumps(result))
print(status,end='')
''', encoding='utf-8')
            curl.chmod(0o755)
            (work/'admin').write_text('stub-admin')
            (work/'batch').write_text(json.dumps({'accounts':[dict(id=k,username=k,mode='managed',parameters={}) for k in ['audit','access']], 'passwords':{'audit':'stub-audit','access':'stub-access'}}))
            env=dict(os.environ, PATH=str(work)+':'+os.environ['PATH'], STUB_STATE=str(work/'state'), STUB_INVALID_LOGIN_LOG=str(work/'invalid-login'), STUB_REJECT_RESET='1' if reject_reset else '0',
                     PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(work/'admin'),
                     PLATFORM_SCRIPT_SECRET_ACCOUNT_BATCH_FILE=str(work/'batch'))
            result=subprocess.run(['/bin/sh',str(SCRIPT),'accounts','https://stub.invalid','master','admin','keycloak','','','{}'],env=env,capture_output=True,text=True,timeout=30)
            self.assertFalse((work/'invalid-login').exists(), 'Do not probe an account before its initial password is set')
            if reject_reset:
                self.assertEqual(1,result.returncode)
                self.assertEqual({'status':'error','step':30,'http_status':400,'curl_exit':0},json.loads(result.stdout))
                return
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertEqual({'status':'ok','changed':True},json.loads(result.stdout))
            self.assertEqual({'audit','access'},set(json.loads((work/'state').read_text())))

            repeat=subprocess.run(['/bin/sh',str(SCRIPT),'accounts','https://stub.invalid','master','admin','keycloak','','','{}'],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(0,repeat.returncode,repeat.stdout+repeat.stderr)
            self.assertEqual({'status':'ok','changed':False},json.loads(repeat.stdout))
            self.assertFalse((work/'invalid-login').exists())

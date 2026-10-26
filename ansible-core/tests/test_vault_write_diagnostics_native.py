"""Exercise private URI failure handling against a loopback HTTP fixture."""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

import yaml

ROOT=Path(__file__).resolve().parents[2]
VAULT=ROOT/'services/vault'
TASKS=VAULT/'ansible_collections/platform/vault/roles/application_provider/tasks/document.yml'


@unittest.skipUnless(shutil.which('ansible-playbook'),'native Ansible required')
class VaultWriteDiagnosticsTests(unittest.TestCase):
    def test_delegated_cas_retry_preserves_intervening_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copyfile('/etc/pki/tls/certs/ca-bundle.crt',Path(folder)/'vault-provider-ca.pem')
            requests=[]
            state={'version':2,'data':{'_platform_owner':'owner','field':'old','foreign':'retained'}}
            class Handler(http.server.BaseHTTPRequestHandler):
                def send(self,status,value):
                    self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(json.dumps(value).encode())
                def do_GET(self):
                    requests.append('GET')
                    self.send(200,{'data':{'data':state['data'],'metadata':{'version':state['version']}}})
                def do_PATCH(self):
                    requests.append('PATCH')
                    value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    if value['options']['cas']!=state['version']:
                        self.send(400,{'errors':['check-and-set parameter did not match the current version']});return
                    state['data'].update(value['data']);state['version']+=1
                    self.send(200,{'data':{'version':state['version']}})
                def log_message(self,*args):pass
            server=http.server.HTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                key='provider:secret/document'
                document={'mount':'secret','document':'document','owner':'owner'}
                variables={'platform_application_vault_runtime':{'provider':{'url':'http://127.0.0.1:'+str(server.server_port),'token':'synthetic-private-token'}},
                    'platform_application_secret_root':folder,
                    'platform_application_vault_documents':{key:{'status':200,'json':{'data':{'data':{'_platform_owner':'owner','field':'old'},'metadata':{'version':1}}}}},
                    'platform_application_vault_values':{key:{'field':'synthetic-private-value'}}}
                play=[{'hosts':'consumer','gather_facts':False,'vars':variables,'tasks':[{
                    'ansible.builtin.include_role':{'name':'platform.vault.application_provider','tasks_from':'library',
                        'apply':{'delegate_to':'localhost','delegate_facts':True,'become':False}},
                    'loop':[{'providerId':'provider','documents':[document]}],
                    'loop_control':{'loop_var':'platform_vault_application_job'}}]}]
                path=Path(folder)/'play.yml';path.write_text(yaml.safe_dump(play))
                inventory=Path(folder)/'hosts';inventory.write_text('consumer ansible_connection=local ansible_python_interpreter=/nonexistent-consumer-python\nlocalhost ansible_connection=local\n')
                result=subprocess.run(['ansible-playbook','-i',str(inventory),str(path)],capture_output=True,text=True,timeout=60,
                    env=dict(os.environ,ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg'),ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections')+':'+str(VAULT)))
                output=result.stdout+result.stderr
                self.assertEqual(0,result.returncode,output)
                self.assertEqual(['PATCH','GET','PATCH'],requests)
                self.assertEqual({'_platform_owner':'owner','field':'synthetic-private-value','foreign':'retained'},state['data'])
                self.assertEqual(3,state['version'])
                for private in ('synthetic-private-token','synthetic-private-value'):
                    self.assertNotIn(private,output)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_delegated_instance_policy_role_and_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copyfile('/etc/pki/tls/certs/ca-bundle.crt',Path(folder)/'vault-provider-ca.pem')
            requests=[]
            state={}
            class Handler(http.server.BaseHTTPRequestHandler):
                def respond(self):
                    requests.append((self.command,self.path))
                    body=self.rfile.read(int(self.headers.get('Content-Length',0)))
                    if self.command!='GET':
                        state[self.path]=json.loads(body)
                    value=({'role_id':'synthetic-private-role'} if self.path.endswith('/role-id') else state.get(self.path))
                    self.send_response(200 if value is not None else 404)
                    self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(json.dumps({'data':value}).encode())
                do_PUT=respond
                do_POST=respond
                do_GET=respond
                def log_message(self,*args):pass
            server=http.server.HTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                variables={'platform_vault_application_job':{'providerId':'provider','identity':'identity','owner':'owner','policy':'# owner\n','libraryId':'library','instanceId':'instance'},
                    'platform_application_vault_runtime':{'provider':{'url':'http://127.0.0.1:'+str(server.server_port),'token':'synthetic-private-token'}},
                    'platform_application_secret_root':folder,'platform_application_vault_identities':{},
                    'platform_vault_application_token_ttl':3600,'platform_vault_application_token_max_ttl':86400,
                    'application_vault_identity_before':{'results':[{'status':404},{'status':404}]},
                    'application_vault_routes':{'results':[{'stdout':'[{"prefsrc":"192.0.2.1"}]'}]},
                    'application_vault_lxc_addresses':{'results':[{'stdout':'[{"addr_info":[{"family":"inet","scope":"global","local":"10.0.3.1","prefixlen":24}]}]'}]}}
                preflight=yaml.safe_load((TASKS.parent/'preflight.yml').read_text())
                tasks=[t for t in preflight if t['name'] in (
                    'Чтение текущих политики и роли перед изменением Vault',
                    'Отклонение неуправляемой политики или неожиданных политик роли')]
                tasks+=yaml.safe_load((TASKS.parent/'instance.yml').read_text())[5:]
                task_path=Path(folder)/'tasks.yml';task_path.write_text(yaml.safe_dump(tasks))
                play=[{'hosts':'consumer','gather_facts':False,'vars':variables,'tasks':[{
                    'ansible.builtin.include_tasks':{'file':str(task_path),'apply':{'delegate_to':'localhost','delegate_facts':True,'become':False}},
                    'loop':[1,2],'loop_control':{'loop_var':'qa_pass'}},
                    {'ansible.builtin.assert':{'that':"hostvars['localhost'].platform_application_vault_identities['library/instance'].roleId == 'synthetic-private-role'"},'no_log':True}]}]
                path=Path(folder)/'play.yml';path.write_text(yaml.safe_dump(play))
                inventory=Path(folder)/'hosts';inventory.write_text('consumer ansible_connection=local ansible_python_interpreter=/nonexistent-consumer-python\nlocalhost ansible_connection=local\n')
                result=subprocess.run(['ansible-playbook','-i',str(inventory),str(path)],capture_output=True,text=True,timeout=60,
                    env=dict(os.environ,ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg'),ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections')+':'+str(VAULT)))
                output=result.stdout+result.stderr
                self.assertEqual(0,result.returncode,output)
                self.assertEqual(['GET','GET','PUT','POST','GET','GET','GET','GET'],[method for method,_ in requests])
                for private in ('synthetic-private-token','synthetic-private-role'):
                    self.assertNotIn(private,output)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_success_and_redacted_write_rejection(self):
        for status in (200,403,None):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as folder:
                shutil.copyfile('/etc/pki/tls/certs/ca-bundle.crt',Path(folder)/'vault-provider-ca.pem')
                requests=[]
                class Handler(http.server.BaseHTTPRequestHandler):
                    def do_PATCH(self):
                        requests.append(self.path)
                        self.rfile.read(int(self.headers.get('Content-Length',0)))
                        self.send_response(status or 200)
                        self.send_header('Content-Type','application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'errors':['synthetic-private-response']}).encode())
                    def log_message(self,*args):pass
                server=http.server.HTTPServer(('127.0.0.1',0),Handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    key='provider:secret/document'
                    variables={'platform_vault_application_job':{'providerId':'provider'},
                        'platform_application_vault_runtime':{'provider':{'url':'http://127.0.0.1:'+str(server.server_port),'token':'synthetic-private-token'}},
                        'application_vault_document':{'mount':'secret','document':'document','owner':'owner'},
                        'platform_application_secret_root':folder,
                        'platform_application_vault_documents':{key:{'status':200,'json':{'data':{'data':{'_platform_owner':'owner','field':'synthetic-private-value' if status is None else 'old'},'metadata':{'version':1}}}}},
                        'platform_application_vault_values':{key:{'field':'synthetic-private-value'}}}
                    job={'providerId':'provider','documents':[variables['application_vault_document']]}
                    play=[{'hosts':'consumer','gather_facts':False,'vars':variables,'tasks':[{
                        'ansible.builtin.include_role':{'name':'platform.vault.application_provider','tasks_from':'library',
                            'apply':{'delegate_to':'localhost','delegate_facts':True,'become':False}},
                        'loop':[job],'loop_control':{'loop_var':'platform_vault_application_job'}}]}]
                    path=Path(folder)/'play.yml';path.write_text(yaml.safe_dump(play))
                    inventory=Path(folder)/'hosts';inventory.write_text('consumer ansible_connection=local ansible_python_interpreter=/nonexistent-consumer-python\nlocalhost ansible_connection=local\n')
                    result=subprocess.run(['ansible-playbook','-i',str(inventory),str(path)],capture_output=True,text=True,timeout=60,
                        env=dict(os.environ,ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg'),ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections')+':'+str(VAULT)))
                    output=result.stdout+result.stderr
                    self.assertEqual(status==403,result.returncode!=0,output)
                    self.assertEqual([] if status is None else ['/v1/secret/data/document'],requests)
                    for private in ('synthetic-private-response','synthetic-private-token','synthetic-private-value'):
                        self.assertNotIn(private,output)
                    if status==403:
                        self.assertIn('APPLICATION_VAULT_DOCUMENT_WRITE_FAILED',output)
                        self.assertIn('HTTP 403, http',output)
                finally:
                    server.shutdown();server.server_close();thread.join()

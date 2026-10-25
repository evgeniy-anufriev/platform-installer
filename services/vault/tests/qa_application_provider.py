"""Explicit isolated RED OS A4 QA; existing prepared image, no deployed mutations."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import select
import threading
import shutil
import socket
import ssl
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
import yaml

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('a3_native',ROOT/'services/postgresql/tests/qa_application_provider.py')
a3=importlib.util.module_from_spec(spec); spec.loader.exec_module(a3)
ADDRESS='10.0.3.1'
IMAGE='platform-application-connection-probe:qa'
IMAGE_ID='sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb'


def digest(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


class VaultCASProxy:
    """Local TLS forwarder that injects one real KV v2 CAS race into Vault."""
    def __init__(self, host, port, upstream, certificate, private_key):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.upstream=upstream; self.target=''; self.armed=False
        self.injected=False; self.conflict=False; self.race_status=None; self.writes=[]; self.lock=threading.Lock()
        proxy=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def _forward(self, method, path, body, token, content_type):
                headers={'Content-Type':content_type}
                if token: headers['X-Vault-Token']=token
                request=urllib.request.Request(proxy.upstream+path,data=body,method=method,headers=headers)
                try:
                    with urllib.request.urlopen(request,context=ssl._create_unverified_context(),timeout=10) as response:
                        return response.status,response.read(),response.headers.get('Content-Type','application/json')
                except urllib.error.HTTPError as error:
                    return error.code,error.read(),error.headers.get('Content-Type','application/json')
            def _handle(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                token=self.headers.get('X-Vault-Token',''); content_type=self.headers.get('Content-Type','application/json')
                with proxy.lock:
                    inject=proxy.armed and self.command=='PATCH' and self.path==proxy.target
                    if inject: proxy.armed=False
                if inject:
                    payload=json.loads(body)
                    race={'options':{'cas':payload['options']['cas']},'data':{'qa_cas_neighbor':'preserved'}}
                    status,_,_=self._forward('PATCH',self.path,json.dumps(race).encode(),token,'application/merge-patch+json')
                    with proxy.lock: proxy.injected=status==200; proxy.race_status=status
                status,response,response_type=self._forward(self.command,self.path,body,token,content_type)
                if self.command=='PATCH' and self.path==proxy.target:
                    with proxy.lock: proxy.writes.append((status,b'check-and-set' in response.lower()))
                if inject and status==400 and b'check-and-set' in response.lower():
                    with proxy.lock: proxy.conflict=True
                self.send_response(status); self.send_header('Content-Type',response_type)
                self.send_header('Content-Length',str(len(response))); self.send_header('Connection','close'); self.end_headers()
                if response: self.wfile.write(response)
            do_GET=do_POST=do_PATCH=do_DELETE=do_PUT=_handle
        self.server=ThreadingHTTPServer((host,port),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(str(certificate),str(private_key))
        self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def start(self): self.thread.start()
    def arm(self,target):
        with self.lock: self.target=target; self.armed=True; self.injected=False; self.conflict=False; self.race_status=None; self.writes=[]
    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)

class ApplicationVaultQA(a3.ApplicationProviderQA):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server=None
        cls.cas_proxy=None
        cls.output=None
        cls.project=None
        cls.account=pwd.getpwnam('platform-docker')
        cls.docker=['sudo','-n','-u','platform-docker','env','HOME='+cls.account.pw_dir,
                    'XDG_RUNTIME_DIR=/run/user/'+str(cls.account.pw_uid),
                    'DOCKER_HOST=unix:///run/user/'+str(cls.account.pw_uid)+'/docker.sock','docker']
        cls.external=os.environ.get('A4_FULL_SERVICES') == '1'
        cls.tls=cls.secret_root/'tls'; cls.tls.mkdir(mode=0o700)
        pg_address='192.168.56.101' if cls.external else ADDRESS
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(cls.tls/'pg-key.pem'),
            '-out',str(cls.tls/'pg-cert.pem'),'-days','1','-subj','/CN='+pg_address,'-addext','subjectAltName=IP:'+pg_address],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        for source,dest in ((cls.tls/'pg-key.pem',cls.data/'private-key.pem'),(cls.tls/'pg-cert.pem',cls.data/'ca-chain.pem')):
            subprocess.run(['sudo','-n','cp',str(source),str(dest)],check=True)
            subprocess.run(['sudo','-n','chown','postgres:postgres',str(dest)],check=True)
            subprocess.run(['sudo','-n','chmod','600',str(dest)],check=True)
        if cls.external:
            cls.server=None
            cls.node_key=Path('/tmp/a4-full-services/node2-key')
            cls.node2_known_hosts=Path('/tmp/a4-full-services/node2-known-hosts')
            if not cls.node_key.is_file() or not cls.node2_known_hosts.is_file():
                raise RuntimeError('A4_MULT_HOST_SSH_PREREQUISITE')
            cls.token=Path('/tmp/a4-full-services/admin-token').read_text().strip()
            ca=subprocess.run(['sudo','-n','cat','/etc/platform-installer/pki/project-b46aa3f5f57a495f/qa-tls-profile--node1/ca-chain.pem'],capture_output=True,check=True).stdout
            (cls.tls/'vault-ca.pem').write_bytes(ca)
            (cls.tls/'pg-ca.pem').write_bytes((cls.tls/'pg-cert.pem').read_bytes())
            cls.url='https://qa-vault-consumer.qa-renamed.example.internal'
            cls.context=ssl.create_default_context(cafile=str(cls.tls/'vault-ca.pem'))
            if cls.api('sys/auth')['data'].get('approle/',{}).get('type') != 'approle':
                raise RuntimeError('A4_FULL_SERVICES_APPROLE_UNAVAILABLE')
        else:
            with socket.socket() as sock:
                sock.bind((ADDRESS,0)); cls.vport=sock.getsockname()[1]
            with socket.socket() as sock:
                sock.bind((ADDRESS,0)); cls.upstream_port=sock.getsockname()[1]
            cls.server=subprocess.Popen(['vault','server','-dev','-dev-tls','-dev-tls-san='+ADDRESS,
                '-dev-tls-cert-dir='+str(cls.tls),'-dev-listen-address='+ADDRESS+':'+str(cls.upstream_port)],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=dict(os.environ,HOME=str(cls.secret_root)))
            output=bytearray()
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                ready,_,_=select.select([cls.server.stdout],[],[],.1)
                if ready: output.extend(os.read(cls.server.stdout.fileno(),4096))
                if b'Root Token: ' in output and b'\n' in output.split(b'Root Token: ',1)[1]:
                    cls.token=output.split(b'Root Token: ',1)[1].splitlines()[0].decode().strip();break
            else:
                cls.stop_vault()
                super().tearDownClass()
                raise RuntimeError('A4_VAULT_FIXTURE_UNAVAILABLE')
            output.clear()
            def drain():
                for _ in cls.server.stdout:
                    pass
            threading.Thread(target=drain,daemon=True).start()
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(cls.tls/'proxy-key.pem'),
                '-out',str(cls.tls/'proxy-ca.pem'),'-days','1','-subj','/CN='+ADDRESS,'-addext','subjectAltName=IP:'+ADDRESS],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            cls.agent_ca_path=cls.tls/'proxy-ca.pem'
            cls.url='https://'+ADDRESS+':'+str(cls.vport)
            cls.context=ssl.create_default_context(cafile=str(cls.tls/'proxy-ca.pem'))
            cls.cas_proxy=VaultCASProxy(ADDRESS,cls.vport,'https://'+ADDRESS+':'+str(cls.upstream_port),cls.tls/'proxy-ca.pem',cls.tls/'proxy-key.pem')
            cls.cas_proxy.start()
            cls.api('sys/auth/approle','POST',{'type':'approle'})
        if not (cls.tls/'pg-ca.pem').exists():
            (cls.tls/'pg-ca.pem').write_bytes((cls.tls/'pg-cert.pem').read_bytes())
        (cls.tls/'ca-chain.pem').write_bytes((cls.tls/'pg-ca.pem').read_bytes()+cls.agent_ca_path.read_bytes())

    @classmethod
    def api(cls,path,method='GET',body=None,token=None):
        data=json.dumps(body).encode() if body is not None else None
        headers={'Content-Type':'application/merge-patch+json' if method=='PATCH' else 'application/json'}
        if token is not None or path != 'auth/approle/login':headers['X-Vault-Token']=token or cls.token
        request=urllib.request.Request(cls.url+'/v1/'+path,data=data,method=method,headers=headers)
        with urllib.request.urlopen(request,context=cls.context,timeout=10) as response:
            data=response.read()
            return json.loads(data) if data else {}

    @classmethod
    def stop_vault(cls):
        if cls.cas_proxy:
            cls.cas_proxy.stop()
        if cls.server:
            cls.server.terminate()
            try: cls.server.wait(timeout=10)
            except subprocess.TimeoutExpired: cls.server.kill();cls.server.wait()
        if cls.output:cls.output.close()

    @classmethod
    def cleanup_external_vault(cls):
        if not getattr(cls,'external',False) or not cls.project:
            return
        identity='pla-'+hashlib.sha256((cls.project.name+':sdku:apigateway-sdku').encode()).hexdigest()[:32]
        for path in ('auth/approle/role/'+identity,'sys/policies/acl/'+identity):
            try: cls.api(path,'DELETE')
            except urllib.error.HTTPError as error:
                if error.code != 404: raise
        prefix='sdku'
        for document in (prefix+'/shared',prefix+'/apigateway-sdku/accounts/postgres',cls.project.name+'/other'):
            if document.startswith(prefix+'/'):
                try:
                    current=cls.api('secret/data/'+document)['data']['data']
                except urllib.error.HTTPError as error:
                    if error.code == 404: continue
                    raise
                expected='platform.application/v1:'+cls.project.name+':sdku:'+document
                if current.get('_platform_owner') != expected:
                    continue
            for path in ('secret/metadata/'+document,'secret/data/'+document):
                try: cls.api(path,'DELETE')
                except urllib.error.HTTPError as error:
                    if error.code != 404: raise
    @classmethod
    def tearDownClass(cls):
        if cls.project:
            cleanup_hosts=getattr(cls, 'application_cleanup_hosts',
                (('node1','192.168.56.101'),('node2','192.168.56.102')) if cls.external else (('node1','192.168.56.101'),))
            for host,ip in cleanup_hosts:
                container=cls.project.name+'-apigateway-sdku-'+host
                docker=['sudo','-n','-u','platform-docker','env','HOME=/home/platform-docker','XDG_RUNTIME_DIR=/run/user/1002',
                        'DOCKER_HOST=unix:///run/user/1002/docker.sock','docker','rm','-f',container]
                if host=='node1': subprocess.run(docker,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                else: subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                    '-o','UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                    'platform-automation@'+ip,*docker],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                network=cls.project.name+'-sdku-apigateway-sdku-'+host+'_default'
                inspect=['sudo','-n','-u','platform-docker','env','HOME=/home/platform-docker','XDG_RUNTIME_DIR=/run/user/1002',
                         'DOCKER_HOST=unix:///run/user/1002/docker.sock','docker','network','inspect',network]
                if host=='node1': exists=subprocess.run(inspect,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
                else: exists=subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                    '-o','UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                    'platform-automation@'+ip,*inspect],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
                if exists:
                    remove_network=inspect[:-2]+['rm',network]
                    if host=='node1': subprocess.run(remove_network,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
                    else: subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                        '-o','UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                        'platform-automation@'+ip,*remove_network],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
                root=Path(cls.account.pw_dir)/'.local/share/platform-installer/applications'/cls.project.name
                if root.parent==Path(cls.account.pw_dir)/'.local/share/platform-installer/applications' and root.name.startswith('a4entry-'):
                    remove=['sudo','-n','rm','-rf','--',str(root)]
                    if host=='node1': subprocess.run(remove,check=True)
                    else: subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                        '-o','UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                        'platform-automation@'+ip,*remove],check=True)
                pki=Path('/etc/platform-installer/pki')/cls.project.name
                if pki.parent==Path('/etc/platform-installer/pki') and pki.name.startswith('a4entry-'):
                    remove=['sudo','-n','rm','-rf','--',str(pki)]
                    if host=='node1': subprocess.run(remove,check=True)
                    else: subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
                        '-o','UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                        'platform-automation@'+ip,*remove],check=True)
        cls.cleanup_external_vault()
        cls.stop_vault()
        super().tearDownClass()

    def play_core(self,playbook,success=True):
        result=subprocess.run(['ansible-playbook','-i',str(self.project/'inventory/hosts.yml'),
            str(ROOT/'ansible-core/playbooks'/playbook),'-e','@'+str(self.extra)],env=self.env,
            capture_output=True,timeout=600)
        log=self.secret_root/'last-core.log'; log.write_bytes(result.stdout+result.stderr); log.chmod(0o600)
        if (result.returncode==0)!=success:
            preserved=Path(os.environ.get('A4_PROTECTED_LOG', self.secret_root/'a4-core-last-protected.log'))
            preserved.write_bytes(result.stdout+result.stderr);preserved.chmod(0o600)
            raise AssertionError('A4_CORE_RESULT_UNEXPECTED protected fixture log')
        for path in self.passwords.values():
            self.assertTrue(Path(path).read_bytes() not in result.stdout+result.stderr, 'A4_SECRET_OUTPUT_FORBIDDEN')
        self.assertTrue(self.token.encode() not in result.stdout+result.stderr, 'A4_TOKEN_OUTPUT_FORBIDDEN')
        preserved=Path(os.environ.get('A4_PROTECTED_LOG', self.secret_root/'a4-core-last-protected.log'))
        preserved.write_bytes(result.stdout+result.stderr);preserved.chmod(0o600)
        return result.stdout+result.stderr

    def prepare_application_fixture(self):
        self.__class__.project=self.runtime/('a4entry-'+secrets.token_hex(5))
        shutil.copytree(ROOT/'examples/valid/application-runtime',self.project)
        group_file=self.project/'inventory/group_vars/all/platform-installer.yml'
        group=json.loads(group_file.read_text());desired=group['platform_desired_state']
        pg=json.loads((ROOT/'examples/valid/application-providers/inventory/group_vars/all/platform-installer.yml').read_text())['platform_desired_state']
        desired['serviceDeployments']['postgres-sdku']=copy.deepcopy(pg['serviceDeployments']['postgres-sdku'])
        desired['serviceDeployments']['postgres-sdku']['configuration']['port']=self.port
        if self.external:
            desired['endpointGroups']={'qa-shared-endpoint':{'address':{'domain':'qa-renamed.example.internal','wildcard':False}}}
            desired['serviceDeployments']['qa-vault-consumer']={'serviceType':'vault','mode':'raft-ha','configuration':{'tlsProfile':'apps-tls','port':8300},'endpointGroup':'qa-shared-endpoint'}
        else:
            desired['serviceDeployments']['vault-main']={'serviceType':'vault','mode':'standalone','configuration':{'tlsProfile':'apps-tls','port':self.vport}}
        desired['applicationLibraryDeployments']={'sdku':desired['applicationLibraryDeployments']['sdku']}
        deployment=desired['applicationLibraryDeployments']['sdku']
        vault_ref='qa-vault-consumer' if self.external else 'vault-main'
        deployment['bindings']={'database':{'deploymentRef':'postgres-sdku'},'secrets':{'deploymentRef':vault_ref},'application_pki':{'profileRef':'apps-tls'}}
        deployment['vault_ref']={'binding':'secrets'}
        deployment['resources']={'application-database':{'kind':'postgresql.database','mode':'managed','binding':'database','parameters':{'name':'a4qa'},}}
        deployment['applications']['gateway']['overrides']['parameters']['postgres']={'user':'a4qa_user','password_ref':'gateway-password'}
        deployment['applications']['gateway']['overrides']['ports']={'http':{'container':8080,'published':28281}}
        app=self.project/'application-packages/apigateway/1.0.0'
        defaults_path=app/'roles/application_apigateway/defaults/main.yml'
        definition=json.loads(defaults_path.read_text())['platform_application_definition']
        base=definition['defaults'];base.update(image=IMAGE,command=['/usr/bin/connection-probe'],user='1000:1000',config_files=[],environment={
            'PGHOST':('192.168.56.101' if self.external else ADDRESS),'PGPORT':str(self.port),'PGDATABASE':'a4qa','PGSSLMODE':'verify-ca','PGSSLROOTCERT':'/opt/application/pki/pg-ca.pem',
            'PROBE_PORT':'8080','PROBE_KEYSTORE_PKCS12':'/opt/application/pki/keystore.p12',
            'PROBE_TRUSTSTORE_PKCS12':'/opt/application/pki/truststore.p12'})
        base['parameters']['postgres']={'user':'{{ application_instance_id }}','password_ref':'{{ application_instance_id }}-password'}
        base['accounts']={'postgres':{'mode':'managed','databaseRef':'application-database','credentials':{
            'username':{'source':{'kind':'literal','value':'{{ application_parameters.postgres.user }}'}},
            'password':{'source':{'kind':'runtime_secret_ref','ref':'{{ application_parameters.postgres.password_ref }}'}}}}}
        base['provisioner']={'type':'vault-agent','mode':'process-supervisor','auth':{'method':'approle'},'approle':{'bind_secret_id':False},
            'secrets':{'mount':'secret'},'secret_bindings':{'PGUSER':{'source':{'account':'postgres','field':'username'}},
            'PROBE_VAULT_MARKER':{'source':{'account':'postgres','field':'username'}},
            'PGPASSWORD':{'source':{'account':'postgres','field':'password'}},'PROBE_KEYSTORE_PASSWORD':{'source':{'library_secret':'java_keystore_password'}},
            'PROBE_TRUSTSTORE_PASSWORD':{'source':{'library_secret':'java_keystore_password'}}}}
        definition['connections']={'postgres':{'library_binding':'database','protocol':'tcp'},'vault':{'library_binding':'secrets','protocol':'https'}}
        defaults_path.write_text(json.dumps({'platform_application_definition':definition}))
        manifest_path=app/'application.yml';manifest=json.loads(manifest_path.read_text())
        agent='roles/application_apigateway/templates/agent.hcl.j2'
        manifest['files'] += [agent]
        manifest['render']['agent_template']=agent;manifest_path.write_text(json.dumps(manifest))
        (app/agent).write_text('{{ application_runtime | platform.core.application_agent_config }}\n')
        compose=app/manifest['render']['compose_template']
        content=compose.read_text().replace('entrypoint: {{ application_effective.command | to_json }}',
            'entrypoint: ["/usr/bin/vault", "agent", "-config=/opt/vault/agent.hcl"]')
        content=content[:content.index('    volumes:')]+'''    tmpfs:
      - /run/probe:uid=1000,gid=1000,mode=0700
    volumes:
      - {{ (application_runtime.vault_path ~ ':/opt/vault:ro') | to_json }}
      - {{ (application_runtime.pki_path ~ ':/opt/application/pki:ro') | to_json }}
''';compose.write_text(content)
        library=self.project/'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml'
        lib=json.loads(library.read_text());lib['platform_library_definition']['shared_secrets']={'java_keystore_password':{
            'source':{'kind':'pki_credential','binding':'application_pki','credential':'java_keystore_password'}}};library.write_text(json.dumps(lib))
        inventory_hosts={'node1':{'ansible_connection':'local','ansible_host':('192.168.56.101' if self.external else ADDRESS),'platform_postgresql_user':'postgres'}}
        if self.external:
            inventory_hosts['node2']={'ansible_connection':'ssh','ansible_host':'192.168.56.102','ansible_user':'platform-automation',
                'ansible_private_key_file':'/tmp/a4-full-services/node2-key','ansible_ssh_common_args':'-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts'}
            inventory_hosts['node3']={'ansible_connection':'ssh','ansible_host':'192.168.56.103','ansible_user':'platform-automation',
                'ansible_private_key_file':'/tmp/a4-full-services/node2-key','ansible_ssh_common_args':'-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts'}
        inventory={'all':{'hosts':{'localhost':{'ansible_connection':'local'}},'children':{'platform_targets':{'hosts':inventory_hosts}}}}
        (self.project/'inventory/hosts.yml').write_text(json.dumps(inventory))
        hostvars=self.project/'inventory/host_vars'
        shutil.rmtree(hostvars)
        for host,port in (('node1',8301),('node2',8302),('node3',8303)):
            (hostvars/host).mkdir(parents=True)
            deployments={'docker':{},vault_ref:{'members':{'vault-'+host[-1]:{'configuration':({'port':port} if self.external else {}),'roles':['vault']}}}}
            memberships={'sdku':{}} if host in ('node1','node2') or not self.external else {}
            if host=='node1': deployments['postgres-sdku']={'members':{'pg':{'roles':['database']}}}
            (hostvars/host/'platform-installer.yml').write_text(json.dumps({'platform_application_libraries':memberships,'platform_deployments':deployments}))
        bundle=self.runtime/'image-bundle';archive=bundle/'runtime/artifacts/applications/probe.tar';archive.parent.mkdir(parents=True)
        with open(archive,'wb') as stream:
            subprocess.run(self.docker+['save',IMAGE_ID],stdout=stream,stderr=subprocess.DEVNULL,check=True)
        manifest={'apiVersion':'platform.installer/execution-bundle/v1alpha1','kind':'ExecutionRuntimeBundle','components':[
            {'path':'runtime/artifacts/applications/probe.tar','sha256':digest(archive),'size':archive.stat().st_size}]}
        (bundle/'manifest.yaml').write_text(json.dumps(manifest))
        group['platform_artifact_lock']['digest']=digest(bundle/'manifest.yaml')
        group['platform_artifact_lock']['x-container-images']['images']={IMAGE:{'imageId':IMAGE_ID,'platform':{'os':'linux','architecture':'amd64'},
            'archive':{'ref':'runtime/artifacts/applications/probe.tar','sha256':digest(archive),'size':archive.stat().st_size}}}
        group['platform_application_approved_registries']=[];group_file.write_text(json.dumps(group))
        store=self.secret_root/'store-password';store.write_text(secrets.token_hex(20));store.chmod(0o600)
        self.passwords['runtime:pki-store-password']=str(store)
        self.extra=self.secret_root/'extra.json'
        extra_values={'platform_project_root':str(self.project),'platform_service_catalog_path':str(ROOT/'examples/catalog/service-catalog.yml'),
            'platform_postgresql_application_socket':str(self.data),'platform_postgresql_application_secret_root':str(self.secret_root),
            'platform_postgresql_secret_files':self.passwords,'platform_runtime_secret_inputs':[{'purpose':'SERVICE_ADMIN_TOKEN','requirementRef':'si-'+'a'*40,'value':self.token}],
            'platform_execution_bundle_root':str(bundle)}
        if self.external:
            extra_values.update(platform_vault_application_token_ttl=15,platform_vault_application_token_max_ttl=60)
        self.extra.write_text(json.dumps(extra_values));self.extra.chmod(0o600)
        self.env=dict(self.env,ANSIBLE_COLLECTIONS_PATH=':'.join([str(ROOT/'ansible-core/collections'),str(ROOT/'services/postgresql'),str(ROOT/'services/vault')]))
        self.play_core('applications/stages/resolve-runtime.yml')
        # Materialization uses only exact Core-selected plans, and is QA fixture setup.
        wrapper=self.secret_root/'materialize.yml'
        plans='{{ application_snapshot.pki_materialization.materializationPlans }}'
        tasks=[{'ansible.builtin.file':{'path':'{{ item.targetDirectory }}','state':'directory','mode':'0700'},'become':True,
                'loop':plans,'delegate_to':'{{ item.hostId }}'},
            {'ansible.builtin.copy':{'src':str(self.tls/'ca-chain.pem'),'dest':'{{ item.targetDirectory }}/ca-chain.pem','mode':'0644'},'become':True,
             'loop':plans,'delegate_to':'{{ item.hostId }}'},
            {'ansible.builtin.copy':{'src':str(self.tls/'pg-ca.pem'),'dest':'{{ item.targetDirectory }}/pg-ca.pem','mode':'0644'},'become':True,
             'loop':plans,'delegate_to':'{{ item.hostId }}'}]
        subprocess.run(self.pgcmd+['tee','-a',str(self.data/'postgresql.conf')],input=("\nlisten_addresses='0.0.0.0'\n").encode(),stdout=subprocess.DEVNULL,check=True)
        subprocess.run(self.pgcmd+['tee','-a',str(self.data/'pg_hba.conf')],input=b'hostssl all all 192.168.56.0/24 scram-sha-256\nhostssl all all 10.0.3.0/24 scram-sha-256\n',stdout=subprocess.DEVNULL,check=True)
        subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'-l',str(self.data/'server.log'),'-m','fast','-w','restart'],capture_output=True,check=True,timeout=90)
        (self.tls/'pg-key.pem').chmod(0o600)
        (self.tls/'pg-cert.pem').chmod(0o600)
        store_password_bytes=Path(self.passwords['runtime:pki-store-password']).read_bytes()
        for filename in ('keystore.p12','truststore.p12'):
            subprocess.run(['openssl','pkcs12','-export','-in',str(self.tls/'pg-cert.pem'),'-inkey',str(self.tls/'pg-key.pem'),
                '-certfile',str(self.tls/'pg-ca.pem'),'-out',str(self.tls/filename),'-passout','stdin'],input=store_password_bytes,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            (self.tls/filename).chmod(0o600)
            tasks.append({'ansible.builtin.copy':{'src':str(self.tls/filename),'dest':'{{ item.targetDirectory }}/'+filename,'mode':'0600'},
                'become':True,'loop':plans,'delegate_to':'{{ item.hostId }}'})
        wrapper.write_text(yaml.safe_dump([{'import_playbook':str(ROOT/'ansible-core/playbooks/applications/stages/resolve-runtime.yml')},
            {'hosts':'localhost','gather_facts':False,'tasks':tasks}]))
        result=subprocess.run(['ansible-playbook','-i',str(self.project/'inventory/hosts.yml'),str(wrapper),'-e','@'+str(self.extra)],env=self.env,capture_output=True,timeout=300)
        if result.returncode:
            log=Path('/tmp/a4-core-last-protected.log');log.write_bytes(result.stdout+result.stderr);log.chmod(0o600)
            self.fail('A4_PKI_FIXTURE_FAILED protected log /tmp/a4-core-last-protected.log')
    def test_generated_password_uses_normal_apply_and_reuses_published_value(self):
        if self.external:
            self.skipTest('Generated native provider test uses isolated Vault only')
        from runtime_secret_identity import generated_password_ref
        # Exercise the production Vault/provider stages without requiring a probe image.
        subprocess.run(self.pgcmd+['openssl','req','-x509','-newkey','rsa:2048','-nodes',
            '-keyout',str(self.data/'private-key.pem'),'-out',str(self.data/'ca-chain.pem'),
            '-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'],
            capture_output=True,check=True)
        subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'reload'],capture_output=True,check=True)
        trust=self.secret_root/'vault-trust';trust.mkdir(mode=0o700)
        (trust/'ca-chain.pem').write_bytes(Path(self.agent_ca_path).read_bytes())
        job=self.make_job('a4gen',1)
        account=job['accounts'][0]
        account['passwordRef']=generated_password_ref('a4gen','lib','app-0','postgres')
        bindings={'PGUSER':{'source':{'account':'postgres','field':'username'}},
                  'PGPASSWORD':{'source':{'account':'postgres','field':'password'}},
                  'SHARED':{'source':{'library_secret':'marker'}}}
        instance=dict(agentRequired=True,placements={'node1':{}},
            connections={'vault':dict(serviceType='vault',deploymentRef='vault-qa',targets=[
                dict(hostId='node1',port=self.vport,address=ADDRESS,tlsProfileRef='v')])},
            credentialRequirements={'postgres':dict(mode='managed',credentials={
                'username':{'source':{'kind':'literal','value':account['name']}},
                'password':{'source':{'kind':'generated'}}})},secretBindings=bindings)
        row=dict(libraryId='lib',instanceId='app-0',hostId='node1',vaultRef={'binding':'secrets'},
            bindings={'secrets':{'deploymentRef':'vault-qa'}},
            settings={'provisioner':{'secrets':{'mount':'secret'},'secret_bindings':bindings}})
        prepared=dict(snapshot={'project':{'id':'a4gen'},'applicationLibraries':{'libraries':{
            'lib':{'instances':{'app-0':instance},'sharedSecretRequirements':{
                'marker':{'source':{'kind':'runtime_secret_ref','ref':'gateway-password'}}}}}}},
            pki_materialization={'materializationPlans':[dict(hostId='node1',tlsProfileId='v',targetDirectory=str(trust))]})
        libraries,instances=a3.split_provider_jobs([job])
        variables=dict(application_provider_snapshot=prepared,platform_application_rows=[row],
            application_provider_inputs=dict(status='PASS',jobs=[job],libraryJobs=libraries,instanceJobs=instances),
            platform_application_secret_root=str(self.secret_root),platform_application_secret_files=self.passwords,
            platform_postgresql_application_secret_root=str(self.secret_root),platform_postgresql_secret_files=self.passwords,
            platform_postgresql_application_socket=str(self.data),platform_runtime_secret_inputs=[
                dict(purpose='SERVICE_ADMIN_TOKEN',requirementRef='si-'+'a'*40,value=self.token)])
        extra=self.secret_root/'generated-vars.json';extra.write_text(json.dumps(variables));extra.chmod(0o600)
        agent=self.secret_root/'generated-agent.hcl'
        runtime=dict(vault=dict(endpoint_url=self.url,ca_container_path='/opt/vault/ca.pem',auth_mount='auth/approle',
            role_id_container_path='/opt/vault/role-id',env_templates='{{ application_vault_inputs.instanceJobs[0].envTemplates }}'),
            application_command=['/opt/application/run'])
        wrapper=self.secret_root/'generated-apply.yml'
        wrapper.write_text(yaml.safe_dump([
            {'import_playbook':str(ROOT/'ansible-core/playbooks/applications/stages/vault-preflight.yml')},
            {'import_playbook':str(ROOT/'ansible-core/playbooks/applications/stages/provider-stage.yml')},
            dict(hosts='localhost',connection='local',gather_facts=False,vars={'application_runtime':runtime},tasks=[
                {'ansible.builtin.copy':{'content':'{{ application_runtime | platform.core.application_agent_config }}',
                                        'dest':str(agent),'mode':'0600'}}])],sort_keys=False))
        env=dict(self.env,ANSIBLE_COLLECTIONS_PATH=':'.join([str(ROOT/'ansible-core/collections')]+
            [str(ROOT/'services'/service) for service in ('vault','postgresql','redis','clickhouse','kafka')]))
        def apply(success=True):
            result=subprocess.run(['ansible-playbook','-i',str(self.inventory),str(wrapper),'-e','@'+str(extra)],
                env=env,capture_output=True,timeout=300)
            log=self.secret_root/'last-generated.log';log.write_bytes(result.stdout+result.stderr);log.chmod(0o600)
            if (result.returncode == 0) != success:
                preserved=Path(os.environ.get('A4_PROTECTED_LOG',log))
                preserved.write_bytes(log.read_bytes());preserved.chmod(0o600)
                self.fail('GENERATED_NATIVE_STAGE_RESULT protected log')
            self.assertTrue(self.token.encode() not in result.stdout+result.stderr)
            return result.stdout+result.stderr
        document='secret/data/lib/app-0/accounts/postgres'
        self.api(document,'POST',{'data':{'_platform_owner':'foreign-test-fixture','password':secrets.token_urlsafe(32)}})
        apply(success=False)
        self.assertEqual('0',self.sql("SELECT count(*) FROM pg_roles WHERE rolname='a4gen_user_0'"))
        self.api(document.replace('/data/','/metadata/'),'DELETE')
        legacy='secret/data/a4gen/lib/shared'
        self.api(legacy,'POST',{'data':{'retained':'test-owned-legacy-document'}})
        legacy_version=self.api(legacy)['data']['metadata']['version']
        output=apply()
        self.assertTrue('secret/data/lib/shared' in agent.read_text())
        self.assertTrue('a4gen' not in agent.read_text())
        self.assertEqual(legacy_version,self.api(legacy)['data']['metadata']['version'])
        before=self.api(document)['data']
        self.assertTrue(len(before['data']['password']) == 43)
        self.assertTrue(before['data']['password'].encode() not in output)
        output=apply()
        after=self.api(document)['data']
        self.assertTrue(before['data']['password'].encode() not in output)
        self.assertTrue(before['data']['password'] == after['data']['password'])
        self.assertEqual(before['metadata']['version'], after['metadata']['version'])
        # Simulate completed provider ownership but missing password publication.
        pending=dict(after['data']);del pending['password']
        self.api(document,'POST',{'options':{'cas':after['metadata']['version']},'data':pending})
        output=apply()
        repaired=self.api(document)['data']['data']['password']
        self.assertTrue(repaired != before['data']['password'])
        self.assertTrue(repaired.encode() not in output)
        self.assertFalse((self.secret_root/account['passwordRef']).exists())
        print('GENERATED_NATIVE_PROVIDER_VAULT_AGENT_RENDER_REUSE_RETRY_PASS no_container_acceptance')

    def test_a4_full_apply_verify_repeat(self):
        self.prepare_application_fixture()
        self.play_core('applications/apply.yml')
        self.play_core('applications/verify.yml')
        document='secret/data/sdku/apigateway-sdku/accounts/postgres'
        before=self.api(document)['data']['metadata']['version']
        self.api(document,'PATCH',{'options':{'cas':before},'data':{'neighbor':'keep'}})
        before=self.api(document)['data']['metadata']['version']
        repeat=self.play_core('applications/apply.yml')
        self.assertEqual(before,self.api(document)['data']['metadata']['version'])
        self.assertEqual(self.api(document)['data']['data']['neighbor'],'keep')
        self.assertFalse(re.search(rb'changed=[1-9]',repeat), 'A4_REPEAT_NOT_IDEMPOTENT')
        statuses={host:self.probe_status(host) for host in (('node1','node2') if self.external else ('node1',))}
        for host,status in statuses.items():
            self.assertTrue(Path(self.passwords['gateway-password']).read_text() not in json.dumps(status), 'A4_STATUS_SECRET_FORBIDDEN')
            self.assertTrue(Path(self.passwords['runtime:pki-store-password']).read_text() not in json.dumps(status), 'A4_STATUS_SECRET_FORBIDDEN')
            for name in ('pkcs12','pkcs12Client','postgresql','vaultAgent'):
                self.assertEqual(status['checks'][name]['state'],'ok', 'A4_'+host+'_'+name.upper()+'_STATUS_FAILED')
        if self.external:
            time.sleep(20)
            for host in ('node1','node2'):
                renewed=self.probe_status(host)
                self.assertEqual(renewed['checks']['vaultAgent']['state'],'ok','A4_'+host+'_APPROLE_RENEWAL_FAILED')
            print('A4_MULT_HOST_ENDPOINT_AND_APPROLE_RENEWAL_PASS hosts=node1,node2 endpoint=https443')
        print('A4_STATUS_STATES '+','.join(name+'='+statuses['node1']['checks'][name]['state'] for name in ('pkcs12','pkcs12Client','postgresql','vaultAgent')))
        print('A4_NATIVE_APPLY_VERIFY_REPEAT_PASS pg_pkcs12_agent=ok')
        identity='pla-'+hashlib.sha256((self.project.name+':sdku:apigateway-sdku').encode()).hexdigest()[:32]
        role_path='auth/approle/role/'+identity
        role=self.api(role_path)['data']
        self.assertFalse(role['bind_secret_id'])
        role_cidrs={str(__import__('ipaddress').ip_network(x,strict=False)) for x in role['token_bound_cidrs']}
        self.assertIn('127.0.0.1/32',role_cidrs)
        if self.external:self.assertIn('192.168.56.0/24',role_cidrs)
        else:self.assertIn('10.0.3.0/24',role_cidrs)
        role_id=self.api(role_path+'/role-id')['data']['role_id']
        probe_token=self.api('auth/approle/login','POST',{'role_id':role_id})['auth']['client_token']
        try:
            self.assertTrue(self.api(document,token=probe_token)['data']['data']['password']==Path(self.passwords['gateway-password']).read_text())
            self.api('secret/data/'+self.project.name+'/other','POST',{'data':{'value':'neighbor'}})
            with self.assertRaises(urllib.error.HTTPError) as denied:
                self.api('secret/data/'+self.project.name+'/other',token=probe_token)
            self.assertEqual(denied.exception.code,403)
            self.api('auth/token/renew-self','POST',{},token=probe_token)
        finally:
            self.api('auth/token/revoke-self','POST',{},token=probe_token)
        try:
            self.api(role_path,'POST',{'token_bound_cidrs':['192.0.2.0/24']})
            try:
                outside=self.api('auth/approle/login','POST',{'role_id':role_id})['auth']
            except urllib.error.HTTPError as denied:
                self.assertEqual(denied.code,403)
            else:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    self.api(document,token=outside['client_token'])
                self.assertEqual(denied.exception.code,403)
                self.api('auth/token/revoke-accessor','POST',{'accessor':outside['accessor']})
        finally:
            self.api(role_path,'POST',{'token_bound_cidrs':role['token_bound_cidrs']})
        container=self.project.name+'-apigateway-sdku-node1'
        subprocess.run(self.docker+['restart',container],capture_output=True,check=True)
        if self.external:
            subprocess.run(['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o',
                'UserKnownHostsFile=/tmp/a4-full-services/node2-known-hosts','-i','/tmp/a4-full-services/node2-key',
                'platform-automation@192.168.56.102','sudo','-n','-u','platform-docker','env','HOME=/home/platform-docker',
                'XDG_RUNTIME_DIR=/run/user/1002','DOCKER_HOST=unix:///run/user/1002/docker.sock','docker','restart',
                self.project.name+'-apigateway-sdku-node2'],capture_output=True,check=True)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            try:
                status=self.probe_status('node1')
                if all(status['checks'][name]['state']=='ok' for name in ('pkcs12','pkcs12Client','postgresql','vaultAgent')):break
            except (urllib.error.URLError,ConnectionError):pass
            time.sleep(.5)
        else:self.fail('A4_RESTART_STATUS_FAILED')
        if self.external:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                try:
                    status=self.probe_status('node2')
                    if status['checks']['vaultAgent']['state']=='ok':break
                except (urllib.error.URLError,ConnectionError):pass
                time.sleep(.5)
            else:self.fail('A4_NODE2_RESTART_STATUS_FAILED')
        self.assertTrue(role_id==self.api(role_path+'/role-id')['data']['role_id'],'A4_ROLE_ID_CHANGED')
        print('A4_SCOPE_CIDR_RENEW_RESTART_PASS')
        # Force one real Vault KV v2 conflict, then require bounded reconciliation.
        if not self.external:
            before_cas=self.api(document)['data']
            stale_data=dict(before_cas['data']); stale_data['password']='qa-stale-password'
            self.api(document,'POST',{'options':{'cas':before_cas['metadata']['version']},'data':stale_data})
            self.cas_proxy.arm('/v1/'+document)
            try:
                self.play_core('applications/apply.yml')
            except AssertionError:
                print('A4_CAS_PROXY_STATE injected='+str(self.cas_proxy.injected)+' conflict='+str(self.cas_proxy.conflict)+' race_status='+str(self.cas_proxy.race_status)+' writes='+str(self.cas_proxy.writes))
                raise
            self.assertTrue(self.cas_proxy.injected and self.cas_proxy.conflict,'A4_LIVE_CAS_CONFLICT_NOT_OBSERVED')
            after_cas=self.api(document)['data']['data']
            self.assertEqual(after_cas['qa_cas_neighbor'],'preserved','A4_CAS_NEIGHBOR_FIELD_LOST')
            self.assertEqual(after_cas['password'],Path(self.passwords['gateway-password']).read_text(),'A4_CAS_DESIRED_FIELD_NOT_RECONCILED')
            print('A4_LIVE_CAS_CONFLICT_RETRY_PASS neighbor=preserved')
        # Native fail-closed checks: required secret field and private identity symlink.
        current=self.api(document)
        original_data=current['data']['data']
        reduced={key:value for key,value in original_data.items() if key!='password'}
        self.api(document,'POST',{'options':{'cas':current['data']['metadata']['version']},'data':reduced})
        try:
            missing_output=self.play_core('applications/verify.yml',success=False)
            self.assertNotIn(Path(self.passwords['gateway-password']).read_bytes(),missing_output,'A4_SECRET_OUTPUT_FORBIDDEN')
        finally:
            latest=self.api(document)
            self.api(document,'POST',{'options':{'cas':latest['data']['metadata']['version']},'data':original_data})
        instance_root=Path(self.account.pw_dir)/'.local/share/platform-installer/applications'/self.project.name/'sdku'/'apigateway-sdku'/'node1'
        vault_dir=instance_root/'vault'; vault_backup=instance_root/'.a4-vault-private-backup'
        subprocess.run(['sudo','-n','mv',str(vault_dir),str(vault_backup)],check=True)
        try:
            subprocess.run(['sudo','-n','ln','-s','/tmp/a4-unsafe-private-target',str(vault_dir)],check=True)
            unsafe_output=self.play_core('applications/verify.yml',success=False)
            self.assertNotIn(Path(self.passwords['gateway-password']).read_bytes(),unsafe_output,'A4_SECRET_OUTPUT_FORBIDDEN')
        finally:
            subprocess.run(['sudo','-n','rm','-f','--',str(vault_dir)],check=True)
            subprocess.run(['sudo','-n','mv',str(vault_backup),str(vault_dir)],check=True)
        print('A4_MISSING_FIELD_AND_UNSAFE_PATH_FAIL_CLOSED_PASS')
        original=Path(self.passwords['gateway-password']).read_bytes()
        version=self.api(document)['data']['metadata']['version']
        try:
            Path(self.passwords['gateway-password']).write_text(secrets.token_hex(20))
            self.play_core('applications/apply.yml',success=False)
            self.assertEqual(self.api(document)['data']['metadata']['version'],version)
        finally:Path(self.passwords['gateway-password']).write_bytes(original)
        # Read the original field; do not duplicate or overwrite that KV source.
        base['accounts']['postgres']['credentials']['password']['source']={
            'kind':'vault_ref','binding':'secrets','mount':'secret','document':'sdku/apigateway-sdku/accounts/postgres','field':'password'}
        defaults_path.write_text(json.dumps({'platform_application_definition':definition}))
        self.play_core('applications/apply.yml')
        self.play_core('applications/verify.yml')
        self.assertEqual(self.api(document)['data']['metadata']['version'],version)
        self.assertEqual(list(self.secret_root.glob('pla-vault-*')),[])
        print('A4_WRONG_PASSWORD_AND_READONLY_SOURCE_PASS')
        owner=self.api(document)['data']['data']['_platform_owner']
        try:
            self.api(document,'PATCH',{'data':{'_platform_owner':'foreign'}})
            blocked_version=self.api(document)['data']['metadata']['version']
            self.play_core('applications/apply.yml',success=False)
            self.assertEqual(self.api(document)['data']['metadata']['version'],blocked_version)
        finally:self.api(document,'PATCH',{'data':{'_platform_owner':owner}})
        print('A4_FOREIGN_DOCUMENT_BLOCK_PASS')
        # Exercise the existing standalone Vault credential paths through Core.
        original_extra=self.extra.read_text()
        standalone=json.loads(original_extra)
        standalone.pop('platform_runtime_secret_inputs')
        try:
            standalone['platform_vault_admin_token']=self.token
            self.extra.write_text(json.dumps(standalone))
            self.play_core('applications/apply.yml')
            standalone.pop('platform_vault_admin_token')
            custody=self.secret_root/'bootstrap';custody.mkdir(mode=0o700)
            token_file=custody/'admin-token';token_file.write_text(self.token);token_file.chmod(0o600)
            standalone['platform_vault_bootstrap_output_dir']=str(custody)
            self.extra.write_text(json.dumps(standalone))
            self.play_core('applications/apply.yml')
            self.play_core('applications/verify.yml')
            token_file.unlink();custody.rmdir()
        finally:self.extra.write_text(original_extra)
        print('A4_STANDALONE_TOKEN_AND_BOOTSTRAP_PASS')

    def probe_status(self,host='node1'):
        # A4 does not provision Redis/Kafka/ClickHouse, so overall can be 503.
        try:
            url='http://192.168.56.102:28281/status' if host == 'node2' else 'http://127.0.0.1:28281/status'
            response=urllib.request.urlopen(url,timeout=25)
        except urllib.error.HTTPError as error:
            if error.code != 503:
                raise
            response=error
        with response:
            return json.load(response)


if __name__=='__main__':
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([ApplicationVaultQA('test_a4_full_apply_verify_repeat')])).wasSuccessful())

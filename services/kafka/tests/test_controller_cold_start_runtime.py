"""Explicit native acceptance: three isolated KRaft members, real role tasks.

Uses installed approved Kafka on the QA node; never touches installed project
units, data or accounts. Run as root with KAFKA_CONTROLLER_NATIVE_QA=1.
"""
import base64
import copy
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import yaml

ROOT=Path(__file__).resolve().parents[3]
ROLE=ROOT/'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'
sys.path.insert(0,str(ROOT/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from kafka_schema_registry import properties_value

@unittest.skipUnless(os.environ.get('KAFKA_CONTROLLER_NATIVE_QA')=='1' and os.geteuid()==0, 'explicit native Kafka QA required')
class ControllerColdStartTests(unittest.TestCase):
 def test_clean_three_member_quorum_repeat_and_all_members_cold_start(self):
  suffix=uuid.uuid4().hex[:8]
  root=Path('/run/qa-kafka-sasl-'+suffix);root.mkdir(mode=0o755)
  private=root/'.runtime/secrets';private.mkdir(parents=True,mode=0o700)
  os.chmod(root/'.runtime',0o700)
  public=root/'members';public.mkdir(mode=0o755)
  unit_prefix='qa-kafka-sasl-'+suffix
  units=[unit_prefix+'@'+unit_prefix+'-'+str(i)+'.service' for i in range(1,4)]
  role_path=ROLE/'tasks'
  env=dict(os.environ,ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg'),
    ANSIBLE_COLLECTIONS_PATH=str(ROOT/'services/kafka/ansible_collections')+':'+str(ROOT/'ansible-core/collections'),
    KAFKA_HEAP_OPTS='-Xms32m -Xmx128m',ANSIBLE_NOCOLOR='1')
  def cmd(args,timeout=180,**kwargs):
   return subprocess.run(args,capture_output=True,text=True,timeout=timeout,env=env,**kwargs)
  def native(args):
   result=cmd(args)
   self.assertEqual(0,result.returncode,'native command failed: '+args[0])
  try:
   for i in range(1,4):
    for port in [54000+i*100+93,54000+i*100+94,54000+i*100+96]:
     import socket
     sock=socket.socket();sock.bind(('127.0.0.1',port));sock.close()
   password=secrets.token_hex(20)+',"\\Ж'
   secret=private/'admin';secret.write_text(password);secret.chmod(0o600)
   native(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2',
     '-keyout',str(private/'ca-key.pem'),'-out',str(private/'ca-chain.pem'),'-subj','/CN=Kafka isolated QA CA'])
   native(['openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',str(private/'private-key.pem'),
     '-out',str(private/'certificate.csr'),'-subj','/CN=localhost'])
   (private/'certificate.ext').write_text('subjectAltName=IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth,clientAuth\n')
   native(['openssl','x509','-req','-in',str(private/'certificate.csr'),'-CA',str(private/'ca-chain.pem'),
      '-CAkey',str(private/'ca-key.pem'),'-CAcreateserial','-days','2','-extfile',str(private/'certificate.ext'),
      '-out',str(private/'certificate.pem')])
   (private/'materialization-fingerprint').write_text('isolated-sasl-controller-qa\n')
   members=[];requests=[];plans=[]
   for i in range(1,4):
    member_root=public/('m'+str(i));member_root.mkdir(mode=0o755)
    runtime=member_root/'runtime';runtime.mkdir(mode=0o755)
    (runtime/'heap.env').write_text('KAFKA_HEAP_OPTS="-Xms64m -Xmx192m"\n')
    members.append(dict(id='member-'+str(i),node_id=i,host='localhost',roles=['broker','controller'],
      deployment_id=unit_prefix,directory_id=base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip('='),
      advertised_host='127.0.0.1',tls_profile='qa-tls',data_directory=str(member_root/'data'),
      config_directory=str(member_root/'config'),log_directory=str(member_root/'logs'),
      _compatibility_unit=dict(runtime_directory=str(runtime),environment_pattern=str(runtime/'*.env')),
      listeners=dict(QUORUM=dict(purpose='controller',securityProtocol='SASL_SSL',port=54000+i*100+93),
         REPLICATION=dict(purpose='interBroker',securityProtocol='SSL',port=54000+i*100+94),
         CLIENT=dict(purpose='client',securityProtocol='SASL_SSL',port=54000+i*100+96))))
    request_id='qa-'+str(i)
    requests.append(dict(id=request_id,usages=['serverAuth','clientAuth'],consumers=[dict(deploymentId=unit_prefix,
      memberId='member-'+str(i),hostId='localhost',tlsProfileRef='qa-tls')]))
    plans.append(dict(hostId='localhost',requestId=request_id,tlsProfileId='qa-tls',targetDirectory=str(private),formats=['PEM']))
   apply=yaml.safe_load((role_path/'apply.yml').read_text())
   projection_names=['Получение наборов экземпляров службы Kafka','Получение локальных наборов экземпляров службы ролей Kafka',
      'Определение зарезервированных настроек Kafka','Построение детерминированных проекций кворума только для контроллеров Kafka',
      'Обнаружение требования авторизации SCRAM для всего развертывания']
   projection={task.get('name'):task for task in apply}
   tasks=[{'ansible.builtin.set_fact':dict(_platform_kafka_instances=[])},
     {'ansible.builtin.include_role':dict(name='platform.kafka.kafka_kraft',tasks_from='normalize_member',public=True),
      'loop':members,'loop_control':dict(loop_var='kafka_input_member')},
     {'ansible.builtin.set_fact':{'_platform_kafka_instances':"{{ _platform_kafka_instances | map('combine', {}) | list }}"}}]
   # Unit paths are isolated; names and all other member fields come from the
   # actual production normalization task.
   tasks += [{'ansible.builtin.set_fact':{'_qa_members':[]}},
     {'ansible.builtin.set_fact':{'_qa_members':"{{ _qa_members + [item | combine({'systemd_unit_destination': '/run/systemd/system/' ~ item.systemd_unit_name})] }}"},'loop':'{{ _platform_kafka_instances }}','no_log':True},
     {'ansible.builtin.set_fact':{'_platform_kafka_instances':'{{ _qa_members }}'}}]
   tasks += [copy.deepcopy(projection[name]) for name in projection_names]
   tasks += [{'ansible.builtin.include_role':dict(name='platform.kafka.kafka_kraft',tasks_from='member'),
     'loop':'{{ _platform_kafka_local_instances }}','loop_control':dict(loop_var='kafka_member')}]
   values=dict(platform_kafka_name=unit_prefix,platform_kafka_service_name='kafka',platform_kafka_deployment_id=unit_prefix,
      platform_kafka_cluster_id=base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip('='),
      platform_kafka_schema_registry_enabled=False,platform_kafka_instances=members,platform_kafka_quorum_mode='dynamic',
      platform_kafka_advanced_config={'num.network.threads':2,'num.io.threads':2,'num.replica.fetchers':1,'log.segment.bytes':16777216},
      platform_kafka_admin_credential=dict(passwordSecretRef='runtime:admin'),platform_kafka_secret_files={'runtime:admin':str(secret)},
      platform_pki_requests=requests,platform_pki_materialization_plans=plans,
      platform_kafka_startup_readiness_retries=30,platform_kafka_startup_readiness_delay=2)
   play=root/'play.yml'
   play.write_text(yaml.safe_dump([dict(hosts='localhost',connection='local',become=True,gather_facts=False,vars=values,tasks=tasks)],sort_keys=False))
   print('PHASE clean-role-apply',flush=True)
   first=cmd(['ansible-playbook','-i','localhost,',str(play)],timeout=600)
   self.assertEqual(0,first.returncode,(first.stdout+first.stderr)[-2600:])
   import time
   import socket
   # Three JVMs share the small QA VM with existing services. Allow election
   # and initial metadata catch-up without changing production readiness.
   deadline=time.monotonic()+300
   pending={54000+i*100+port for i in range(1,4) for port in [93,94,96]}
   while pending and time.monotonic()<deadline:
    for port in list(pending):
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=0.3):pending.remove(port)
     except OSError:pass
    if pending:time.sleep(1)
   self.assertFalse(pending,'isolated Kafka listeners did not start')
   print('PHASE native-admin-scram-and-quorum',flush=True)
   escaped=json.dumps(password,ensure_ascii=False)
   jaas='org.apache.kafka.common.security.scram.ScramLoginModule required username="admin" password='+escaped+';'
   client=private/'client.properties'
   client.write_text('security.protocol=SASL_SSL\nsasl.mechanism=SCRAM-SHA-512\nsasl.jaas.config='+properties_value(jaas)+'\nssl.truststore.type=PEM\nssl.truststore.location='+str(private/'ca-chain.pem')+'\nssl.endpoint.identification.algorithm=https\nrequest.timeout.ms=10000\ndefault.api.timeout.ms=20000\n')
   client.chmod(0o600)
   args=['/opt/kafka/bin/kafka-metadata-quorum.sh','--bootstrap-server','127.0.0.1:54196','--command-config',str(client),'describe','--status']
   def quorum():
    result=cmd(args,timeout=60)
    classes=sorted(set(re.findall(r'\b[A-Z][A-Za-z]+(?:Exception|Error)\b',result.stderr)))
    self.assertEqual(0,result.returncode,'SCRAM admin/quorum diagnostic failed: '+','.join(classes))
    voters=set(map(int,re.findall(r'"id":\s*([0-9]+)',result.stdout)))
    self.assertTrue({1,2,3}.issubset(voters),'quorum missing expected voter')
   quorum()
   print('PHASE repeat-role-apply',flush=True)
   repeat=cmd(['ansible-playbook','-i','localhost,',str(play)],timeout=600)
   self.assertEqual(0,repeat.returncode,(repeat.stdout+repeat.stderr)[-2600:])
   self.assertTrue(re.search(r'changed=0\s+',repeat.stdout),'repeat role Apply changed resources')
   print('PHASE full-quorum-stop-and-start',flush=True)
   native(['systemctl','stop',*units])
   native(['systemctl','start',*units])
   import time
   ready=False
   for attempt in range(30):
    result=cmd(args,timeout=60)
    if result.returncode==0:
     ready=True;break
    time.sleep(2)
   self.assertTrue(ready,'full cold start did not restore quorum')
   quorum()
   for i in range(1,4):
    properties=(public/('m'+str(i))/'config/server.properties').read_text()
    self.assertIn('super.users=User:admin\n',properties)
    self.assertTrue(password not in properties,'runtime credential leaked into server config')
   self.assertFalse(list(Path('/run').glob('platform-kafka-format-*')),'formatter argfile remained')
   print('NATIVE_COLD_QUORUM_PASS',flush=True)
  finally:
   for unit in units:
    cmd(['systemctl','stop',unit])
    cmd(['systemctl','disable',unit])
    cmd(['systemctl','reset-failed',unit])
    Path('/run/systemd/system',unit).unlink(missing_ok=True)
   cmd(['systemctl','daemon-reload'])
   if root.exists():shutil.rmtree(root)

if __name__=='__main__':unittest.main()

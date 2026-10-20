"""Vault projection security boundaries, not infrastructure mocks as acceptance."""
import copy
import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../collections/ansible_collections/platform/core/plugins/module_utils')))
from application_vault import project_vault
from application_runtime import agent_config, validate_agent
from schema_validation import SchemaValidator


class ApplicationVaultTest(unittest.TestCase):
    def test_scram_jaas_uses_existing_agent_env_and_both_credential_locations(self):
        self.instance['connections']['postgres'] = {'serviceType': 'kafka'}
        self.instance['secretBindings'] = {
            name: {'source': {'account': 'postgres', 'field': 'password'}, 'format': 'kafka_scram_jaas'}
            for name in ('KAFKA_PRODUCER_SASL_JAAS_CONFIG', 'KAFKA_CONSUMER_SASL_JAAS_CONFIG')}
        result = project_vault(self.rows, self.prepared)
        job = result['instanceJobs'][0]
        self.assertEqual(2, len(job['envTemplates']))
        for entry in job['envTemplates']:
            self.assertIn('ScramLoginModule required', entry['contents'])
            self.assertIn('.Data.data.username | replaceAll', entry['contents'])
            self.assertIn('.Data.data.password | replaceAll', entry['contents'])
            self.assertNotIn('toJSON', entry['contents'])
            self.assertNotIn('test-user', entry['contents'])
        self.assertEqual({'username', 'password'}, {f for fields in job['readFields'].values() for f in fields})

    def setUp(self):
        credential = {'credentials': {'username': {'source': {'kind':'literal','value':'test-user'}},
                                    'password': {'source': {'kind':'runtime_secret_ref','ref':'app-password'}}}}
        self.instance = {'agentRequired':True,'placements':{'node1':{},'node2':{}},
            'connections':{'vault':{'serviceType':'vault','deploymentRef':'v','targets':[{'hostId':'vhost','port':8200,'address':'10.0.0.3','tlsProfileRef':'vprofile'}]}},
            'credentialRequirements':{'postgres':credential},
            'secretBindings':{'PG_PASSWORD':{'source':{'account':'postgres','field':'password'}}}}
        row = {'libraryId':'sdku','instanceId':'apigateway-sdku','hostId':'node1','vaultRef':{'binding':'secrets'},
               'bindings':{'secrets':{'deploymentRef':'v'}},'settings':{'provisioner':{'secrets':{'mount':'secret'},'secret_bindings':self.instance['secretBindings']}}}
        self.rows=[row,dict(row,hostId='node2')]
        self.prepared={'snapshot':{'project':{'id':'project'},'applicationLibraries':{'libraries':{'sdku':{'instances':{'apigateway-sdku':self.instance},'sharedSecretRequirements':{}}}},
            'endpoints':{'deployments':{'v':{'fqdn':'v.example.test'}}}},
            'pki_materialization':{'materializationPlans':[{'hostId':'vhost','tlsProfileId':'vprofile','targetDirectory':'/etc/platform-installer/pki/p/v'}]}}

    def test_endpoint_precedence_and_one_logical_identity(self):
        result=project_vault(self.rows,self.prepared)
        self.assertEqual(result['providers'][0]['url'],'https://v.example.test')
        self.assertEqual(len(result['instanceJobs']),1)
        self.assertEqual(result['instanceJobs'][0]['hosts'],['node1','node2'])
        self.assertNotIn('token',result['providers'][0])

    def test_endpoint_uses_443_with_different_backend_ports(self):
        self.instance['connections']['vault']['targets'].append(
            {'hostId':'another','port':8202,'address':'10.0.0.4','tlsProfileRef':'vprofile'})
        self.assertEqual(project_vault(self.rows,self.prepared)['providers'][0]['url'],
                         'https://v.example.test')

    def test_absent_endpoint_uses_resolved_port(self):
        self.prepared['snapshot']['endpoints']={}
        self.assertEqual(project_vault(self.rows,self.prepared)['providers'][0]['url'],'https://10.0.0.3:8200')

    def test_two_environment_names_reading_one_field_remain_distinct(self):
        self.instance['secretBindings']['ANOTHER_PASSWORD']={'source':{'account':'postgres','field':'password'}}
        templates=project_vault(self.rows,self.prepared)['instanceJobs'][0]['envTemplates']
        self.assertEqual(len({item['contents'] for item in templates}),2)
        self.assertTrue(all(item['contents'].startswith('{{/* '+item['name']+' */}}') for item in templates))

    def test_no_secret_bindings_skips_vault(self):
        self.instance['agentRequired']=False
        self.instance['secretBindings']={}
        self.assertEqual(project_vault(self.rows,self.prepared)['providers'],[])

    def test_missing_vault_binding_fails(self):
        self.rows[0]['vaultRef']={}
        self.rows[1]['vaultRef']={}
        with self.assertRaisesRegex(ValueError,'BINDING_REQUIRED'):
            project_vault(self.rows,self.prepared)

    def test_vault_source_is_readonly_and_reuses_library_provider(self):
        source={'kind':'vault_ref','binding':'secrets','mount':'secret','document':'existing/account','field':'password'}
        self.instance['credentialRequirements']['postgres']['credentials']['password']['source']=source
        result=project_vault(self.rows,self.prepared)
        self.assertEqual(len(result['sourceJobs']),1)
        self.assertEqual(set(result['instanceJobs'][0]['documents'][0]['fields']),{'username'})
        self.assertIn('secret/data/existing/account',result['instanceJobs'][0]['policy'])

    def test_shared_vault_source_is_preflighted_without_password_file(self):
        self.instance['credentialRequirements']={}
        self.instance['secretBindings']={'SHARED':{'source':{'library_secret':'shared'}}}
        library=self.prepared['snapshot']['applicationLibraries']['libraries']['sdku']
        library['sharedSecretRequirements']={'shared':{'source':{'kind':'vault_ref','binding':'secrets','mount':'secret','document':'existing/shared','field':'value'}}}
        result=project_vault(self.rows,self.prepared)
        self.assertEqual(len(result['sourceJobs']),1)
        self.assertNotIn('passwordRef',result['sourceJobs'][0])
        self.assertEqual(result['libraryJobs'][0]['documents'],[])

    def test_agent_fields_cannot_hide_missing_values_in_index_function(self):
        self.instance['credentialRequirements']['postgres']['credentials']['password']['source']={
            'kind':'vault_ref','binding':'secrets','mount':'secret','document':'existing/account','field':'password-with-dash'}
        with self.assertRaisesRegex(ValueError,'AGENT_FIELD_INVALID'):
            project_vault(self.rows,self.prepared)

    def test_shared_only_no_account_hook_and_exact_pki_binding(self):
        self.instance['credentialRequirements']={}
        self.instance['secretBindings']={'JAVA_KEYSTORE_PASSWORD':{'source':{'library_secret':'java_keystore_password'}}}
        for r in self.rows:
            r['bindings']['pki']={'profileRef':'app'}
        lib=self.prepared['snapshot']['applicationLibraries']['libraries']['sdku']
        lib['sharedSecretRequirements']={'java_keystore_password':{'source':{'kind':'pki_credential','binding':'pki','credential':'java_keystore_password'}}}
        self.prepared['pki_materialization']['materializationPlans'] += [{'hostId':h,'tlsProfileId':'app','formats':['PKCS12_KEYSTORE'], 'storePasswordSecretRef':'store-password','targetDirectory':'/etc/platform-installer/pki/p/app'} for h in ('node1','node2')]
        result=project_vault(self.rows,self.prepared)
        self.assertEqual(result['instanceJobs'][0]['documents'],[])
        self.assertEqual(len(result['libraryJobs'][0]['documents']),1)
        self.prepared['pki_materialization']['materializationPlans'].append(copy.deepcopy(self.prepared['pki_materialization']['materializationPlans'][-1]))
        with self.assertRaisesRegex(ValueError,'PKI_CREDENTIAL_AMBIGUOUS'):
            project_vault(self.rows,self.prepared)

    def test_agent_cannot_override_exec_or_add_token_sink(self):
        runtime={'vault':{'endpoint_url':'https://v.example.test','ca_container_path':'/opt/vault/ca.pem','auth_mount':'auth/approle','role_id_container_path':'/opt/vault/role-id','env_templates':[]},'application_command':['/opt/apigateway/bin/apigateway']}
        content=agent_config(runtime)
        self.assertTrue(validate_agent(content,runtime))
        with self.assertRaisesRegex(ValueError,'PROFILE_INVALID'):
            validate_agent(content+'sink "file" { path = "/tmp/token" }',runtime)

    def test_vault_path_traversal_is_rejected(self):
        self.instance['credentialRequirements']['postgres']['credentials']['password']['source']={'kind':'vault_ref','binding':'secrets','mount':'secret','document':'existing/../foreign','field':'password'}
        with self.assertRaisesRegex(ValueError,'REFERENCE_INVALID'):
            project_vault(self.rows,self.prepared)

    def test_runtime_only_admin_credentials_schema(self):
        root=os.path.abspath(os.path.join(os.path.dirname(__file__),'../..'))
        validator=SchemaValidator(root+'/contracts')
        path=root+'/contracts/application-libraries/v1alpha1/deployments.schema.json'
        base={'libraryRef':'sdku@1.0.0','runtimeRef':'docker'}
        for source, valid in [({'binding':'secrets'},True),
            ({'binding':'secrets','admin_token_file':'/private/admin-token.age','encryption_password_ref':'runtime:vault-password'},False),
            ({'binding':'secrets','admin_token_file':'/private/admin-token.age'},False),
            ({'binding':'secrets','admin_token_file':'relative','encryption_password_ref':'password'},False),
            ({'binding':'secrets','password':'plaintext'},False)]:
            with self.subTest(source=source):
                self.assertEqual(not valid,bool(validator.validate({'sdku':dict(base,vault_ref=source)},path)))

    def test_private_file_mapping_and_symlink_guard(self):
        module_path=os.path.join(os.path.dirname(__file__),'../collections/ansible_collections/platform/core/plugins/modules/application_identity_files.py')
        spec=importlib.util.spec_from_file_location('identity_files_a4',module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            mapping=directory+'/uid_map'
            with open(mapping,'w') as stream:stream.write('0 1002 1\n1 655360 65536\n')
            self.assertEqual(module.mapped(mapping,1000),656359)
            with self.assertRaises(ValueError):module.mapped(mapping,100000)
            private=directory+'/private';os.mkdir(private,0o700)
            link=directory+'/link';os.symlink(private,link)
            with self.assertRaises(ValueError):module.custody(link,{os.getuid()},True)


if __name__=='__main__':
    unittest.main()

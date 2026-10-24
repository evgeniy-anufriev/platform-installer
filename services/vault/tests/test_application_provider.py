"""CAS, identity normalization and scope checks for the application Vault hook."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
PLUGIN=ROOT/'services/vault/ansible_collections/platform/vault/plugins/filter/application_provider.py'
spec=importlib.util.spec_from_file_location('vault_application_filter',PLUGIN)
provider=importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)
sys.path.insert(0,str(ROOT/'ansible-core/collections'))
spec=importlib.util.spec_from_file_location('vault_application_credentials',PLUGIN.parent.parent/'action/application_credentials.py')
credentials=importlib.util.module_from_spec(spec);spec.loader.exec_module(credentials)
spec=importlib.util.spec_from_file_location('vault_application_document',PLUGIN.parent.parent/'action/application_document.py')
document_action=importlib.util.module_from_spec(spec);spec.loader.exec_module(document_action)


class ApplicationProviderTest(unittest.TestCase):
    def test_generated_password_reuses_owned_document_and_rejects_unsafe_sources(self):
        with tempfile.TemporaryDirectory() as root:
            ref = 'pla-generated-' + 'a' * 40
            document = dict(mount='secret', owner='owned', fields={
                'password': dict(source={'kind': 'generated'}, passwordRef=ref)})
            args = dict(document=document, current={'status':404}, secret_root=root,
                        secret_files={}, provider={'mounts':{'secret/':{'type':'kv','options':{'version':'2'}}}})
            action = object.__new__(document_action.ActionModule)
            action._task = SimpleNamespace(args=args)
            with patch.object(document_action.secrets, 'token_urlsafe', wraps=document_action.secrets.token_urlsafe) as generator:
                first = action.run()
                self.assertFalse(first.get('failed', False))
                self.assertEqual(43, len(first['fields']['password']))
                generator.assert_called_once_with(32)
                args['current'] = self.response()
                generator.reset_mock()
                saved = action.run()
                self.assertEqual('old', saved['fields']['password'])
                generator.assert_not_called()
                args['current']['json']['data']['data']['_platform_owner'] = 'foreign'
                self.assertTrue(action.run()['failed'])
                generator.assert_not_called()
                args['current'] = self.response()
                args['current']['json']['data']['metadata']['destroyed'] = True
                self.assertTrue(action.run()['failed'])
                generator.assert_not_called()
            document['fields']['password']['passwordRef'] = '../outside'
            self.assertTrue(action.run()['failed'])

    def response(self):
        return {'status':200,'json':{'data':{'data':{'_platform_owner':'owned','password':'old','neighbor':'keep'},
            'metadata':{'version':7,'deletion_time':'','destroyed':False}}}}

    def test_new_document_uses_cas_zero_and_owner_marker(self):
        result=provider.delta({'status':404},{'password':'new'},'owned')
        self.assertEqual(result['method'],'PUT')
        self.assertEqual(result['body'],{'options':{'cas':0},'data':{'password':'new','_platform_owner':'owned'}})

    def test_patch_preserves_neighbor_and_uses_observed_version(self):
        result=provider.delta(self.response(),{'password':'new'},'owned')
        self.assertEqual(result['method'],'PATCH')
        self.assertEqual(result['body'],{'options':{'cas':7},'data':{'password':'new'}})

    def test_equal_fields_skip_version_creation(self):
        self.assertFalse(provider.delta(self.response(),{'password':'old'},'owned')['changed'])

    def test_foreign_deleted_destroyed_documents_block(self):
        for target,value in (('owner','foreign'),('deletion_time','timestamp'),('destroyed',True)):
            with self.subTest(target=target):
                response=self.response()
                if target=='owner': response['json']['data']['data']['_platform_owner']=value
                else: response['json']['data']['metadata'][target]=value
                with self.assertRaisesRegex(Exception,'OWNERSHIP_INVALID'):
                    provider.delta(response,{'password':'new'},'owned')
        with self.assertRaisesRegex(Exception,'OWNERSHIP_INVALID'):
            provider.delta({'status':404,'json':{'data':{'metadata':{'version':7},'data':None}}},{},'owned')

    def test_cidr_union_and_invalid_route(self):
        self.assertEqual(provider.cidrs([[{'prefsrc':'192.168.56.101'}],[{'prefsrc':'10.0.3.1'}]]),
                         ['10.0.3.0/24','127.0.0.1/32','192.168.56.0/24'])
        with self.assertRaisesRegex(Exception,'ROUTE_INVALID'):provider.cidrs([[{'prefsrc':'::1'}]])

    def test_role_normalizes_cidrs_without_ignoring_security_changes(self):
        desired={'bind_secret_id':False,'token_bound_cidrs':['10.0.3.0/24','127.0.0.1/32'],'token_policies':['owned'],'token_ttl':3600}
        current=copy.deepcopy(desired);current['token_bound_cidrs']=['127.0.0.1','10.0.3.0/24']
        response={'status':200,'json':{'data':current}}
        self.assertFalse(provider.role_changed(response,desired))
        for key,value in (('bind_secret_id',True),('token_ttl',10),('token_bound_cidrs',['0.0.0.0/0'])):
            changed=copy.deepcopy(response);changed['json']['data'][key]=value
            self.assertTrue(provider.role_changed(changed,desired))

    def test_lxc_subnets_use_actual_prefix_and_union_all_placements(self):
        bridges = [[{'addr_info':[{'family':'inet','scope':'global','local':address,'prefixlen':prefix}]}]
                   for address,prefix in [('10.0.3.1',24),('10.22.0.1',20),('10.0.3.1',24)]]
        self.assertEqual(provider.cidrs([[{'prefsrc':'192.168.56.101'}]], bridges),
                         ['10.0.3.0/24','10.22.0.0/20','127.0.0.1/32','192.168.56.0/24'])

    def test_missing_or_unrestricted_lxc_subnet_blocks(self):
        for bridge in ([],[{'addr_info':[]}],
                       [{'addr_info':[{'family':'inet','scope':'global','local':'10.0.3.1','prefixlen':0}]}]):
            with self.subTest(bridge=bridge):
                with self.assertRaisesRegex(Exception,'ROUTE_INVALID'):
                    provider.cidrs([[{'prefsrc':'192.168.56.101'}]], [bridge])

    def test_required_field_missing_is_not_a_successful_verify(self):
        response={'item':'secret/data/app','json':{'data':{'data':{'password':'value'}}}}
        self.assertTrue(provider.verify_fields([response],{'secret/data/app':['password']}))
        self.assertFalse(provider.verify_fields([response],{'secret/data/app':['missing']}))
        self.assertFalse(provider.verify_fields([],{'secret/data/app':['password']}))

    def credential(self, root, auth, inputs=None, files=None, **standalone):
        action=object.__new__(credentials.ActionModule)
        action._task=SimpleNamespace(args={'provider_id':'vault','single_provider':True,'auth':auth})
        return action.run(task_vars={'platform_application_secret_root':root,
            'platform_runtime_secret_inputs':inputs or [],'platform_application_secret_files':files or {}, **standalone})

    def test_typed_token_precedes_standalone_source(self):
        with tempfile.TemporaryDirectory() as root:
            result=self.credential(root,{},
                [{'purpose':'SERVICE_ADMIN_TOKEN','requirementRef':'si-'+'a'*40,'value':'synthetic-fixture'}])
            self.assertFalse(result.get('failed',False))
            self.assertFalse(result['changed'])

    def test_standalone_explicit_token(self):
        with tempfile.TemporaryDirectory() as root:
            result=self.credential(root,{},platform_vault_admin_token='synthetic-fixture')
            self.assertFalse(result.get('failed',False))
            self.assertEqual(result['token'],'synthetic-fixture')

    def test_standalone_bootstrap_custody(self):
        with tempfile.TemporaryDirectory() as root:
            token=Path(root)/'admin-token';token.write_text('synthetic-fixture\n');token.chmod(0o600)
            result=self.credential(root,{},platform_vault_bootstrap_output_dir=root)
            self.assertFalse(result.get('failed',False))
            self.assertEqual(result['token'],'synthetic-fixture')

    def test_bootstrap_symlink_uses_existing_secret_input(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'other';target.write_text('synthetic-fixture');target.chmod(0o600)
            (Path(root)/'admin-token').symlink_to(target)
            result=self.credential(root,{},platform_vault_bootstrap_output_dir=root)
            self.assertFalse(result.get('failed', False))
            self.assertEqual(result['token'], 'synthetic-fixture')

    def test_ambiguous_typed_tokens_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            token={'purpose':'SERVICE_ADMIN_TOKEN','requirementRef':'si-'+'a'*40,'value':'synthetic-fixture'}
            self.assertTrue(self.credential(root,{},[token,token])['failed'])


if __name__=='__main__': unittest.main()

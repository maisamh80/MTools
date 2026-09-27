import json
import unittest
from zipfile import ZipFile
import test_service
from mtools.files import atomic_json

class ProjectTests(unittest.TestCase):
    setUp = test_service.Workspace.setUp
    tearDown = test_service.Workspace.tearDown
    job = test_service.Workspace.job

    def configure(self):
        self.s.projects_configure(str(self.root/'Archive'))

    def save_project(self):
        source=self.root/'input';source.mkdir(exist_ok=True);self.host['input']=str(source)
        (source/'reference.txt').write_text('reference content')
        (self.output/'final.txt').write_text('final content')
        return self.job('project.save', {'title':'Test dossier','graph':{'nodes':[]},'prompt':'a prompt',
            'capture':{'files':[{'role':'references','path':'reference.txt'},{'role':'outputs','path':'final.txt'}], 'metadata':{'source':'test'}}})

    def test_archive_export_import(self):
        self.configure();result=self.save_project();self.assertEqual(result['status'],'complete',result)
        id=result['result']['id'];p=self.s.project_get(id)
        self.assertEqual(len(p['files']),2);self.assertEqual(p['prompt'],'a prompt')
        self.assertNotIn('external_library',self.s.settings)
        archive=self.root/'project.zip'
        result=self.job('project.export',{'id':id,'destination':str(archive)})
        self.assertEqual(result['status'],'complete',result)
        with ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()),{'project.json','workflow.json','references/001-reference.txt','outputs/002-final.txt'})
        upload=self.s.data/'project-uploads';upload.mkdir();token='1'*32;(upload/token).write_bytes(archive.read_bytes())
        result=self.job('project.import',{'token':token});self.assertEqual(result['status'],'complete',result)
        self.assertNotEqual(result['result']['id'],id)
        self.assertEqual(len(self.s.projects_list()['items']),2)
        self.assertEqual(self.s.project_get(result['result']['id'])['prompt'],p['prompt'])

    def test_import_rejects_escape(self):
        self.configure();saved=self.save_project();folder=self.s.project_dir(saved['result']['id'])
        p=json.loads((folder/'project.json').read_text());p['files'][0]['path']='references/../../outside.txt';atomic_json(folder/'project.json',p)
        result=self.job('project.import',{'path':str(folder)});self.assertEqual(result['status'],'failed')
        self.assertFalse((self.root/'outside.txt').exists())

    def test_missing_reference(self):
        self.configure();self.host['input']=str(self.output)
        result=self.job('project.save',{'graph':{'nodes':[]},'capture':{'files':[{'role':'references','path':'missing.png'}]}})
        self.assertEqual(result['status'],'complete');p=self.s.project_get(result['result']['id'])
        self.assertEqual(p['files'],[]);self.assertTrue(p['warnings'])

    def test_disallow_weights(self):
        self.configure();upload=self.s.data/'project-uploads';upload.mkdir();token='2'*32;(upload/token).write_bytes(b'weights')
        result=self.job('project.save',{'graph':{'nodes':[]},'uploads':[{'role':'references','name':'model.safetensors','token':token}]})
        self.assertEqual(result['status'],'failed');self.assertEqual(self.s.projects_list()['items'],[])

    def test_edit_conflict(self):
        self.configure();result=self.save_project();id=result['result']['id'];p=self.s.project_get(id)
        self.s.project_edit(id,'Updated',expected_updated_at=p['updated_at'])
        with self.assertRaises(ValueError):self.s.project_edit(id,'Lost edit',expected_updated_at=p['updated_at'])
        self.assertEqual(self.s.project_get(id)['title'],'Updated')

    def test_append_preserves_capture_and_workflow(self):
        self.configure();result=self.save_project();id=result['result']['id'];p=self.s.project_get(id)
        uploads=self.s.data/'project-uploads';uploads.mkdir();token='3'*32;(uploads/token).write_text('additional output')
        result=self.job('project.update',{'id':id,'title':'Supplemented','expected_updated_at':p['updated_at'],
            'uploads':[{'token':token,'name':'extra.txt','role':'outputs'}]})
        self.assertEqual(result['status'],'complete',result)
        updated=self.s.project_get(id)
        self.assertEqual(len(updated['files']),3)
        self.assertEqual(updated['capture'],p['capture'])
        self.assertEqual(updated['graph'],p['graph'])

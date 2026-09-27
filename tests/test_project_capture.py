import importlib.util
import sys
import types
import unittest
from pathlib import Path
import mtools
import test_service

package=types.ModuleType('capture_test_package');package.__path__=[str(Path(__file__).parents[1])]
sys.modules['capture_test_package']=package
sys.modules['capture_test_package.mtools']=mtools
spec=importlib.util.spec_from_file_location('capture_test_package.project_capture',Path(__file__).parents[1]/'project_capture.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CaptureTests(unittest.TestCase):
    setUp=test_service.Workspace.setUp
    tearDown=test_service.Workspace.tearDown

    def test_exact_execution_and_reference_capture(self):
        self.host['input']=str(self.output)
        (self.output/'reference.png').write_bytes(b'fixture')
        prompt={'1':{'class_type':'LoadImage','inputs':{'image':'reference.png'}},'2':{'class_type':'CLIPTextEncode','inputs':{'text':'my exact words'}}}
        history={'run':{'prompt':[0,'run',prompt], 'outputs':{'3':{'images':[{'filename':'final.png','subfolder':'','type':'output'}]}}}}
        result=module.capture_project({'nodes':[]},prompt,self.host,history)
        self.assertEqual(result['metadata']['execution_id'],'run')
        self.assertEqual(len(result['files']),2)
        self.assertIn('my exact words',result['prompt_text'])
        changed={**prompt,'2':{'class_type':'CLIPTextEncode','inputs':{'text':'changed words'}}}
        result=module.capture_project({'nodes':[]},changed,self.host,history)
        self.assertIsNone(result['metadata']['execution_id'])
        self.assertFalse(any(f['role']=='outputs' for f in result['files']))
        self.assertTrue(result['warnings'])

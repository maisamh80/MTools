import importlib.util
from pathlib import Path
import threading
import types
import unittest

spec = importlib.util.spec_from_file_location('asset_sync', Path(__file__).parents[1] / 'asset_sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class HistorySync(unittest.TestCase):
    def test_only_deleted_output_is_removed_and_jobs_survive(self):
        output = Path.cwd() / 'fixture-output'
        deleted = {'filename': 'same.png', 'subfolder': 'one', 'type': 'output'}
        sibling = {'filename': 'same.png', 'subfolder': 'two', 'type': 'output'}
        input_file = {**deleted, 'type': 'input'}
        queue = types.SimpleNamespace(mutex=threading.RLock(), history={'job': {
            'prompt': ['keep'], 'outputs': {'1': {'images': [deleted, sibling, input_file], 'text': ['keep text']}}}})
        sync.prune_history_output(queue, output, output / 'one' / 'same.png')
        self.assertEqual(queue.history['job']['outputs']['1']['images'], [sibling, input_file])
        self.assertEqual(queue.history['job']['prompt'], ['keep'])
        self.assertEqual(queue.history['job']['outputs']['1']['text'], ['keep text'])

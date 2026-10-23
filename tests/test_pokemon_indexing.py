"""Contract checks for secrets, cache integrity, model identity and store isolation."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from src.pokemon.embeddings import GMS_BASE, GmsEmbeddings, validate_vectors
from src.pokemon.store import indexing_lock, open_collection


class FakeClient:
    def __init__(self, model='test-model', indexes=None):
        self.embeddings = self
        self.model, self.indexes, self.calls = model, indexes, 0

    def create(self, **kwargs):
        self.calls += 1
        indexes = self.indexes if self.indexes is not None else range(len(kwargs['input']))
        return NS(model=self.model, usage=NS(total_tokens=3), data=[
            NS(index=i, embedding=[0.1, 0.2, 0.3]) for i in indexes])


class IndexContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = {'base_url': GMS_BASE, 'embedding_model': 'test-model',
                    'embedding_dimensions': 3, 'batch_size': 2}

    def embedder(self, **kwargs):
        return GmsEmbeddings(self.cfg, self.root/'cache', self.root/'absent.env', **kwargs)

    def test_cache_reuse_offline_and_tamper_rejection(self):
        client = FakeClient()
        vectors = self.embedder(client=client).embed(['한국어 입력'])
        cached = self.embedder(offline=True)
        self.assertEqual(vectors, cached.embed(['한국어 입력']))
        self.assertEqual(cached.calls, 0)
        path = next((self.root/'cache').glob('*.json'))
        payload = json.loads(path.read_text(encoding='utf-8'))
        payload['vector'][0] = 0.9
        path.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ValueError):
            cached.embed(['한국어 입력'])

    def test_offline_miss_never_calls_client(self):
        client = FakeClient()
        with self.assertRaises(RuntimeError):
            self.embedder(offline=True, client=client).embed(['not cached'])
        self.assertEqual(client.calls, 0)

    def test_wrong_model_and_response_indexes_not_cached(self):
        for client in [FakeClient(model='wrong'), FakeClient(indexes=[1])]:
            with self.assertRaises(ValueError):
                self.embedder(client=client).embed(['input'])
        self.assertEqual(list((self.root/'cache').glob('*.json')), [])

    def test_vectors_reject_nonfinite_wrong_dimension_and_zero(self):
        for vector in [[float('nan'), 1, 2], [1, 2], [0, 0, 0]]:
            with self.assertRaises(ValueError):
                validate_vectors([vector], 1, 3)

    def test_endpoint_cannot_silently_switch_provider(self):
        self.cfg['base_url'] = 'https://api.openai.com/v1/'
        with self.assertRaises(ValueError):
            self.embedder()

    def test_lock_excludes_concurrent_writers(self):
        lock = self.root/'index.lock'
        with indexing_lock(lock):
            with self.assertRaises(RuntimeError):
                with indexing_lock(lock):
                    self.fail('Concurrent writer entered')
        self.assertFalse(lock.exists())

    def test_real_chroma_upsert_and_signature_guard(self):
        # Release Windows HNSW file handles by ending the isolated store process.
        code = '''
import sys
from src.pokemon.store import open_collection
c = open_collection(sys.argv[1], 'test_meta', 'signature-a')
for _ in range(2):
    c.upsert(ids=['species:1'], documents=['text'], embeddings=[[0.1,0.2,0.3]], metadatas=[{'item_id':'species:1'}])
assert c.count() == 1
try:
    open_collection(sys.argv[1], 'test_meta', 'signature-b')
except ValueError:
    pass
else:
    raise AssertionError('Incompatible signature accepted')
'''
        subprocess.run([sys.executable, '-c', code, str(self.root/'store')], check=True)


if __name__ == '__main__':
    unittest.main()

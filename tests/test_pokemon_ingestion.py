"""Contracts for source selection, provenance and condition-preserving chunks."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from src.pokemon.chunking import chunks_for, split_text
from src.pokemon.ingestion import validate_query, validate_selection
from src.pokemon.llm import GmsJson
from src.pokemon.embeddings import GMS_BASE


def document(**updates):
    value = {'doc_id': 'doc-a', 'item_id': 'pokemon-species:1', 'title': 'synthetic title',
        'content': 'synthetic body', 'kind': 'species_description', 'language': 'ko',
        'source_url': 'https://example.org/test', 'source_type': 'test', 'version': 'test-version',
        'version_kind': 'version', 'version_scope': 'explicit', 'source_revision': 'test', 'collected_at': 'test'}
    value.update(updates)
    return value


class IngestionContracts(unittest.TestCase):
    def test_cross_item_chunk_ids_cannot_overwrite_shared_document(self):
        a = chunks_for(document(), 'pokemon-species:1', 800, 100)
        b = chunks_for(document(), 'pokemon-species:2', 800, 100)
        self.assertNotEqual(a[0]['id'], b[0]['id'])
        self.assertEqual(b[0]['metadata']['source_item_id'], 'pokemon-species:1')
        self.assertEqual(b[0]['metadata']['item_id'], 'pokemon-species:2')

    def test_profile_change_changes_ids_and_preserves_short_document(self):
        a = chunks_for(document(), 'pokemon-species:1', 800, 100)
        b = chunks_for(document(), 'pokemon-species:1', 400, 100)
        self.assertNotEqual(a[0]['id'], b[0]['id'])
        self.assertIn('synthetic body', a[0]['text'])
        for size, overlap in [(0,0), (100,100), (100,-1)]:
            with self.assertRaises(ValueError):
                chunks_for(document(), 'pokemon-species:1', size, overlap)

    def test_long_text_has_no_dropped_characters(self):
        text = ''.join(chr(0x4e00+i) for i in range(2500))
        parts = list(split_text(text, 400, 50))
        self.assertTrue(all(len(p)<=400 for p in parts))
        rebuilt = parts[0] + ''.join(p[50:] for p in parts[1:])
        self.assertEqual(rebuilt, text)

    def test_evolution_alternatives_and_conjunction_fields_kept(self):
        chain = {'chain_id':'test', 'edges':[{'from_species_id':1,'from':'a', 'to_species_id':2,'to':'b',
                  'conditions':[{'minimum_level':'20','time_of_day':'night'}, {'trigger_item_name':'test-stone'}]}]}
        chunks = chunks_for(document(kind='evolution_chain',content=json.dumps(chain)), 'pokemon-species:1',800,100)
        self.assertEqual(len(chunks),2)
        self.assertIn('AND / 다른 조건 행과 OR',chunks[0]['text'])
        self.assertIn('minimum_level',chunks[0]['text'])
        self.assertIn('time_of_day',chunks[0]['text'])
        self.assertNotIn('test-stone',chunks[0]['text'])
        with self.assertRaises(json.JSONDecodeError):
            chunks_for(document(kind='evolution_chain', content='broken json'), 'pokemon-species:1',800,100)

    def test_translation_provenance_survives(self):
        doc = document(is_machine_translation=True,is_official_korean_text=False,original_doc_id='english-source',
                       translation_model='test-model')
        c = chunks_for(doc, 'pokemon-species:1',800,100)[0]
        self.assertFalse(c['metadata']['is_official_korean_text'])
        self.assertEqual(c['metadata']['original_doc_id'],'english-source')
        self.assertIn('생성 한국어 번역',c['text'])

    def test_query_unknown_version_and_empty_search_rejected(self):
        plan={'queries':['test'],'kinds':['species_description'],'requested_version':None,
              'unsupported':[],'requires_item_change':False}
        validate_query(plan,['test-version'])
        with self.assertRaises(ValueError):
            validate_query({**plan,'requested_version':'invented-game'},['test-version'])
        with self.assertRaises(ValueError):
            validate_query({**plan,'queries':['']},['test-version'])

    def test_selection_rejects_invented_ids_missing_and_conflicting_decisions(self):
        candidates=[{'candidate_id':'a'}]
        valid={'selected_ids':['a'],'reasons':[{'candidate_id':'a','decision':'select','reason':'relevant'}]}
        validate_selection(valid,candidates,8)
        for invalid in [{'selected_ids':['invented'],'reasons':valid['reasons']},
                        {'selected_ids':['a'],'reasons':[]},
                        {'selected_ids':[],'reasons':valid['reasons']}]:
            with self.assertRaises(ValueError):
                validate_selection(invalid,candidates,8)

    def test_llm_offline_cache_no_calls_and_tamper_rejected(self):
        with TemporaryDirectory() as temp:
            cfg={'base_url':GMS_BASE,'answer_model':'test-model'}
            calls=[]
            def create(**kwargs):
                calls.append(kwargs)
                return NS(status='completed',output_text='{"ok": true}',model='test-model',usage=NS(total_tokens=1))
            client=NS(responses=NS(create=create))
            validate=lambda r: self.assertTrue(r['ok'])
            online=GmsJson(cfg,Path(temp),Path(temp)/'no.env',client=client)
            online.run('test','instructions',{}, {},validate)
            offline=GmsJson(cfg,Path(temp),Path(temp)/'no.env',offline=True,client=client)
            offline.run('test','instructions',{}, {},validate)
            self.assertEqual(len(calls),1)
            with self.assertRaises(RuntimeError):
                offline.run('missing','instructions',{}, {},validate)
            path=next(Path(temp).glob('*.json'))
            cached=json.loads(path.read_text(encoding='utf-8'))
            cached['result']['ok']=False
            path.write_text(json.dumps(cached),encoding='utf-8')
            with self.assertRaises(ValueError):
                offline.run('test','instructions',{}, {},validate)


if __name__=='__main__':
    unittest.main()

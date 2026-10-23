"""Grounding contracts: valid sources, scope, deduplication and two-node flow."""
import unittest
from types import SimpleNamespace as NS
from tempfile import TemporaryDirectory
from pathlib import Path

from src.pokemon.citations import NOTICE, citation_numbers, used_sources, validate_answer
from src.pokemon.graph import build_graph
from src.pokemon.retrieval import Retriever, deduplicate, language_priority, version_matches
from src.pokemon.rag import foreign_item_requested
from src.pokemon.llm import GmsJson
from src.pokemon.embeddings import GMS_BASE


def evidence(number=1, kind='metadata', generated=False):
    return {'number':number,'title':'test','kind':kind,'text':'synthetic body',
            'source_url':'https://example.org/test','is_machine_translation':generated}


def row(identity, version='x', language='ko', kind='species_description'):
    return {'id':identity,'text':'same body','metadata':{'source_item_id':'species:1','kind':kind,
            'language':language,'version_kind':'version','version':version,'content_hash':'body-hash','doc_id':identity}}


class RagContracts(unittest.TestCase):
    def test_bad_answer_is_repaired_once_with_explicit_validation_feedback(self):
        import json
        calls=[]
        def create(**kwargs):
            calls.append(kwargs['input'])
            answer='인용 누락' if len(calls)==1 else '주장 [근거 1]'
            return NS(status='completed',model='test-model',usage=NS(total_tokens=1),
                      output_text=json.dumps({'answer':answer,'status':'answered'}))
        with TemporaryDirectory() as directory:
            llm=GmsJson({'base_url':GMS_BASE,'answer_model':'test-model'},directory,Path(directory)/'no.env',
                        client=NS(responses=NS(create=create)))
            result=llm.run('answer','instructions',{}, {},lambda r:validate_answer(r,[evidence()]))
            self.assertEqual(result['answer'],'주장 [근거 1]')
            self.assertEqual(llm.calls,2)
            self.assertIn('Factual answer requires citations',calls[1])
            self.assertEqual(len(list((Path(directory)/'rejected').glob('*.json'))),1)

    def test_citations_select_only_used_sources_and_strip_bodies(self):
        sources=[evidence(1),evidence(2)]
        result=used_sources('주장 [근거 2, 2]',sources)
        self.assertEqual([s['number'] for s in result],[2])
        self.assertNotIn('text',result[0])
        self.assertEqual(citation_numbers('주장 [근거 1][근거 2]'),[1,2])

    def test_invalid_missing_or_fabricated_citations_rejected(self):
        for answer in ['주장 [근거 0]','주장 [근거 3]','주장 [근거 x]','인용 없는 주장',
                       '주장 [근거 1] 그리고 [근거 99',
                       '주장 [근거 1] https://invented.org']:
            with self.assertRaises(ValueError):
                validate_answer({'status':'answered','answer':answer},[evidence()])
        validate_answer({'status':'insufficient','answer':'확인되지 않습니다.'},[evidence()])

    def test_exact_dedup_preserves_version_comparisons_and_provenance(self):
        rows=[row('a','x'),row('b','y'),row('c','x',language='en'),row('d','x',kind='ability_description')]
        merged=deduplicate(rows)
        self.assertEqual(len(merged),3)
        self.assertEqual({p['version'] for p in merged[0]['provenance']},{'x','y'})
        self.assertEqual(len(deduplicate(rows,keep_versions=True)),4)

    def test_version_and_version_group_are_distinct(self):
        groups={'x':'x-y','y':'x-y','red':'red-blue'}
        doc={'kind':'species_description','version_kind':'version','version':'x'}
        self.assertTrue(version_matches(doc,['x'],groups))
        self.assertFalse(version_matches(doc,['y'],groups))
        ability={**doc,'kind':'ability_description','version_kind':'version_group','version':'x-y'}
        self.assertTrue(version_matches(ability,['y'],groups))
        self.assertFalse(version_matches(ability,['red'],groups))
        self.assertTrue(version_matches({**doc,'kind':'evolution_chain','version_kind':'mixed_or_unspecified'},['red'],groups))

    def test_language_preference_is_explicit(self):
        self.assertLess(language_priority({'language':'ko'}),language_priority({'language':'ko','is_machine_translation':True}))
        self.assertLess(language_priority({'language':'ko','is_machine_translation':True}),language_priority({'language':'en'}))

    def test_mandatory_metadata_cannot_be_silently_dropped_for_budget(self):
        service=Retriever.__new__(Retriever)
        service.config={'retrieval':{'document_top_k':5,'document_fetch_k':30,'max_fetch_k':200,'context_budget_tokens':1}}
        service.groups={}
        item={'item_id':'species:1','name_ko':'test','source_urls':['https://example.org'],
              'source_revision':'test','collected_at':'test','metadata_scope':'snapshot'}
        service.source=NS(resolve=lambda _:item,source_urls={name:'https://example.org/'+name for name in
            ('pokemon_species_names','pokemon_types','type_names','pokemon_stats','pokemon_abilities','ability_names','generations')})
        service.meta=NS(get=lambda **_: {'ids':['species:1'],'documents':['body']})
        with self.assertRaises(ValueError):
            service.retrieve('test','question')

    def test_graph_has_exactly_retrieve_generate_nodes_and_only_cited_sources(self):
        class FakeRetriever:
            def retrieve(self,*args,**kwargs):
                return {'evidence':[evidence(1),evidence(2,'species_description',True)],
                        'warnings':[],'diagnostics':{},'selected_item_id':'species:1','selected_name':'test'}
        class FakeLlm:
            def run(self,role,instructions,payload,schema,validate):
                result={'answer':'근거의 설명입니다. [근거 2]','status':'answered'}
                validate(result)
                return result
        graph=build_graph(FakeRetriever(),FakeLlm())
        self.assertEqual(set(graph.get_graph().nodes),{'__start__','retrieve','generate','__end__'})
        result=graph.invoke({'item':'test','question':'question'})
        self.assertEqual(result['trace'],['retrieve','generate'])
        self.assertEqual([s['number'] for s in result['sources']],[2])
        self.assertIn('생성 한국어 번역',result['answer'])

    def test_unsupported_question_has_no_generation_call_and_explains_missing_citations(self):
        class FakeRetriever:
            def retrieve(self,*args,**kwargs):
                assert kwargs['blocked']
                return {'evidence':[evidence()],'warnings':[],'diagnostics':{},
                        'selected_item_id':'species:1','selected_name':'test'}
        class NoLlm:
            def run(self,*args):
                raise AssertionError('Unsupported question must not call generation')
        result=build_graph(FakeRetriever(),NoLlm()).invoke({'item':'test','question':'question','unsupported':['moves']})
        self.assertEqual(result['status'],'insufficient')
        self.assertEqual(result['sources'],[])
        self.assertEqual(result['citation_notice'],NOTICE)

    def test_foreign_subject_cannot_hide_in_an_evolution_or_comparison_question(self):
        items=[{'item_id':'pokemon-species:1','name_ko':'테스트갑','name':'alpha'},
               {'item_id':'pokemon-species:2','name_ko':'테스트을','name':'beta'},
               {'item_id':'pokemon-species:3','name_ko':'테스트병','name':'gamma'}]
        import json
        source=NS(items=items,own=lambda _: [{'kind':'evolution_chain','content':json.dumps({
            'edges':[{'from_species_id':1,'to_species_id':2}]})}])
        self.assertFalse(foreign_item_requested('테스트을로 진화하는 조건',items[0],source))
        self.assertTrue(foreign_item_requested('테스트병의 진화 조건',items[0],source))
        self.assertTrue(foreign_item_requested('테스트갑과 테스트병 비교',items[0],source))


if __name__=='__main__':
    unittest.main()

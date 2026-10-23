"""Objective filters, evidence-backed cards and Streamlit integration contracts."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.pokemon.evolution import cards_from_evidence
from src.pokemon.explore import matches, validate_constraints
from src.pokemon import ui_service as service

ROOT=Path(__file__).resolve().parents[1]


def plan(**updates):
    result={'types':[],'type_mode':'all','conditions':[],'name_contains':None,'unsupported':[],'ambiguous':False}
    result.update(updates)
    return result


class UiContracts(unittest.TestCase):
    def setUp(self):
        self.item={'types':['전기','강철'],'name_ko':'테스트','name':'test','generation':'generation-i',
                   'weight_kg':6,'height_m':0.3,'stats':{'hp':40,'attack':30},'is_legendary':False,'is_mythical':False}

    def test_all_conditions_are_checked_and_type_or_is_explicit(self):
        p=plan(types=['전기'],conditions=[{'field':'generation','operator':'eq','value':1},
                                        {'field':'weight_kg','operator':'lte','value':10}])
        self.assertTrue(matches(self.item,p))
        self.assertFalse(matches({**self.item,'weight_kg':11},p))
        self.assertFalse(matches({**self.item,'generation':'generation-ii'},p))
        self.assertFalse(matches(self.item,plan(types=['물','전기'])))
        self.assertTrue(matches(self.item,plan(types=['물','전기'],type_mode='any')))

    def test_unsupported_and_ambiguous_conditions_never_return_matches(self):
        self.assertFalse(matches(self.item,plan(unsupported=['guaranteed win'])))
        self.assertFalse(matches(self.item,plan(ambiguous=True)))

    def test_arbitrary_fields_boolean_numbers_and_nonfinite_are_rejected(self):
        for field,operator,value in [('__import__','eq',1),('weight_kg','eq',True),('weight_kg','lte',math.inf),
                                     ('is_legendary','gte',False),('generation','eq',10),('generation','eq',1.5)]:
            with self.assertRaises(ValueError):
                validate_constraints(plan(conditions=[{'field':field,'operator':operator,'value':value}]),['전기','강철'])

    def test_history_and_clear_are_isolated_and_only_used_sources_are_saved(self):
        state={}
        result={'answer':'text','sources':[{'number':2}],'citation_notice':'','evidence':['private prompt/body']}
        service.save_reply(state,'a','question',result,['x'])
        service.save_reply(state,'b','other',result,[])
        self.assertEqual(len(service.history_for(state,'a')),2)
        self.assertNotIn('evidence',service.history_for(state,'a')[1])
        service.clear_history(state,'a')
        self.assertEqual(service.history_for(state,'a'),[])
        self.assertEqual(len(service.history_for(state,'b')),2)
        service.select_item(state,'b')
        self.assertEqual(state['view'],'대화')

    def test_error_logs_never_copy_exception_message(self):
        with TemporaryDirectory() as directory:
            message=service.safe_failure(directory,'test',RuntimeError('PRIVATE_KEY_AND_PROMPT_SENTINEL'))
            log=(Path(directory)/'outputs/pokemon/ui/errors.jsonl').read_text()
            self.assertNotIn('PRIVATE_KEY_AND_PROMPT_SENTINEL',message+log)
            self.assertIn('RuntimeError',log)

    def test_card_expands_retrieved_row_preserves_zero_stats_and_omits_false_flags(self):
        chain={'edges':[{'from_species_id':1,'from':'one','to_species_id':2,'to':'two',
                          'conditions':[{'id':'1','version_group':'test','minimum_level':'20',
                                         'relative_physical_stats':'0','needs_overworld_rain':'0',
                                         'needs_multiplayer':'1','required_pokemon_form_id':'1'}]}]}
        doc={'doc_id':'test','content':json.dumps(chain)}
        source={'kind':'evolution_chain','doc_ids':['test'],'chunk_index':'0:0:0','number':2,
                'title':'test chain','source_url':'https://example.org','source_item_id':'pokemon-species:1'}
        cards=cards_from_evidence([source,{**source,'chunk_index':'0:0:1'}],{'test':doc},
            {'pokemon-species:1':{'name_ko':'갑'},'pokemon-species:2':{'name_ko':'을'}},'https://example.org/names')
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['from'],'갑')
        self.assertTrue(cards[0]['expanded_from_parent_row'])
        labels={r['조건']:r['값'] for r in cards[0]['conditions']}
        self.assertEqual(labels['공격·방어 관계 값(원문)'],'0')
        self.assertNotIn('필드의 비 필요',labels)
        self.assertEqual(labels['멀티플레이 필요'],'필요')


@unittest.skipUnless((ROOT/'dataset/pokemon/indexing/metadata_manifest.json').exists(), 'Local ignored Pokemon data/index required')
class StreamlitContracts(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT/'streamlit_lab/app.py'),default_timeout=60)

    def test_real_cached_chat_keeps_sources_when_switching_items_and_reports_progress(self):
        at=self.app().run()
        self.assertFalse(at.exception)
        at.chat_input[0].set_value('피카츄가 라이츄로 진화하는 조건을 찾아줘').run(timeout=60)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.session_state['chat_histories']['pokemon-species:25']),2)
        self.assertTrue(any('thunder-stone' in m.value for m in at.markdown))
        self.assertTrue(any(service.STAGES['generate'] in m.value for m in at.markdown))
        at.selectbox(key='selected_item').set_value('pokemon-species:133').run()
        self.assertEqual(len(at.chat_message),0)
        at.selectbox(key='selected_item').set_value('pokemon-species:25').run()
        self.assertEqual(len(at.chat_message),2)
        self.assertTrue(any('답변에 사용한 근거' in e.label for e in at.expander))
        next(b for b in at.button if b.label=='이 포켓몬의 대화 지우기').click().run()
        self.assertEqual(at.session_state['chat_histories']['pokemon-species:25'],[])

    def test_missing_key_is_shown_without_exposing_key(self):
        with patch.dict(os.environ,{'GMS_KEY':''}),patch('src.pokemon.ui_service.dotenv_values',return_value={}):
            at=self.app().run()
            self.assertFalse(at.exception)
            self.assertTrue(any('키가 설정되지 않았습니다' in w.value for w in at.warning))
            self.assertTrue(at.chat_input[0].disabled)

    def test_missing_index_uses_actual_absent_manifest_configuration(self):
        cfg=service.load_config(ROOT)
        cfg['metadata']['manifest_path']='dataset/pokemon/absent-ui-test-manifest.json'
        with patch('src.pokemon.ui_service.load_config',return_value=cfg):
            at=self.app().run()
            self.assertFalse(at.exception)
            self.assertTrue(any('항목 색인이 없습니다' in w.value for w in at.warning))
            self.assertTrue(at.chat_input[0].disabled)

    def test_source_history_error_and_pick_callback_have_correct_ui_behavior(self):
        at=self.app().run()
        at.radio(key='view').set_value('조건 탐색').run()
        item=json.loads((ROOT/'dataset/pokemon/items.json').read_text(encoding='utf-8'))[0]
        at.session_state['exploration']={'plan':plan(types=[item['types'][0]]),'conditions':['test'],'count':1,'items':[item]}
        at.run()
        at.button(key='choose_'+item['item_id']).click().run()
        self.assertEqual(at.session_state['selected_item'],item['item_id'])
        self.assertEqual(at.session_state['view'],'대화')
        with patch('src.pokemon.rag.answer_question',side_effect=RuntimeError('PRIVATE_SENTINEL')):
            # app imports the function each rerun, so the backend failure is reached by the real UI.
            at.chat_input[0].set_value('테스트 질문').run()
            self.assertFalse(at.exception)
            self.assertTrue(at.error)
            self.assertTrue(all('PRIVATE_SENTINEL' not in e.value for e in at.error))

    def test_actual_cached_search_renders_matches_empty_and_subjective_notice(self):
        at=self.app().run()
        at.radio(key='view').set_value('조건 탐색').run()
        cases=[('1세대 전기 타입 중 몸무게 10kg 이하',2),
               ('1세대 드래곤 타입 중 몸무게 0.1kg 이하',0),
               ('귀엽고 대전에서 무조건 이기는 포켓몬',0)]
        for query,count in cases:
            at.text_input(key='explore_query').set_value(query)
            next(b for b in at.button if b.label=='조건에 맞는 포켓몬 찾기').click().run(timeout=60)
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state['exploration']['count'],count)
        self.assertTrue(any('판단하기 어려운 조건' in w.value for w in at.warning))

    def test_quick_exploration_moves_query_to_real_filter_and_selects_result(self):
        at=self.app().run()
        at.text_input(key='quick_explore').set_value('1세대 전기 타입 중 몸무게 10kg 이하')
        next(b for b in at.button if b.label=='조건으로 탐색하기').click().run(timeout=60)
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['view'],'조건 탐색')
        self.assertEqual({i['species_id'] for i in at.session_state['exploration']['items']},{25,81})
        at.button(key='choose_pokemon-species:81').click().run()
        self.assertEqual(at.session_state['selected_item'],'pokemon-species:81')
        self.assertEqual(at.session_state['view'],'대화')

    def test_actual_cached_evolution_cards_render_condition_rows_and_sources(self):
        at=self.app().run()
        at.radio(key='view').set_value('진화 조건').run()
        next(b for b in at.button if b.label=='진화 조건 살펴보기').click().run(timeout=60)
        self.assertFalse(at.exception)
        result=at.session_state['evolution_results']['pokemon-species:25']
        self.assertEqual(len(result['cards']),3)
        self.assertEqual(len(at.dataframe),3)
        self.assertTrue(any('조건 원문' in m.value and '[근거 ' in m.value for m in at.markdown))


if __name__=='__main__':
    unittest.main()

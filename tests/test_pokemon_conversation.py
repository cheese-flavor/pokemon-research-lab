"""Global routing must not mix identities or reuse another species' citations."""
import unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from src.pokemon.conversation import answer_global, named_items

ITEMS=[{'item_id':'pokemon-species:'+str(n),'species_id':n,'name_ko':ko,'name':en}
       for n,ko,en in [(4,'파이리','charmander'),(25,'피카츄','pikachu'),(26,'라이츄','raichu'),
                       (122,'마임맨','mr-mime'),(439,'흉내내','mime-jr'),(1025,'복숭악동','pecharunt')]]
ITEMS.append({'item_id':'pokemon-species:151','species_id':151,'name_ko':'뮤','name':'mew'})


class GlobalConversation(unittest.TestCase):
    def test_name_number_english_boundaries_and_longest_match(self):
        self.assertEqual([i['species_id'] for i in named_items('파이리와 #1025, 25번',ITEMS)],[4,1025,25])
        self.assertEqual(named_items('notpikachunot',ITEMS),[])
        self.assertEqual([i['species_id'] for i in named_items('뮤의 특성',ITEMS)],[151])
        self.assertEqual(named_items('커뮤니티',ITEMS),[])
        self.assertEqual([i['species_id'] for i in named_items('#25와 파이리',ITEMS)],[25,4])

    def test_new_name_overrides_previous_topic_and_followup_keeps_topic(self):
        calls=[]
        def answer(root,config,item,q,**kwargs):
            calls.append(item)
            return {'answer':'정보 [근거 2, 4]','sources':[{'number':2},{'number':4}]}
        result=answer_global('.',{},ITEMS,'파이리의 도감 설명', ['pokemon-species:25'],answer_fn=answer)
        self.assertEqual(calls,['pokemon-species:4'])
        self.assertEqual(result['answer'],'정보 [근거 1, 2]')
        answer_global('.',{},ITEMS,'그 포켓몬의 특성은?',result['topic_ids'],answer_fn=answer)
        self.assertEqual(calls[-1],'pokemon-species:4')
        answer_global('.',{},ITEMS,'진화 조건은?',result['topic_ids'],answer_fn=answer)
        self.assertEqual(calls[-1],'pokemon-species:4')

    def test_multiple_species_sources_are_renumbered_and_other_names_removed(self):
        calls=[]
        def answer(root,config,item,q,**kwargs):
            calls.append((item,q))
            return {'answer':'정보 [근거 1]','sources':[{'number':1,'source_item_id':item}]}
        result=answer_global('.',{},ITEMS,'파이리와 피카츄의 특성을 각각 알려줘',answer_fn=answer)
        self.assertEqual([s['number'] for s in result['sources']],[1,2])
        self.assertNotIn('피카츄',calls[0][1])
        self.assertNotIn('파이리',calls[1][1])

    def test_no_identity_does_not_guess_from_browsed_profile(self):
        result=answer_global('.',{},ITEMS,'누가 좋아?')
        self.assertEqual(result['topic_ids'],[])
        self.assertEqual(result['sources'],[])

    def test_invalid_number_never_falls_back_to_previous_species(self):
        result=answer_global('.',{},ITEMS,'#9999의 도감 설명', ['pokemon-species:25'])
        self.assertEqual(result['sources'],[])


ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT/'dataset/pokemon/ingestion/active.json').exists(),'Local prepared corpus required')
class PreparedReuse(unittest.TestCase):
    def test_complete_generation_reuses_without_planner_or_embedding(self):
        from src.pokemon.ui_service import load_config
        from src.pokemon.ingestion import prepare_documents
        with patch('src.pokemon.ingestion.GmsJson',side_effect=AssertionError('Planner must not be called')):
            result=prepare_documents(ROOT,load_config(ROOT),'25','피카츄의 도감 설명',offline=True,reuse_prepared=True)
        self.assertTrue(result['reused_prepared'])
        self.assertEqual(result['embedding_calls'],0)

    def test_version_expression_and_changed_chunk_generation_use_planner(self):
        from src.pokemon.ui_service import load_config
        from src.pokemon.ingestion import prepare_documents
        cfg=load_config(ROOT)
        changed=deepcopy(cfg);changed['documents']['chunk_size_chars']=791
        for settings,question in [(cfg,'피카츄의 X 도감 설명'),(cfg,'피카츄의 shield 도감 설명'),
                                  (changed,'피카츄의 도감 설명')]:
            with patch('src.pokemon.ingestion.GmsJson',side_effect=RuntimeError('planner path reached')):
                with self.assertRaisesRegex(RuntimeError,'planner path reached'):
                    prepare_documents(ROOT,settings,'25',question,offline=True,reuse_prepared=True)


if __name__=='__main__':
    unittest.main()

"""Task-6 live objective-condition checks and cached evolution-card verification."""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.pokemon.embeddings import write_json
from src.pokemon.explore import explore_items, matches
from src.pokemon.evolution import load_evolution_cards

QUERIES=[('objective','1세대 전기 타입 중 몸무게 10kg 이하'),
         ('units','키 50cm 이하이고 몸무게 1000g 이하인 포켓몬'),
         ('subjective','귀엽고 대전에서 무조건 이기는 포켓몬'),
         ('empty','1세대 드래곤 타입 중 몸무게 0.1kg 이하')]


def main():
    config=tomllib.loads((ROOT/'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    files=[ROOT/'dataset/pokemon'/n for n in ('items.json','documents.json','documents_ko_enriched.json')]
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    summaries=[]
    for name,query in QUERIES:
        print('Verifying UI search '+name,flush=True)
        result=explore_items(ROOT,config,query)
        assert all(matches(i,result['plan']) for i in result['items'])
        if name=='objective':
            assert {i['species_id'] for i in result['items']}=={25,81}
        elif name=='units':
            assert all(i['height_m']<=0.5 and i['weight_kg']<=1 for i in result['items'])
            filters={(c['field'],c['operator']):c['value'] for c in result['plan']['conditions']}
            assert filters['height_m','lte']==0.5 and filters['weight_kg','lte']==1
        elif name=='subjective':
            assert not result['items'] and (result['plan']['unsupported'] or result['plan']['ambiguous'])
            assert result['diagnostics']['embedding_calls']==0
        else:
            assert result['count']==0 and not result['plan']['unsupported']
        replay=explore_items(ROOT,config,query,offline=True)
        assert replay['plan']==result['plan'] and replay['items']==result['items']
        assert replay['diagnostics']['llm_calls']==replay['diagnostics']['embedding_calls']==0
        summaries.append({'case':name,'matched_count':result['count'],'conditions':result['conditions'],
                          'unsupported_count':len(result['plan']['unsupported']),'diagnostics':result['diagnostics'],
                          'offline_replay_identical':True})
    cards=load_evolution_cards(ROOT,config,'pokemon-species:25',offline=True)
    assert len(cards['cards'])==3 and all(c['source_item_id']=='pokemon-species:25' for c in cards['cards'])
    assert all(c['citation_number']>=2 and c['expanded_from_parent_row'] for c in cards['cards'])
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    summary={'search_cases':summaries,'evolution_cards':len(cards['cards']),'all_inputs_unchanged':True,
             'scope':'four language-condition cases and one evolution case; UI AppTest runs separately'}
    write_json(ROOT/'outputs/pokemon/ui/verification.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(f'UI service verification failed ({type(error).__name__}).',file=sys.stderr)
        sys.exit(1)

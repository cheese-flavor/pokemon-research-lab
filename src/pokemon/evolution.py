"""Evidence-backed cards, expanding retrieved fragments to their complete parent condition row."""
import json
from pathlib import Path

from .embeddings import write_json
from .ingestion import prepare_documents
from .retrieval import Retriever

FLAG_FIELDS={'needs_overworld_rain','turn_upside_down','needs_multiplayer','near_special_rock'}
IDENTITY_FIELDS={'id','evolved_species_id','evolution_trigger_id','version_group_id','is_default','version_group',
                 'required_pokemon_form_id','evolved_pokemon_form_id'}
LABELS={'minimum_level':'최소 레벨','minimum_happiness':'친밀도 최솟값','minimum_beauty':'아름다움 최솟값',
        'minimum_affection':'애정도 최솟값','trigger_name':'진화 계기','trigger_item_name':'사용 아이템(원문)',
        'held_item_name':'지닌 아이템(원문)','time_of_day':'시간대(원문)','needs_overworld_rain':'필드의 비 필요',
        'turn_upside_down':'기기 뒤집기 필요','needs_multiplayer':'멀티플레이 필요','near_special_rock':'특수 바위 근처 필요',
        'location_id':'장소 ID','region_id':'지역 ID','relative_physical_stats':'공격·방어 관계 값(원문)',
        'trigger_item_id':'사용 아이템 ID','held_item_id':'지닌 아이템 ID'}


def cards_from_evidence(evidence,by_doc,by_item,names_url):
    cards=[]
    seen=set()
    for source in evidence:
        if source['kind']!='evolution_chain':
            continue
        doc=by_doc[source['doc_ids'][0]]
        chain=json.loads(doc['content'])
        pointer=source['chunk_index'].split(':')
        if pointer[0]=='no-edges':
            continue
        edge_index,condition_index=int(pointer[0]),int(pointer[1])
        key=(doc['doc_id'],edge_index,condition_index)
        if key in seen:
            continue
        seen.add(key)
        edge=chain['edges'][edge_index]
        condition=edge['conditions'][condition_index]
        rows=[]
        for field,value in condition.items():
            if field in IDENTITY_FIELDS or value in ('',None) or (field in FLAG_FIELDS and str(value)=='0'):
                continue
            rows.append({'조건':LABELS.get(field,field),'값':'필요' if field in FLAG_FIELDS else str(value)})
        def name(number,fallback):
            return by_item.get(f'pokemon-species:{number}',{}).get('name_ko') or fallback
        cards.append({'from':name(edge['from_species_id'],edge['from']), 'to':name(edge['to_species_id'],edge['to']),
            'conditions':rows,'version_group':condition.get('version_group','미지정'),
            'required_form_id':condition.get('required_pokemon_form_id','미지정'),
            'evolved_form_id':condition.get('evolved_pokemon_form_id','미지정'),
            'condition_id':condition.get('id','미지정'),'citation_number':source['number'],'title':source['title'],
            'source_url':source['source_url'],'source_urls':source.get('source_urls',[]),'names_source_url':names_url,
            'source_item_id':source['source_item_id'],'expanded_from_parent_row':True})
    return cards


def load_evolution_cards(root,config,item,offline=False,progress=None):
    root=Path(root)
    # Exact identity is resolved before asking the model.
    items=json.loads((root/config['metadata']['items_path']).read_text(encoding='utf-8'))
    selected=next(i for i in items if item in (i['item_id'],i['name_ko'],i['name'],str(i['species_id'])))
    question=selected['name_ko']+'의 진화 조건을 알려줘'
    prepare_documents(root,config,selected['item_id'],question,offline,progress)
    retriever=Retriever(root,config,offline)
    if progress:
        progress('retrieve')
    found=retriever.retrieve(selected['item_id'],question,kinds=['evolution_chain'])
    cards=cards_from_evidence(found['evidence'],retriever.source.by_doc,retriever.source.by_item,
                              retriever.source.source_urls['pokemon_species_names'])
    result={'cards':cards,'warnings':found['warnings'],'item_id':selected['item_id'],
            'scope':'검색된 조건 일부. 같은 행은 AND, 다른 행은 OR. 특정 게임 적용·완전성 미확인.'}
    write_json(root/'outputs/pokemon/ui/evolution'/(selected['item_id'].split(':')[-1]+'.json'),result)
    return result

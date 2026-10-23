"""Run bounded task-5 grounding cases and Top-k comparisons; no UI or RAG ablation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.pokemon.citations import citation_numbers
from src.pokemon.embeddings import write_json
from src.pokemon.rag import answer_question
from src.pokemon.retrieval import Retriever

CASES=[
    {'id':'evolution','item':'25','question':'피카츄가 라이츄로 진화하는 조건을 찾아줘'},
    {'id':'branches','item':'133','question':'이브이의 진화 분기와 조건을 비교할 자료를 찾아줘'},
    {'id':'translation','item':'1008','question':'미라이돈의 바이올렛 도감 설명을 한국어로 찾아줘'},
    {'id':'versions','item':'25','question':'피카츄의 X와 Y 버전 도감 설명을 비교해 줘','versions':['x','y'],'prepare':False},
    {'id':'unsupported','item':'25','question':'피카츄가 기술을 배우는 모든 레벨은?','prepare':False},
    {'id':'different_item','item':'25','question':'리자몽의 도감 설명을 알려줘','prepare':False},
    {'id':'missing_version','item':'1008','question':'미라이돈의 레드 버전 도감 설명을 알려줘','versions':['red'],'prepare':False},
    {'id':'metadata','item':'25','question':'피카츄의 현재 기본 형태 타입과 키를 알려줘','prepare':False},
]


def main():
    config=tomllib.loads((ROOT/'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    files=[ROOT/'dataset/pokemon'/n for n in ('items.json','documents.json','documents_ko_enriched.json')]
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    reports=[]
    for case in CASES:
        print('Verifying '+case['id'],flush=True)
        args={k:v for k,v in case.items() if k!='id'}
        result=answer_question(ROOT,config,**args)
        assert result['trace']==['retrieve','generate']
        assert result['evidence'][0]['evidence_type']=='metadata'
        assert all(e['item_id']==result['selected_item_id']==e['source_item_id'] for e in result['evidence'])
        assert citation_numbers(result['answer'])==[s['number'] for s in result['sources']]
        assert result['diagnostics']['evidence_tokens']<=config['retrieval']['context_budget_tokens']
        if case['id'] in ('unsupported','different_item','missing_version'):
            assert result['status']=='insufficient'
        if case['id'] in ('unsupported','different_item'):
            assert result['citation_notice'] and result['diagnostics']['answer_calls']==0 and not result['sources']
        if case['id']=='translation':
            assert any(s['is_machine_translation'] for s in result['sources']) and '생성 한국어 번역' in result['answer']
            assert all(s['versions']==['violet'] for s in result['sources'] if s['evidence_type']=='external_document')
        if case['id']=='versions':
            assert {'x','y'}<={v for s in result['sources'] for v in s['versions']}
        if case['id']=='metadata':
            assert 1 in citation_numbers(result['answer'])
        if case['id']=='evolution':
            assert 'thunder-stone' in result['answer'] and '게임' in result['answer']
        replay=answer_question(ROOT,config,**args,offline=True)
        assert replay['answer']==result['answer'] and replay['sources']==result['sources']
        assert replay['diagnostics']['answer_calls']==replay['diagnostics']['embedding_calls']==0
        reports.append({'case':case['id'],'status':result['status'],'evidence_count':len(result['evidence']),
                        'used_citation_count':len(result['sources']),'diagnostics':result['diagnostics'],
                        'timings':result['timings'],'offline_replay_identical':True})
    comparisons=[]
    for top_k in (3,5,8):
        changed=deepcopy(config)
        changed['retrieval']['document_top_k']=top_k
        retriever=Retriever(ROOT,changed,offline=True)
        found=retriever.retrieve('133',CASES[1]['question'],kinds=['evolution_chain'])
        comparisons.append({'top_k':top_k,'external_evidence_count':len(found['evidence'])-1,
                            'evidence_tokens':found['diagnostics']['evidence_tokens']})
    counts=[r['external_evidence_count'] for r in comparisons]
    assert counts[:2]==[3,5] and 5<=counts[2]<=8
    assert all(r['evidence_tokens']<=config['retrieval']['context_budget_tokens'] for r in comparisons)
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    summary={'cases':reports,'top_k_comparisons':comparisons,'all_inputs_unchanged':True,
             'scope':'structural grounding assertions, not independent factual accuracy scoring'}
    write_json(ROOT/'outputs/pokemon/rag/verification.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(f'RAG verification failed ({type(error).__name__}).',file=sys.stderr)
        sys.exit(1)

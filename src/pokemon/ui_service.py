"""Small UI-facing service boundary, readiness checks and per-item session helpers."""
import json
import os
from pathlib import Path
import tomllib
import uuid

from dotenv import dotenv_values

from .store import read_collection

STAGES={'search_queries':'질문에 맞는 검색어를 정리하고 있어요', 'source_search':'관련 자료를 찾고 있어요',
        'documents_reused':'준비된 설명 자료를 재사용하고 있어요',
        'candidate_selection':'질문에 필요한 자료를 고르고 있어요','document_indexing':'설명 자료를 준비하고 있어요',
        'documents_ready':'설명 자료를 준비했어요','retrieve':'답변의 근거를 찾고 있어요','generate':'근거를 확인하며 답변하고 있어요',
        'conditions':'탐색 조건을 해석하고 있어요','condition_filter':'실제 속성과 조건을 대조하고 있어요'}


def load_config(root):
    return tomllib.loads((Path(root)/'config/pokemon_rag.toml').read_text(encoding='utf-8'))


def load_items(root,config):
    return json.loads((Path(root)/config['metadata']['items_path']).read_text(encoding='utf-8'))


def readiness(root,config):
    root=Path(root)
    key_configured=bool(os.environ.get('GMS_KEY') or dotenv_values(root/'streamlit_lab/.env').get('GMS_KEY'))
    meta_count=doc_count=0
    issues=[]
    try:
        path=root/config['metadata']['manifest_path']
        if path.exists():
            meta=json.loads(path.read_text(encoding='utf-8'))['summary']
            meta_count=read_collection(root/config['metadata']['store_path'],config['metadata']['collection'],meta['index_signature']).count()
    except Exception:
        issues.append('metadata')
    try:
        path=root/'dataset/pokemon/ingestion/active.json'
        if path.exists():
            active=json.loads(path.read_text(encoding='utf-8'))
            doc_count=read_collection(root/config['metadata']['store_path'],active['collection'],active['signature']).count()
    except Exception:
        issues.append('documents')
    if meta_count!=config['metadata']['expected_count']:
        issues.append('metadata')
    return {'key_configured':key_configured,'metadata_count':meta_count,'document_count':doc_count,
            'issues':list(set(issues)),'ready':key_configured and 'metadata' not in issues and 'documents' not in issues}


def history_for(state,item_id):
    return state.setdefault('chat_histories',{}).setdefault(item_id,[])


def save_reply(state,item_id,question,result,versions):
    history_for(state,item_id).extend([{'role':'user','content':question,'versions':versions},
        {'role':'assistant','content':result['answer'],'sources':result['sources'],
         'citation_notice':result['citation_notice'],'warnings':result.get('warnings',[]),'versions':versions}])


def select_item(state,item_id):
    state['selected_item']=item_id
    state['view']='대화'


def clear_history(state,item_id):
    state.setdefault('chat_histories',{})[item_id]=[]


def safe_failure(root,operation,error):
    identity=uuid.uuid4().hex[:10]
    # No exception messages, local variables, request bodies or secrets in logs.
    path=Path(root)/'outputs/pokemon/ui/errors.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as handle:
        handle.write(json.dumps({'request_id':identity,'operation':operation,'error_type':type(error).__name__})+'\n')
    return '요청을 완료하지 못했습니다. 설정과 연결 상태를 확인한 뒤 다시 시도해 주세요. 확인 번호: '+identity

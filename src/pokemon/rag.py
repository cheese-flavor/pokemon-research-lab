"""Application entry point: optional ingestion, then the two-node answer graph."""
import json
from pathlib import Path
import re
import time

from langsmith import tracing_context

from .data import fingerprint
from .embeddings import write_json
from .graph import build_graph
from .ingestion import ItemChangeRequired, prepare_documents
from .llm import GmsJson
from .prompts import KINDS
from .retrieval import Retriever


def known_unsupported(question):
    return bool(re.search(r'기술.*(습득|배우|레벨)|출현\s*(장소|위치)|대전.*(승률|순위)',question))


def infer_kinds(question):
    if '진화' in question:
        return ['evolution_chain']
    if '도감' in question:
        return ['species_description']
    if '특성' in question:
        return ['ability_description']
    return KINDS


def foreign_item_requested(question, selected, source):
    """Longest exact name matches; evolution relatives are allowed only for evolution questions."""
    text=question.casefold()
    matches=[]
    for item in source.items:
        for name in (item['name_ko'],item['name']):
            if len(name)<2:
                continue
            for match in re.finditer(re.escape(name.casefold()),text):
                matches.append((match.start(),match.end(),item['item_id']))
    named={identity for start,stop,identity in matches if not any(
        left<=start and right>=stop and right-left>stop-start for left,right,_ in matches)}
    allowed={selected['item_id']}
    if '진화' in question:
        for doc in source.own(selected['item_id']):
            if doc['kind']=='evolution_chain':
                for edge in json.loads(doc['content'])['edges']:
                    allowed.update(f'pokemon-species:{edge[k]}' for k in ('from_species_id','to_species_id'))
    return bool(named-allowed)


def answer_question(root, config, item, question, versions=None, kinds=None, offline=False, prepare=True, progress=None):
    if not question.strip() or len(question)>4000:
        raise ValueError('Question must contain 1-4000 characters')
    root=Path(root)
    started=time.monotonic()
    preparation={}
    unsupported=['known uncollected domain'] if known_unsupported(question) else []
    block_reason=''
    if prepare and not unsupported:
        try:
            preparation=prepare_documents(root,config,item,question,offline,progress,reuse_prepared=True)
            unsupported=preparation['unsupported']
        except ItemChangeRequired:
            block_reason='selected item differs from requested item'
    prepare_seconds=round(time.monotonic()-started,3)
    retriever=Retriever(root,config,offline)
    selected=retriever.source.resolve(item)
    if foreign_item_requested(question,selected,retriever.source):
        block_reason='selected item differs from requested item'
    llm=GmsJson(config['gms'],root/config['retrieval']['answer_cache_path'],root/'streamlit_lab/.env',offline)
    graph=build_graph(retriever,llm,progress)
    state={'item':selected['item_id'],'question':question,
           'versions':versions if versions is not None else ([preparation['requested_version']] if preparation.get('requested_version') else []),
           'kinds':kinds or preparation.get('requested_kinds') or infer_kinds(question),
           'unsupported':unsupported,'block_reason':block_reason}
    # Do not export document bodies or prompts through ambient tracing configuration.
    with tracing_context(enabled=False):
        result=graph.invoke(state,config={'callbacks':[]})
    result['timings'].update(prepare_seconds=prepare_seconds,total_seconds=round(time.monotonic()-started,3))
    result['diagnostics'].update(answer_calls=llm.calls,answer_cache_hits=llm.hits,answer_tokens=llm.tokens,
                                 preparation_llm_calls=preparation.get('llm_calls',0),
                                 preparation_embedding_calls=preparation.get('embedding_calls',0))
    result['diagnostics']['reused_prepared']=preparation.get('reused_prepared',False)
    key=fingerprint([state,config['retrieval'],result['evidence']])
    write_json(root/'outputs/pokemon/rag/answers'/(key+'.json'),result)
    write_json(root/'outputs/pokemon/rag/graph.json',graph.get_graph().to_json())
    return result

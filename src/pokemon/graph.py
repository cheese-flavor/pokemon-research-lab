"""Exactly two LangGraph nodes: retrieve and generate. No secrets in state."""
import time
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from .citations import NOTICE, prompt_evidence, used_sources, validate_answer
from .prompts import ANSWER_PROMPT, ANSWER_SCHEMA


class RagState(TypedDict, total=False):
    item: str
    question: str
    versions: list[str]
    kinds: list[str]
    unsupported: list[str]
    block_reason: str
    selected_item_id: str
    selected_name: str
    evidence: list[dict]
    warnings: list[str]
    diagnostics: dict
    answer: str
    status: str
    sources: list[dict]
    citation_notice: str
    timings: dict
    trace: list[str]


def build_graph(retriever, llm, progress=None):
    def retrieve(state):
        started = time.monotonic()
        if progress:
            progress('retrieve')
        found = retriever.retrieve(state['item'],state['question'],state.get('versions'),state.get('kinds'),
                                   blocked=bool(state.get('unsupported') or state.get('block_reason')))
        return {**found,'timings':{'retrieve_seconds':round(time.monotonic()-started,3)},'trace':['retrieve']}

    def generate(state):
        started=time.monotonic()
        if progress:
            progress('generate')
        evidence=state['evidence']
        if state.get('block_reason'):
            answer='질문할 포켓몬을 변경한 뒤 다시 질문해 주세요.'
            status='insufficient'
        elif state.get('unsupported'):
            answer='해당 질문은 현재 수집 범위에 없어 수집한 문서에서 확인되지 않습니다.'
            status='insufficient'
        else:
            payload={'selected_item':state['selected_item_id'],'selected_name':state['selected_name'],
                     'question':state['question'],'requested_versions':state.get('versions',[]),
                     'evidence':prompt_evidence(evidence),'warnings':state['warnings']}
            result=llm.run('pokemon_answer_v1',ANSWER_PROMPT,payload,ANSWER_SCHEMA,
                           lambda r: validate_answer(r,evidence))
            answer,status=result['answer'],result['status']
        cited=used_sources(answer,evidence)
        generated=[s['number'] for s in cited if s.get('is_machine_translation')]
        if generated:
            answer+='\n\n※ '+', '.join(f'[근거 {n}]' for n in generated)+'에는 영어 원문을 보완한 생성 한국어 번역이 사용되었습니다.'
        evolution=[s['number'] for s in cited if s['kind']=='evolution_chain']
        if evolution:
            answer+='\n\n※ 진화 조건은 수집 체인 기준이며, 특정 게임에서의 적용·완전성은 확인되지 않습니다.'
        validate_answer({'answer':answer,'status':status},evidence)
        return {'answer':answer,'status':status,'sources':used_sources(answer,evidence),
                'citation_notice':'' if cited else NOTICE,
                'timings':{**state['timings'],'generate_seconds':round(time.monotonic()-started,3)},
                'trace':state['trace']+['generate']}

    graph=StateGraph(RagState)
    graph.add_node('retrieve',retrieve)
    graph.add_node('generate',generate)
    graph.add_edge(START,'retrieve')
    graph.add_edge('retrieve','generate')
    graph.add_edge('generate',END)
    return graph.compile()

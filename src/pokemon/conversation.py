"""Global session chat with deterministic identity routing and scoped citations."""
import re
import time
from .citations import CITATION, citation_numbers


def named_items(question, items):
    text=question.casefold()
    matches=[]
    for item in items:
        for name in (item['name_ko'],item['name']):
            if len(name)<2 and name.isascii():
                continue
            pattern=re.escape(name.casefold())
            if name.isascii():
                pattern=r'(?<![a-z])'+pattern+r'(?![a-z])'
            elif len(name)==1:
                pattern=r'(?<![가-힣a-z])'+pattern+r'(?=$|[^가-힣a-z]|[은는이가의을를와과도랑에])'
            matches.extend((m.start(),m.end(),item['item_id']) for m in re.finditer(pattern,text))
    for m in re.finditer(r'(?:#\s*|도감\s*)(\d{1,4})(?!\d)|(?<!\d)(\d{1,4})\s*번',text):
        matches.append((m.start(),m.end(),'pokemon-species:'+str(int(m.group(1) or m.group(2)))))
    matches=[m for m in matches if not any(a<=m[0] and b>=m[1] and b-a>m[1]-m[0] for a,b,_ in matches)]
    ids=[m[2] for m in sorted(matches)]
    by_id={i['item_id']:i for i in items}
    return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]


def answer_global(root,config,items,question,topic_ids=None,versions=None,progress=None,answer_fn=None,previous_question=None):
    from .rag import answer_question
    answer_fn=answer_fn or answer_question
    if not question.strip() or len(question)>4000:
        raise ValueError('Question must contain 1-4000 characters')
    started=time.monotonic()
    targets=named_items(question,items)
    if not targets and re.search(r'세대|(?:키|몸무게|종족값).*(?:이하|이상|미만|초과)|타입.*(?:찾|추천)|조건.*(?:찾|추천)',question):
        from .explore import explore_items
        result=explore_items(root,config,question,progress=progress)
        if result['plan']['unsupported'] or result['plan']['ambiguous'] or not result['conditions']:
            text='현재 자료로 판단하기 어려운 조건입니다. 세대·타입·키·몸무게 등 확인 가능한 조건을 입력해 주세요.'
            sources=[]
        else:
            shown=result['items'][:12]
            text='조건: '+' / '.join(result['conditions'])+f"\n\n일치하는 포켓몬은 {result['count']}종입니다."
            sources=[]
            for n,item in enumerate(shown,1):
                text+=f"\n- #{item['species_id']:04d} {item['name_ko']} [근거 {n}]"
                sources.append({'number':n,'title':item['name_ko']+' 기본 형태 메타데이터',
                    'evidence_type':'metadata','kind':'metadata','source_url':item['source_urls'][0],
                    'source_item_id':item['item_id'],'language':'ko','versions':[],'is_machine_translation':False})
            if result['count']>12:
                text+='\n\n12종을 표시했습니다. 조건을 추가하면 결과를 좁힐 수 있습니다.'
        return {'answer':text,'sources':sources,'citation_notice':'' if sources else '인용된 근거가 없습니다.',
                'topic_ids':[],'timings':{'total_seconds':round(time.monotonic()-started,3)}}
    # A named evolution destination is evidence context, not a second conversation target.
    if len(targets)>1 and '진화' in question and re.search(r'로\s*진화|으로\s*진화',question) and not re.search(r'비교|각각|차이',question):
        targets=targets[:1]
    followup=not targets
    if not targets and not re.search(r'#\s*\d|도감\s*\d|\d\s*번',question):
        by_id={i['item_id']:i for i in items}
        targets=[by_id[i] for i in (topic_ids or []) if i in by_id]
    if not targets or len(targets)>3:
        return {'answer':'궁금한 포켓몬 이름이나 도감 번호를 알려주세요. 한 번에 최대 3종을 질문할 수 있습니다.',
                'sources':[],'citation_notice':'인용된 근거가 없습니다.','topic_ids':[],
                'timings':{'total_seconds':round(time.monotonic()-started,3)}}
    sections=[]; sources=[]; diagnostics=[]
    for target in targets:
        scoped=(f'이전 질문: {previous_question[:1600]}\n후속 질문: {question}'
                if followup and previous_question else question)
        if len(targets)>1:
            for other in sorted(targets,key=lambda i:len(i['name_ko']),reverse=True):
                if other['item_id']!=target['item_id']:
                    for name in (other['name_ko'],other['name']):
                        scoped=re.sub(re.escape(name),'',scoped,flags=re.I)
            scoped=f"질문 대상은 {target['name_ko']} 한 종입니다. 이 종의 정보만 정리하세요. 다른 대상이나 비교 가능 여부를 안내하는 문장은 넣지 마세요. 요청: {scoped}"
        result=answer_fn(root,config,target['item_id'],scoped,versions=versions,progress=progress)
        offset=len(sources)
        mapping={s['number']:offset+n for n,s in enumerate(result['sources'],1)}
        text=CITATION.sub(lambda m:'[근거 '+', '.join(str(mapping[int(n)]) for n in m.group(1).split(','))+']',result['answer'])
        sections.append((f"### {target['name_ko']}\n\n" if len(targets)>1 else '')+text)
        sources.extend({**s,'number':mapping[s['number']]} for s in result['sources'])
        diagnostics.append(result.get('diagnostics',{}))
    answer='\n\n'.join(sections)
    if set(citation_numbers(answer))!={s['number'] for s in sources}:
        raise ValueError('Global citation registry mismatch')
    return {'answer':answer,'sources':sources,'citation_notice':'' if sources else '인용된 근거가 없습니다.',
            'topic_ids':[i['item_id'] for i in targets],'diagnostics':diagnostics,
            'timings':{'total_seconds':round(time.monotonic()-started,3)}}

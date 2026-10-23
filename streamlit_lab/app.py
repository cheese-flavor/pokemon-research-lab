"""Pokemon UI adapted from step7_skeleton: selection, chat, status and cited sources.

Run from the repository root: python -m streamlit run streamlit_lab/app.py
The original step7_skeleton.py remains an unchanged teaching example.
"""
from pathlib import Path
import sys

import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.pokemon import ui_service as service
from src.pokemon import ui_theme as theme
from src.pokemon.explore import explore_items
from src.pokemon.evolution import load_evolution_cards
from src.pokemon.rag import answer_question

st.set_page_config(page_title='포켓몬 리서치 랩',page_icon=str(ROOT/'streamlit_lab/assets/pokemon/pikachu-watercolor.png'),layout='wide')
st.markdown('<style>'+(ROOT/'streamlit_lab/assets/pokemon.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)

try:
    config=service.load_config(ROOT)
    items=service.load_items(ROOT,config)
    ready=service.readiness(ROOT,config)
except Exception as error:
    st.error(service.safe_failure(ROOT,'startup',error))
    st.info('먼저 포켓몬 데이터를 준비해 주세요. 실행 안내는 프로젝트 README를 확인할 수 있습니다.')
    st.stop()
by_id={i['item_id']:i for i in items}
if 'selected_item' not in st.session_state:
    st.session_state.selected_item='pokemon-species:25'
if st.session_state.selected_item not in by_id:
    st.session_state.selected_item=items[0]['item_id']

def choose(identity):
    service.select_item(st.session_state,identity)

def clear_selected():
    service.clear_history(st.session_state,st.session_state.selected_item)

def open_exploration():
    st.session_state['explore_query']=st.session_state.get('quick_explore','').strip() or '1세대 전기 타입 중 몸무게 10kg 이하'
    st.session_state['view']='조건 탐색'
    st.session_state['run_exploration']=True


with st.sidebar:
    st.markdown(theme.brand(ROOT),unsafe_allow_html=True)
    st.subheader('함께 알아볼 포켓몬')
    identity=st.selectbox('포켓몬 이름 또는 번호',list(by_id),key='selected_item',
        format_func=lambda key:f"#{by_id[key]['species_id']:04d} {by_id[key]['name_ko']} · {by_id[key]['name']}")
    st.caption('목록을 열어 한국어·영문 이름이나 번호로 찾아보세요.')
    st.divider()
    st.write('**지식 준비 현황**')
    st.caption(f"포켓몬 {ready['metadata_count']:,}종 · 설명 {ready['document_count']:,}조각")
    st.caption('설명 자료는 질문에 맞춰 추가로 준비합니다.')
    st.button('이 포켓몬의 대화 지우기',on_click=clear_selected,width='stretch')
    st.divider()
    st.caption('기본 형태의 고정 자료를 사용합니다. 생성 번역과 게임별 범위는 근거에서 확인하세요.')
    with st.expander('빠른 도감'):
        for number in (25,1,2,3,4,5,6,7,8,9,81,133):
            item=by_id.get(f'pokemon-species:{number}')
            if item:
                st.button(f"#{number:04d} {item['name_ko']}",key=f'nav_{number}',on_click=choose,args=(item['item_id'],),width='stretch')

selected=by_id[identity]
st.markdown(theme.profile(ROOT,selected,compact=st.session_state.get('view')=='조건 탐색'),unsafe_allow_html=True)
st.caption('수치·타입은 고정 원본의 기본 형태 기준입니다. 특정 게임의 과거 수치를 보장하지 않습니다.')
view=st.radio('기능',['대화','조건 탐색','진화 조건'],horizontal=True,key='view',label_visibility='collapsed')

if not ready['key_configured']:
    st.warning('GMS 키가 설정되지 않았습니다. 로컬 streamlit_lab/.env의 GMS_KEY 설정을 확인해 주세요.')
if 'metadata' in ready['issues']:
    st.warning('포켓몬 항목 색인이 없습니다. 먼저 python scripts/index_pokemon_metadata.py를 실행해 주세요.')
if 'documents' in ready['issues']:
    st.warning('설명 자료를 읽지 못했습니다. 색인 설정과 저장소를 확인해 주세요.')
elif ready['document_count']==0:
    st.info('설명 색인이 아직 없습니다. 첫 질문에서 관련 자료를 준비합니다.')

def render_sources(sources,notice=''):
    if not sources:
        st.caption(notice or '답변에 인용된 근거가 없습니다.')
        return
    with st.expander(f'답변에 사용한 근거 {len(sources)}건'):
        for source in sources:
            st.markdown(f"**[근거 {source['number']}] {source['title']}**")
            kind='항목 메타데이터' if source['evidence_type']=='metadata' else '외부 설명 문서'
            version=', '.join(source.get('versions',[])) or '고정 스냅샷 / 게임 적용 범위 확인 필요'
            st.caption(f"{kind} · {source.get('language','')} · {version}")
            if source.get('is_machine_translation'):
                st.caption('생성 한국어 번역 · 공식 한국어 문구가 아닙니다.')
            st.markdown(f"[원문 보기]({source['source_url']})")
            if source.get('original_doc_id'):
                st.caption('영어 원문 문서 ID: '+source['original_doc_id'])
            extra=[u for u in source.get('source_urls',[]) if u!=source['source_url']]
            for n,url in enumerate(extra,1):
                st.markdown(f'[관련 원본 {n}]({url})')

def render_message(message):
    with st.chat_message(message['role']):
        st.markdown(message['content'])
        if message.get('versions'):
            st.caption('요청 버전: '+', '.join(message['versions']))
        if message['role']=='assistant':
            render_sources(message.get('sources',[]),message.get('citation_notice',''))

def run_with_status(label,operation):
    failure=None
    with st.status(label,expanded=True) as status:
        def progress(stage):
            text=service.STAGES.get(stage,'자료를 확인하고 있어요')
            status.update(label=text)
            status.write(text)
        try:
            result=operation(progress)
            status.update(label='완료했어요',state='complete',expanded=False)
            return result
        except Exception as error:
            status.update(label='요청을 완료하지 못했어요',state='error',expanded=False)
            failure=service.safe_failure(ROOT,view,error)
    # Keep recovery guidance visible even when the progress container is collapsed.
    if failure:
        st.error(failure)
    return None

if view=='대화':
    conversation,discovery=st.columns([2.4,1],gap='large')
    with discovery:
        with st.container(border=True,key='quick-discovery'):
            st.markdown('#### 조건으로 찾아보기')
            st.caption('세대·타입·키·몸무게 등 원하는 조건으로 포켓몬을 찾아보세요.')
            st.text_input('탐색 조건',key='quick_explore',placeholder='1세대 전기 타입 중 몸무게 10kg 이하')
            st.button('조건으로 탐색하기',on_click=open_exploration,type='primary',width='stretch',disabled=not ready['ready'],icon=':material/search:')
            st.caption('조건 탐색에서 해석한 조건과 실제 일치 결과를 확인할 수 있습니다.')
    with conversation:
        st.caption('도감·특성·진화 조건을 질문하고, 실제 사용한 원문을 확인하세요.')
        # Exact identifiers match the version fields in the source, avoiding guessed game mappings.
        import csv
        raw=ROOT/'dataset/pokemon/raw'/('bulk_'+selected['source_revision'])/'versions.csv'
        with raw.open(encoding='utf-8',newline='') as handle:
            versions=[r['identifier'] for r in csv.DictReader(handle)]
        requested=st.multiselect('게임 버전 지정 (선택)',versions,key='versions_'+identity,
                                placeholder='버전을 선택하거나 비워두세요',
                                help='지정한 버전의 자료가 없으면 다른 버전으로 대신 답하지 않습니다.')
        history=service.history_for(st.session_state,identity)
        for message in history:
            render_message(message)
        hint=st.empty()
        if not history:
            hint.info(f"예: {selected['name_ko']}의 도감 설명을 알려줘")
        live_reply=st.container()
        question=st.chat_input('이 포켓몬에 대해 궁금한 점을 물어보세요',disabled=not ready['ready'])
        if question:
            hint.empty()
            with live_reply:
                render_message({'role':'user','content':question,'versions':requested})
                result=run_with_status('질문에 맞는 자료를 준비하고 있어요',lambda progress:answer_question(
                    ROOT,config,identity,question,versions=requested or None,progress=progress))
                if result:
                    service.save_reply(st.session_state,identity,question,result,requested)
                    render_message(service.history_for(st.session_state,identity)[-1])
elif view=='조건 탐색':
    st.write('#### 원하는 조건으로 찾아보기')
    st.caption('세대·타입·키·몸무게·능력치·전설/환상 여부처럼 확인 가능한 조건을 입력해 주세요.')
    with st.form('explore_form'):
        query=st.text_input('어떤 포켓몬을 찾고 있나요?',placeholder='예: 1세대 전기 타입 중 몸무게 10kg 이하',key='explore_query')
        submitted=st.form_submit_button('조건에 맞는 포켓몬 찾기',disabled=not ready['ready'],type='primary')
    if submitted or st.session_state.pop('run_exploration',False):
        st.session_state.pop('exploration',None)
        result=run_with_status('조건을 확인하고 있어요',lambda progress:explore_items(ROOT,config,query,progress=progress))
        if result is not None:
            st.session_state.exploration=result
    result=st.session_state.get('exploration')
    if result:
        if result['plan']['unsupported'] or result['plan']['ambiguous'] or not result['conditions']:
            st.warning('현재 자료로 판단하기 어려운 조건입니다. 확인 가능한 조건으로 구체화해 주세요.')
            for text in result['plan']['unsupported']:
                st.write('• '+text)
        else:
            st.write('**해석한 조건:** '+' / '.join(result['conditions']))
            st.caption(f"일치하는 포켓몬 {result['count']}종 · 모든 표시 결과를 실제 속성과 대조했습니다.")
            if not result['items']:
                st.info('조건에 맞는 포켓몬이 없습니다. 조건을 바꿔 다시 찾아보세요.')
            for start in range(0,min(len(result['items']),12),2):
                for column,item in zip(st.columns(2),result['items'][start:start+2]):
                    with column,st.container(border=True):
                        st.markdown(theme.result_card(ROOT,item),unsafe_allow_html=True)
                        st.button('선택해서 대화하기',key='choose_'+item['item_id'],on_click=choose,args=(item['item_id'],),width='stretch')
            if len(result['items'])>12:
                st.caption('상위 12종을 표시했습니다. 조건을 추가하면 결과를 좁힐 수 있습니다.')
else:
    st.write('#### 진화 조건을 출처와 함께')
    st.caption('검색된 조건의 일부를 보여줍니다. 한 행 안은 모두 충족(AND), 다른 행은 대안(OR)입니다.')
    if st.button('진화 조건 살펴보기',type='primary',disabled=not ready['ready']):
        st.session_state.setdefault('evolution_results',{}).pop(identity,None)
        result=run_with_status('진화 자료를 확인하고 있어요',lambda progress:load_evolution_cards(
            ROOT,config,identity,progress=progress))
        if result is not None:
            st.session_state.setdefault('evolution_results',{})[identity]=result
    result=st.session_state.get('evolution_results',{}).get(identity)
    if result:
        st.info(result['scope'])
        if not result['cards']:
            st.info('검색된 자료에서 표시할 진화 조건을 확인하지 못했습니다. 진화가 없다는 뜻은 아닙니다.')
        for index,card in enumerate(result['cards'],1):
            with st.container(border=True):
                st.markdown(f"#### {card['from']} → {card['to']}")
                st.caption(f"조건 행 {card['condition_id']} · 기록된 버전 그룹: {card['version_group']}")
                st.dataframe(card['conditions'],hide_index=True,width='stretch')
                st.caption(f"필수 형태 ID: {card['required_form_id']} · 결과 형태 ID: {card['evolved_form_id']}")
                st.caption('특정 게임의 진화 가능 여부와 모든 예외를 보장하지 않습니다. 아이템 이름이 없으면 원문 식별자/ID로 표시합니다.')
                st.markdown(f"[근거 {card['citation_number']}] {card['title']} · [조건 원문]({card['source_url']}) · [종 이름 출처]({card['names_source_url']})")

st.markdown('<p class="pk-footer">비공식 포켓몬 백과형 서비스 · 고정 자료와 생성 번역의 범위는 답변의 근거에서 확인하세요. 원본 이미지와 생성 일러스트는 구분해 표시합니다.</p>',unsafe_allow_html=True)

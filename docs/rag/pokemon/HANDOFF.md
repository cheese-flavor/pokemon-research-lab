# Pokémon Research Lab 작업 인계

기준: 2026-10-23 KST. 다른 채팅·도구·PC에서 작업을 이어갈 때 README와 이 문서를 먼저 읽고, 현재 파일과 실제 실행 결과를 다시 확인한다. 키나 데이터 전문은 이 문서에 없다.

## 프로젝트와 사용자 결정

현재 도메인은 포켓몬이다. 영화 데이터는 예비 후보였으며 사용하지 않았다. 반려식물도 검토했지만 포켓몬 백과형 RAG로 확정했다. 원래 ML 결과와 Streamlit 실습 예제는 보존한다.

전국도감 1~1,025종을 대상으로 도감 설명·특성·진화 조건과 객관 조건 탐색을 제공한다. 최신 웹 전체 정보를 보장하는 서비스가 아니라 고정 PokéAPI 자료와 별도 생성 번역을 사용하는 비공식 도감이다. 특정 게임 적용 여부는 해당 버전의 근거로만 답한다.

작업은 `WORK_PLAN.md`에 맞춰 작은 단위로 진행하고, 사용자가 다음 단위를 요청하기 전 이후 기능까지 만들지 않는다. 현재 추가 작업은 6b이며, 사용자가 체크리스트 점검과 인계 문서도 명시적으로 함께 요청했다. 선택 심화 F2013~F2016은 미선택이다.

## 저장소와 제외 규칙

- 공개 GitHub: https://github.com/cheese-flavor/pokemon-research-lab
- 로컬 프로젝트 루트: `C:\Users\SSAFY\Desktop\05-pjt`.
- 원본 루트의 `origin`은 GitLab다. 일시 중단 후 사용자가 2026-10-23 GitLab 최신화를 다시 허용했다. GitLab은 원본 루트, 공개 GitHub는 별도 허용 목록 복사본에서 갱신한다. 원격을 확인하고 일반 푸시한다.
- GitHub는 과거 ML 이력이 없는 별도 공개 이력이다. 최초 공개 커밋은 `5eb9a2b`, 공개 확인 문서 커밋은 `5f24f79`였다. 후속 커밋은 실제 Git 로그에서 확인한다.
- 현재 공개 저장소 작업 복사본은 ignored `outputs/pokemon/public-release-v2/`다. 그 복사본의 `origin`은 GitHub다. 다른 PC에서는 GitHub를 새로 clone한다.
- PDF, 원본/점검 Excel, 데이터, 다운로드한 이미지, API 응답 캐시, 임베딩, 벡터 DB, `.env`와 비밀은 모든 원격에서 제외한다. 이미 추적된 파일에는 ignore가 소급되지 않으므로 매번 스테이징 목록을 검사한다.
- `scripts/export_pokemon_public.py`는 허용된 포켓몬 코드·설정·문서·테스트·생성 화면 에셋·집계 그림·기능 캡처만 새 폴더로 내보낸다. 대상은 새 폴더여야 한다. 기존 폴더 삭제/덮어쓰기나 과거 이력 재작성·force push를 하지 않는다.
- 공개 갱신은 내보내기 후보와 비밀 검사를 거친 변경 파일만 GitHub 작업 복사본에 복사·검토·명시적 stage·commit·일반 push한다. `result`의 공개 범위도 PNG와 Markdown뿐이다.

## 구현된 흐름과 파일

| 영역 | 주요 파일 / 역할 |
|---|---|
| 수집 | `scripts/collect_pokemon_bulk.py`: 1,025종 정식 재현 경로. `collect_pokemon.py`는 151종 파일럿 |
| 번역 | `translate_pokemon_descriptions.py`, `review_pokemon_translation.py`, `pokemon_korean_terms.py` |
| 메타 색인 | `index_pokemon_metadata.py`, `src/pokemon/data.py`, `embeddings.py`, `store.py` |
| 문서 준비 | `sources.py`, `ingestion.py`, `chunking.py`, `prompts.py` |
| RAG | `retrieval.py`, `graph.py`, `rag.py`, `citations.py`, `llm.py` |
| 전체 대화 | `conversation.py`: 정확한 이름/번호, 최대 3종의 별도 조회, 인용 재번호, 이전 주제 후속 질문 |
| 특화 기능 | `explore.py`: 조건 해석 후 모든 속성 재검사. `evolution.py`: 원본 조건 행 확장 |
| 화면 | `streamlit_lab/app.py`, `src/pokemon/ui_theme.py`, `streamlit_lab/assets/pokemon.css` |
| 설정/테스트 | `config/pokemon_rag.toml`, `requirements-pokemon-rag.txt`, `tests/test_pokemon*.py` |

LangGraph는 retrieve와 generate 두 노드다. 메타데이터를 반드시 포함하고, 외부 문서는 정확한 item_id/source_item_id와 요청 버전/버전 그룹으로 제한한다. 인용 번호가 맞는 것과 사실이 맞는 것은 별도 평가다. 사용한 출처만 화면에 표시하고 프롬프트/데이터 전문을 원격 tracing에 내보내지 않는다.

조건 탐색은 세대·타입·키·몸무게·능력치·전설/환상 여부만 실제 메타데이터로 재확인한다. 모호하거나 미지원 조건은 결과를 만들지 않는다. 진화 카드는 원본 조건 행을 확장하며 AND/OR, 0 값, 형태 ID, 적용 범위를 유지한다.

## 데이터와 로컬 전용 파일

| 경로 | 의미 |
|---|---|
| `dataset/pokemon/items.json` | 기본 개체에 연결한 1,025종 메타데이터 |
| `dataset/pokemon/documents.json` | 보존할 원본 코퍼스, 64,017문서 |
| `dataset/pokemon/documents_ko_enriched.json` | 후속 RAG용 보완 코퍼스, 64,264문서 |
| `dataset/pokemon/raw/bulk_*/` | 고정 리비전 CSV 20개와 원본 출처/해시 |
| `dataset/pokemon/ingestion/active.json` | 반드시 읽어야 하는 현재 설명 컬렉션 포인터 |
| `dataset/pokemon/ingestion/manifest_*.json` | 설정 세대별 필수 문서·청크 연결 |
| `dataset/pokemon/ingestion/cache/` | 검색/모델 캐시와 전체 provenance sidecar |
| `dataset/pokemon/vectorstore/`, `embeddings/` | 로컬 Chroma 및 GMS 임베딩 캐시 |
| `dataset/pokemon/artwork/` | 1,025종 이미지와 출처/해시 manifest |
| `streamlit_lab/.env` | 사용자가 입력한 로컬 GMS 키, 다른 환경에서 별도 준비 |
| `outputs/pokemon/` | 비공개 실행 결과·답변·점검 사본·공개 내보내기 복사본 |

한국어 설명이 없던 127종의 영어 버전 설명 247건을 GMS로 번역하고 별도 모델 검수했다. 생성 번역은 공식 한국어 문구나 독립된 사람 검수로 표시하지 않는다. 원문 언어/문구/ID/버전/모델/검수 provenance를 보존한다. 공식 한국어 명칭·구성요소 9개를 조사해 번역 11건을 보완했고, 날개의왕·무쇠이무기·외미르·내미르를 새 종으로 세지 않았다.

메타 1,025건을 색인했고 설명은 질문별로 증분 준비한다. 작업 4의 224청크는 역사적 수치이며 작업 7의 추가 질문 이후 기본 설명 컬렉션은 402청크가 됐다. 새로운 질문은 이 수를 늘릴 수 있다. 전체 코퍼스를 모두 선색인했다고 가정하지 않는다. 다른 청킹 설정은 별도 컬렉션으로 보존한다.

이름·타입 벡터 검색 점검은 기대 종 Top-5 3/5였으므로 고유명사 식별은 정확한 이름·번호를 사용한다. 의미 검색 품질이 충분히 검증됐다고 표현하지 않는다.

## 모델과 재실행

답변 모델은 사용자 선택 `gpt-6.1-sol`, 주소는 SSAFY GMS `https://gms.ssafy.io/gmsapi/api.openai.com/v1/responses`다. 임베딩은 GMS `text-embedding-3-small`, 1,536차원이다. 직접 OpenAI 계정으로 바꾸지 않는다. 모델 목록 조회는 500 오류였고 실제 임베딩/Responses 호출로 해당 모델을 확인했다.

기존 PC에서는 프로젝트 루트 PowerShell에서 실행한다.

```powershell
streamlit_lab/.venv/Scripts/python.exe -m streamlit run streamlit_lab/app.py --server.port 8501 --server.headless true
streamlit_lab/.venv/Scripts/python.exe -m unittest discover -s tests -p "test_pokemon*.py" -q
streamlit_lab/.venv/Scripts/python.exe -m pip check
streamlit_lab/.venv/Scripts/python.exe scripts/verify_pokemon_submission.py
```

페이지는 http://127.0.0.1:8501/ 이며 인터넷 배포 URL이 아니다. 서버 프로세스가 종료되면 다시 실행한다. 포트 8502는 이번 셀프 점검의 임시 결함 주입 화면이며 제품 서비스가 아니다.

다른 PC는 README의 설치 순서를 따른다. Python 3.11 이상, 새 venv, requirements 설치, bulk 수집, 사용자 로컬 `.env`, 번역/용어 검수 절차, 메타 색인, 이미지 수집 후 앱을 실행한다. 데이터와 키가 GitHub에 없으므로 clone만으로 동일 화면/답변이 바로 재현되지는 않는다. 원본 키를 이 문서나 대화·브라우저 업로드로 옮기지 않는다. 새 번역/색인/질문은 실제 GMS 호출이 생길 수 있다. 캐시가 없는 상태의 offline 검증은 실패하는 것이 정상이다. 새 PC 전체 설치 재현은 아직 실행 검증하지 않았다.

## 최신 화면·성능 정책

디자인은 빨강/흰색 전자 도감과 수채화 그림 조합이다. 피카츄·코일은 생성 수채화, 다른 종은 PokéAPI 원본 그림이며 구분·출처를 표시한다. 없는 이미지는 회색 공통 실루엣과 물음표다. 원본 이미지 1,025종을 확보했고 오프라인 해시 확인에서 누락/오류 0이었다. 다운로드 원본은 공개하지 않는다. Tabler 아이콘의 MIT 고지를 포함한다. 포켓몬 이미지의 재사용 권리를 포괄적으로 보장하지 않는다.

최신 사용자 요청으로 왼쪽은 아이콘 전체 도감만 남기고, 제목은 영어로 바꿨다. 대화는 선택 도감과 독립된 전체 세션이며 원래의 항목별 기록 규칙을 대체한다. 출처 종 격리는 그대로다. 한 번에 최대 3종을 분리 설명하며 비교 결론을 별도로 합성하는 기능은 아니다.

준비된 종의 단순 질문은 동일 세대의 필수 문서/청크를 확인해 준비용 모델 2단계를 재사용한다. 버전 표현·다른 설정·미준비 종은 원래 흐름을 따른다. 파이리의 준비된 새 질문 7.390초, 같은 질문 반복 1.070초를 실측했다. 과거 신규 자료 준비 포함 질문은 약 44초였다. 조건이 달라 동일 조건 개선율로 계산하지 않는다. 상세는 `GLOBAL_CHAT_VALIDATION.md`.

## 검증·체크리스트와 남은 일

최신 회귀 70개 통과, RAG 8사례 및 Top-k 3/5/8 비교, 제출 캐시 10사례, 메타 재색인 두 번 1,025건 유지, pip check를 실행했다. 기능별 실제 화면은 루트 `result/`에 있다. 실제 실행하지 않은 별도 환경/품질 시험을 통과로 바꾸지 않는다.

로컬 원본 `2회차_셀프·상호_체크리스트.xlsx`는 보존했고 입력 사본은 `outputs/pokemon/checklist-review/2회차_체크리스트_셀프점검_20261023.xlsx`다. 27항목을 통과 17 / 실패 2 / 미확인 2 / 해당없음 6으로 채웠다. 원문·방법·집계 수식·서식·선택 목록을 유지하며, 실제 사람의 상호 점검과 피드백은 미실시다. 이 사본도 Git 제외다.

남은 사항:

1. 전체 대화 유지 정책과 원본 F2009/체크리스트 10번의 항목별 대화 분리 기준을 평가자와 정합화한다. 요청된 전체 대화를 임의로 되돌리지 않는다.
2. F2004의 고정 외부 자료 카탈로그 검색이 질문 시점 원격 검색 요구를 충족하는지 평가 기준을 확인한다. 현재 이를 완전 통과로 표시하지 않는다.
3. 신규 종/미준비 상태의 지연과 더 넓은 질문 표본을 평가한다. 캐시 재현을 cold/network 성능으로 부르지 않는다.
4. 실제 교육생 상호 점검과 독립된 사실 평가를 받고, 제출자·파일명 규칙을 확인해 최종 제출물을 구성한다. 현재 최종 제출 승인 완료는 아니다.
5. 외부 서비스 배포나 선택 심화는 사용자가 별도 요청할 때 진행한다.

과거 상세 기록은 `DATA_VALIDATION.md`, `TRANSLATION.md`, `KOREAN_TERMS.md`, `EDA.md`, `INDEXING.md`, `INGESTION.md`, `RAG_VALIDATION.md`, `UI_VALIDATION.md`, `FINAL_REVIEW.md`, `SUBMISSION.md`, `ARTWORK.md`, `PUBLIC_RELEASE.md`를 순서에 맞게 참고한다. 문서별 당시 수치와 최신 상태를 구분한다.

## 이번 대화의 저장 지점

사용자가 대화 용량을 고려해 재개 가능한 상태만 남기도록 요청했다. 추가 개발·큰 검증은 중단했다. 구현 코드와 현재 점검 결과를 저장하되 최종 제출 승인으로 표시하지 않는다.

재개할 때 할 일은 먼저 Git 상태와 이 문서를 확인하고 앱을 재시작하는 것이다. 마지막 종별 프롬프트 문구 다듬기까지 회귀 70개는 통과했지만, 그 문구의 복수 종 브라우저 재촬영과 독립 사실 검수는 남아 있다. 기존 08번 캡처를 이 문구의 최종 검증으로 부르지 않는다. 핵심 기능 화면 13장과 셀프 점검 사본은 이미 저장했다.

다음 채팅에 사용할 요청 예시: “docs/rag/pokemon/HANDOFF.md와 WORK_PLAN.md를 먼저 읽고 현재 상태를 확인해줘. GitLab과 GitHub 원격 및 공개 제외 규칙을 확인해. 우선 미완료 점검을 설명한 뒤 내가 지정한 작업만 진행해줘.”

이번 UI/전체 대화/준비 재사용 구현의 원본 로컬 커밋: `e0b020b`. 공개 GitHub 복사본의 커밋 해시는 별도 이력이므로 다를 수 있다.

최신 지시: 사용자가 GitLab 최신화를 재허용했다. 이전 GitLab 중단 기록은 당시 상황이다. 제출 원문 21~23쪽 재확인 결과 별도 ZIP 제출 형식이 있으며 SUBMISSION.md 마지막 절에 정리했다. ZIP 생성·실제 제출은 아직 수행하지 않았다.

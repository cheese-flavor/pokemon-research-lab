# 작업 3: GMS 임베딩과 메타데이터 색인 검증

실행일: 2026-10-23. 1,025종 메타데이터 컬렉션 구축까지 완료했다. 문서 컬렉션·프롬프트 1/2·LangGraph·답변 생성·UI는 아직 구현하지 않았다.

## 연결과 설정

- GMS 모델 목록 조회는 HTTP 500으로 실패했다. 전체 지원 모델 목록을 확보했다고 주장하지 않는다.
- GMS `/embeddings`에 `text-embedding-3-small`을 실제 호출하여 응답 모델명과 1,536차원을 확인했다. 전체 색인에서도 모델명·응답 인덱스·벡터 차원·유한값·영벡터 여부를 검증했다.
- 임베딩 경유 주소: `https://gms.ssafy.io/gmsapi/api.openai.com/v1/`. 다른 주소로 바꾸면 코드가 거절한다. Chroma 기본 임베딩 함수는 사용하지 않는다.
- 답변 모델 설정은 사용자 선택인 `gpt-6.1-sol`을 유지했다. 이번 작업에서 답변 모델을 호출하지 않았다.
- 키는 환경변수 `GMS_KEY` 또는 로컬 `streamlit_lab/.env`에서만 읽는다. 루트 `.env.example`은 빈 값 템플릿이다.
- 설정: [pokemon_rag.toml](../../../config/pokemon_rag.toml). 실제 환경 Python 3.11.9, Chroma 1.5.9, OpenAI SDK 2.54.0, python-dotenv 1.2.3, tiktoken 0.14.0. TOML 로더 사용으로 색인 실행은 Python 3.11 이상이 필요하다.

## 실제 결과

| 항목 | 최초 온라인 실행 | 두 번째 오프라인 실행 |
|---|---|---|
| 컬렉션 | pokemon_meta_v1 | 동일 |
| 실행 전 건수 | 0 | 1,025 |
| 실행 후 건수 | 1,025 | 1,025 |
| 임베딩 요청 수 | 33 | 0 |
| 임베딩 캐시 적중 입력 수 | 0 | 1,025 |
| API 보고 총 토큰 | 237,130 | 0 |
| 처리 시간 | 76.766초 | 7.406초 |
| 입력 파일 SHA-256 전후 일치 | 확인 | 확인 |

최초 연결 확인 1회(15토큰)와 검색 점검 1회(69토큰)는 표의 색인 요청과 별도다. GMS 가격·차감액은 확인하지 않았으므로 직접 OpenAI 가격으로 비용을 계산하지 않는다. 단일 실행의 시간이며 서비스 응답시간 p95 검증은 아니다.

전국도감 ID 1~1,025 전체 집합, 저장된 텍스트 및 본문 해시, 고유 건수의 일치를 확인했다. 원본 `items.json`은 변경하지 않았다. 기존 `index_text`에 없던 여섯 능력치와 합계는 색인용 파생 텍스트에서 보강했고 1,025건 모두에 포함됐음을 검사했다. 스냅샷·기본 형태 범위도 유지했다.

## 한국어 검색 점검과 한계

이름과 타입을 포함한 간단한 한국어 질의 5개로 벡터 검색 연결을 점검했다. 목표 항목의 Top-1 적중은 3/5, Top-5 적중도 3/5였다. 목표 순위는 질의 순서대로 `[1, 1, 미포함, 1, 미포함]`이다. 질의와 예상 ID는 재현 스크립트의 `PROBES`에서 확인한다. 5개 항목의 ID 직접 조회는 모두 성공했다.

작은 점검 결과만으로 한국어 검색 품질이 충분하다고 판단하지 않는다. 특히 고유명사 검색에서 벡터 유사도만으로 종을 결정하지 않는다. 선택 항목의 메타데이터는 계획대로 ID 직접 조회로 항상 포함하고, 다음 작업에서 정확한 이름·번호·검증된 별칭을 먼저 해석한다. 조건 탐색은 의미 검색 후보를 객관적 조건으로 재검사해야 한다. 문서 검색 품질·관련 질문·최종 답변 정확성은 미검증이다.

## 재현

기존 프로젝트 환경 또는 Python 3.11+ 가상환경에서 실행한다.

```powershell
python -m pip install -r requirements-pokemon-rag.txt
python scripts/index_pokemon_metadata.py
python scripts/index_pokemon_metadata.py --offline
python scripts/check_pokemon_metadata.py
python scripts/check_pokemon_metadata.py --offline
python -m unittest discover -s tests -p "test_pokemon*.py" -v
python -m pip check
```

`--offline`은 캐시가 없으면 실패하며 GMS를 호출하지 않는다. 검색 점검의 오프라인 실행은 먼저 온라인 점검으로 질의 벡터를 캐시해야 한다. 키가 없는 환경에서도 캐시가 완전하면 오프라인 재색인은 가능하다.

입력·스키마·모델·차원·색인 텍스트 해시로 컬렉션 서명을 고정한다. 다른 입력을 같은 컬렉션에 섞으려 하면 실패한다. 변경 시 새 컬렉션 이름으로 구축하며 이전 저장소를 자동 삭제하지 않는다. 고정 종 ID로 upsert하므로 같은 입력 재실행 시 중복이 생기지 않는다.

쓰기 잠금은 병렬 색인을 차단한다. 프로세스 강제 종료 후 잠금이 남으면 실행 중인 색인 프로세스가 없음을 확인한 뒤 해당 로컬 잠금 파일만 제거한다. 캐시는 키·벡터 해시·차원을 검사하고 파일 교체로 저장한다. 깨진 캐시를 조용히 사용하거나 다른 모델로 대체하지 않는다.

## 저장 위치와 검증 범위

- 벡터 DB: 로컬 `dataset/pokemon/vectorstore/`.
- 임베딩 캐시: 로컬 `dataset/pokemon/embeddings/`.
- 색인 manifest와 출처 연결: 로컬 `dataset/pokemon/indexing/metadata_manifest.json`.
- 집계 실행 기록: 로컬 `outputs/pokemon/indexing/`.
- 위 경로와 키는 Git에서 제외한다. 이번 커밋에는 코드·설정·빈 키 템플릿·테스트·집계 보고서만 포함한다.
- 포켓몬 관련 테스트 29개 통과. 신규 7개는 캐시 변조, 오프라인 실패 시 무호출, 응답 모델/인덱스 오류, 비정상 벡터, GMS 주소 고정, 동시 쓰기 차단, 실제 Chroma 재색인과 서명 충돌을 확인한다. `pip check`도 통과했다.

F2002의 색인·건수·멱등성은 실행 확인했으며 화면의 색인 건수 표시는 작업 6에서 검증한다. NF2003/4의 코드·CLI 비밀 비노출을 반영했고 실제 서비스 오류 화면은 아직 검증하지 않았다. 다음은 작업 4, 검색어 추출·후보 선별·문서 청킹 및 별도 컬렉션 색인이다.

참고: [OpenAI 임베딩 요청 형식](https://developers.openai.com/api/docs/guides/embeddings), [Chroma upsert 동작](https://docs.trychroma.com/docs/collections/update-data). GMS 지원 여부는 이 문서의 실제 호출 결과로 구분했다.

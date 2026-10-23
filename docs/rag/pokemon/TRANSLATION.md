# 작업 1 후속: 한국어 도감 설명 번역 보완

사용자가 8·9세대 한국어 설명 결측을 영어 원문 번역으로 보완하도록 요청한 작업이다. 요구사항 설계·임베딩·RAG·UI 구현으로 범위를 확장하지 않는다.

## 보완 원칙

- PokéAPI 원본에 한국어 도감 설명이 하나도 없는 종만 대상이다. 이미 한국어 설명이 있는 다른 세대 및 항목은 변경하지 않는다.
- 한 종의 여러 게임 버전은 각각 번역한다. 스칼렛과 바이올렛의 설명을 합치거나 한 버전의 설명으로 다른 버전을 채우지 않는다.
- 포켓몬 이름은 수집한 한국어 이름을 용어집으로 제공한다. 원문에 언급된 다른 포켓몬 이름도 연결한다.
- 원문에 없는 타입·진화 조건·기술·설정을 덧붙이지 않는다. 수치·단위·행위 주체·부정·추측·전승·관찰자 시점을 유지한다.
- 번역 후 같은 모델의 별도 요청으로 원문과 대조한다. 이는 독립된 사람의 전수 검수가 아니다.
- 공식 한국어 문구를 복원했다고 주장하지 않는다. 원본 한국어와 생성 번역을 반드시 구별한다.

## GMS 연결

- 실제 연결 모델: 사용자 지정 `gpt-6.1-sol`.
- GMS Responses: `https://gms.ssafy.io/gmsapi/api.openai.com/v1/responses`.
- 키 파일: 로컬 `streamlit_lab/.env`의 `GMS_KEY`. 값은 로그·문서·Git에 출력하지 않는다.
- 구조화 JSON 응답, 결과 ID 집합·한국어 본문·원문 수치 보존 검사. `10,000`과 `1만`처럼 값이 같은 표기는 허용한다.
- 본문·모델·프롬프트·용어집에 따른 요청 해시로 번역/검수 결과를 캐시한다. 같은 입력은 재호출하지 않는다.
- `store=False`, SDK 타임아웃·제한된 재시도 사용. 오류 출력은 오류 종류·HTTP 상태 및 로컬 검증 실패 사유로 제한한다.
- 응답 형식 구현 참고: https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses

## 재현

```powershell
python -m pip install -r requirements-pokemon.txt
python scripts/translate_pokemon_descriptions.py --limit 3 --batch-size 3
python scripts/translate_pokemon_descriptions.py
python scripts/translate_pokemon_descriptions.py --offline
python scripts/review_pokemon_translation.py
python -m unittest discover -s tests -p test_pokemon_translation.py -v
```

기본 배치는 24건이다. 오프라인 재현은 동일 배치 크기의 번역·검수 캐시가 있어야 하며, 캐시가 없으면 모델을 호출하지 않고 실패한다. `--limit`은 파일럿 파일만 생성하며 전체 보완 문서를 만들지 않는다. SDK 의존성을 사용하는 작업으로, 기본 원본 수집기는 여전히 표준 라이브러리만으로 실행된다.

## 로컬 결과와 원본 보존

| 로컬 파일 | 역할 |
|---|---|
| `dataset/pokemon/documents.json` | 원본 설명문. 수정하지 않음 |
| `dataset/pokemon/translations/korean_descriptions.json` | 원문 문서 ID에 연결한 생성 한국어 번역 |
| `dataset/pokemon/translations/cache/` | 번역·검수 응답 및 사용량 캐시. Git 제외 |
| `dataset/pokemon/translations/manifest.json` | 번역 범위·남은 결측·모델·검수 방식 집계 |
| `dataset/pokemon/documents_ko_enriched.json` | 원본 전체 + 생성 번역을 결합한 후속 RAG용 보완본 |
| `outputs/pokemon/translation_audit.json` | 원본 보존·버전·수치·연결·보완 범위 검증 |
| `outputs/pokemon/TRANSLATION_REVIEW.md` | 기존 세대 비교 예시 4쌍 및 전체 영어·번역문 대조 |

후속 RAG에서는 `documents_ko_enriched.json`을 사용하고, `is_machine_translation`, `is_official_korean_text`, `original_doc_id`, `original_content`, `translation_model`, 실제 응답 모델, 번역·검수 시각, 게임 버전, 출처 URL을 유지해야 한다. 원본 한국어가 없는 127종이라는 사실 자체가 바뀌는 것은 아니며, 생성 한국어 근거로 보완하는 것이다.

## 공식 용어 대조

엑스레그의 `Showdown Mode`를 모델이 '승부모드'로 처리한 사례를 확인했다. 포켓몬 공식 도감의 용어 **결전 모드**로 후처리하며, 교정의 범위·출처·규칙 버전을 각 해당 레코드에 남긴다. 다른 포켓몬의 모드 명칭을 일괄 치환하지 않는다.

확인 출처: https://pokemonkorea.co.kr/pokedex/view/1172

용어 대조를 일부 수행했지만 247건 전체를 공식 한국어 원문과 대조한 것은 아니다. 번역 결과가 공식 문구와 일치한다고 보장하지 않는다.

나오하 스칼렛 설명은 원문의 `it`을 한국어 번역에서 '얼굴'로 한정한 부분을 표본 검토에서 발견해 대상을 한정하지 않도록 수정했다. 이 의미 보정은 용어 교정과 별개인 `fidelity_corrections`로 기록한다.

## 실행·검증 결과 (2026-10-22)

| 항목 | 결과 |
|---|---:|
| 원본 한국어 설명 보유 종 | 898 |
| 번역 보완 종 | 127 (8세대 7 / 9세대 120) |
| 번역 문서 | 247 (레전드 아르세우스 7 / 스칼렛 120 / 바이올렛 120) |
| 보완본 한국어 설명 보유 종 | 1,025 |
| 보완본 한국어 설명 결측 종 | 0 |
| 원본 문서 | 64,017, 모두 그대로 보존 |
| 보완 문서 | 64,264 |
| 모델 검수 수정 메모가 있는 문서 | 9 |
| 공식 용어 추가 교정 문서 | 2 |
| 표본 의미 보정 문서 | 1 |

전체 번역과 검수에서 실제 응답 모델 `gpt-6.1-sol`을 확인했다. 오프라인 캐시 재적용 시 신규 모델 호출은 0회였다. 원문 문서 전체 보존, 번역 대상 ID와 게임 버전 일치, 원문 URL·리비전·영어 내용 연결, 한국어 표시 및 수치 보존, 1,025종 한국어 근거 보유를 실제 보완본에서 검사했다.

수집·번역 관련 자동 테스트 15개가 통과했다. 숫자 누락·숫자 부분문자열 오인·한국어 만 단위 동치, 기존 한국어 보존, 원본 덮어쓰기 거부, 버전 ID 누락, 고유명사 연결, 교정 범위 및 기존 수집 계약을 포함한다. 모든 문장의 사실 충실성을 자동 테스트로 보장한다는 뜻은 아니다.

비교 문서에는 **신비록–노라키 / 사마자르–스라크 / 나오하–이상해씨 / 뜨아거–파이리** 4쌍을 원문·게임 버전과 함께 수록했다. 서로 다른 포켓몬의 설정이 같다는 주장이 아니라 도감 문체·구체성·원문 충실성을 확인하는 용도다. 전체 247건의 원문·생성 번역도 같은 로컬 문서에 포함한다.

후속 업데이트: 공식 한국어 명칭 검색을 통해 9개 용어를 확인하고 11건을 추가 보완했다. 위 최초 실행 집계와 구별하며, 최신 검증·교정 범위는 `KOREAN_TERMS.md` 참고. 현재 규칙은 `scripts/pokemon_korean_terms.py`로 분리했다.

# 한국어 공식 용어 대조·보완

2026-10-22. 사용자 요청에 따라 기존 생성 번역에서 한국어 명칭·설정 용어를 검색하고 공식 자료와 대조했다. 전체 번역문을 다시 생성하거나 다른 기능 구현으로 진행하지 않았다.

## 검색·확인 결과

| 영어 원문 용어 | 확인한 한국어 표기 | 적용 기준 및 공식 출처 |
|---|---|---|
| Winged King | 날개의왕 | 코라이돈의 원문에 해당 별칭이 있을 때만. [공식 도감](https://www.pokemonkorea.co.kr/pokedex/view/1274) |
| Iron Serpent | 무쇠이무기 | 미라이돈의 원문에 해당 별칭이 있을 때만. [공식 도감](https://www.pokemonkorea.co.kr/pokedex/view/1275) |
| fore-wyrm | 외미르 | 과미르의 구성 개체 이름. 일반적인 '앞쪽 벌레' 직역을 보완. [공식 도감](https://pokemonkorea.co.kr/pokedex/view/1278) |
| core-wyrm | 내미르 | 과미르의 구성 개체 이름. 일반적인 '속의 벌레' 직역을 보완. [공식 도감](https://pokemonkorea.co.kr/pokedex/view/1278) |
| Showdown Mode | 결전 모드 | 엑스레그. 이전에 교정한 표현을 이번에도 확인·유지. [공식 도감](https://pokemonkorea.co.kr/pokedex/view/1172) |
| flame sac | 불꽃 주머니 | 뜨아거 공식 설명의 신체 용어 표기를 동일한 영어 용어가 있는 뜨아거·악뜨거 설명에 적용. [뜨아거 공식 도감](https://pokemonkorea.co.kr/pokedex/view/1160) |
| Hisui | 히스이지방 | 지역을 의미할 때 공식 지역 표기로 통일. 기존 '히스이'를 잘못된 번역이라고 단정하지 않음. [공식 게임 소개](https://pokemonkorea.co.kr/game/view/11503) |
| Paldea / Paldean | 팔데아지방 | 지역명 또는 지역 수식어일 때 적용. 조사도 '팔데아로 → 팔데아지방으로'처럼 조정. [공식 게임 설명](https://pokemonkorea.co.kr/sv/menu189?mode=view&number=2624) |
| Terastal | 테라스탈 | 기존 번역이 맞아 변경 없이 확인 이력만 추가. [공식 게임 설명](https://pokemonkorea.co.kr/sv/menu189?mode=view&number=2624) |

원문에 별칭이나 용어가 없는 문서에는 새 설정을 넣지 않는다. 예를 들어 코라이돈의 모든 버전에 '날개의왕'을 추가하지 않는다. 별칭 표기를 종 이름 자체와 혼동하지 않는다. 외미르·내미르를 별도 전국도감 종으로 추가하지 않는다.

이 목록은 실제 번역문에서 확인한 전문 용어와 지역명에 대한 대조 결과다. 모든 한국어 포켓몬 이름 1,025개나 모든 팬 커뮤니티 약칭을 웹에서 전수 확인했다는 뜻은 아니다. 검증하지 않은 별명은 추가하지 않았다.

## 구현·데이터 반영

- `scripts/pokemon_korean_terms.py`: 영어 원문과 종 ID에 따라 범위를 제한한 9개 규칙, 공식 출처, 규칙 버전 보존.
- `scripts/translate_pokemon_descriptions.py --offline`: 기존 모델 캐시에서 한국어 보완본 재생성. 신규 GMS 호출 0회.
- 번역 레코드에 `verified_korean_term_mentions`와 `verified_terminology_corrections`를 저장한다. 이미 올바른 테라스탈 등의 용어도 확인 이력을 구별해 남긴다.
- 원본 `documents.json`과 기존 수록 한국어 문장은 수정하지 않는다. 생성 번역 247건과 결합한 `documents_ko_enriched.json`을 갱신한다.
- 이번 변경 직전의 생성 번역은 로컬 `translations/korean_descriptions_before_localization.json`에 보존했다.
- `python scripts/review_pokemon_translation.py`로 보완 전후가 있는 로컬 `outputs/pokemon/KOREAN_TERMS_REVIEW.md`와 집계를 만든다. 기준 파일이 없는 새 환경에서도 원문·번역 검증과 전체 대조 문서는 생성하며, 과거 대비 변화량 보고서만 생략한다.

## 실제 검증 결과

- 신규 내용 수정: **11종의 버전별 설명 11건**. 이 중 과미르 한 문서에 구성 개체 이름 2개가 보완됨.
- 이전부터 적용한 결전 모드 2건을 포함하면 모델 초안 대비 용어 교정 이력이 있는 문서는 총 13건.
- 확인한 용어가 실제로 나타나는 이력은 15회. 고유 종 수나 독립된 외부 문서 수와 구별한다.
- 원본 문서 64,017건 보존, 보완본 64,264건, 한국어 설명 보유 1,025종, 남은 한국어 설명 결측 0종 유지.
- 자동 테스트 22개 통과. 별칭·구성 개체명, 원문 용어 부재 시 미적용, 다른 종에 미적용, 반복 적용 시 불변, 조사 보정 및 기존 수집·번역 계약 포함.
- 공식 페이지 본문·전체 도감·수집 결과·API 키는 Git에 추가하지 않는다. 규칙 코드·테스트·용어와 출처·집계 문서만 반영한다.

공식 용어로 보완했어도 문장 전체는 원문 영어를 바탕으로 한 생성 번역이다. 원문의 추측·전승·수치·단위·게임 버전은 유지하며, 공식 한국어 도감 원문과 동일하다고 표시하지 않는다.
